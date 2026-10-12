#!/usr/bin/env python3
"""Build an end-to-end agropastoral drought risk raster for QGIS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agroclimate_core.acmad_boundaries import build_wfs_getfeature_url, niger_boundary_request
from agroclimate_core.acmad_download import DEFAULT_ACMAD_API_BASE_URL, download_acmad_raster
from agroclimate_core.raster_pipeline import ExposureDefaults, build_agropastoral_risk_rasters, risk_class_labels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download or reuse ACMAD CDI, clip it to Niger, combine it with exposure scores, "
            "and write GeoTIFF risk outputs for QGIS."
        )
    )
    parser.add_argument("--year", type=int, required=True, help="ACMAD product year.")
    parser.add_argument("--month", type=int, required=True, help="ACMAD product month, 1-12.")
    parser.add_argument("--dekad", type=int, default=1, choices=(1, 11, 21), help="Dekad for CDI/SMA/FAPAR products.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/agropastoral_risk"), help="Output directory.")
    parser.add_argument("--acmad-api-base-url", default=DEFAULT_ACMAD_API_BASE_URL, help="ACMAD API base URL.")
    parser.add_argument("--acmad-geoserver-url", default="https://ada.acmad.org/geoserver", help="ACMAD GeoServer base URL.")
    parser.add_argument("--cdi-raster", type=Path, help="Use an existing CDI GeoTIFF instead of downloading from ACMAD.")
    parser.add_argument(
        "--cdi-code-scheme",
        choices=("acmad", "score", "one-based"),
        default="acmad",
        help=(
            "How to convert CDI raster values to 0-3 hazard scores. "
            "'acmad' maps ACMAD detailed CDI codes, 'score' expects values already on 0-3, "
            "and 'one-based' maps 1-4 to 0-3."
        ),
    )
    parser.add_argument("--one-based-cdi", action="store_true", help="Deprecated shortcut for --cdi-code-scheme one-based.")
    parser.add_argument("--cultivated-raster", type=Path, help="Optional 0-3 cultivated exposure raster.")
    parser.add_argument("--rangeland-raster", type=Path, help="Optional 0-3 rangeland exposure raster.")
    parser.add_argument("--water-points-raster", type=Path, help="Optional 0-3 water-point exposure raster.")
    parser.add_argument("--default-cultivated-score", type=float, default=2.0, help="Fallback cultivated exposure score.")
    parser.add_argument("--default-rangeland-score", type=float, default=2.0, help="Fallback rangeland exposure score.")
    parser.add_argument("--default-water-score", type=float, default=1.0, help="Fallback water-point exposure score.")
    return parser.parse_args()


def download_niger_boundary(output_path: Path, geoserver_url: str) -> Path:
    request = niger_boundary_request(wfs_url=geoserver_url, admin_level=0)
    url = build_wfs_getfeature_url(request)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("features"):
        raise RuntimeError(f"ACMAD boundary request returned no features: {url}")
    output_path.write_text(json.dumps(payload), encoding="utf-8")
    return output_path


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    boundary_path = download_niger_boundary(args.output_dir / "niger_boundary_admin0.geojson", args.acmad_geoserver_url)
    cdi_path = args.cdi_raster
    if cdi_path is None:
        cdi_path = download_acmad_raster(
            data_name="cdi",
            year=args.year,
            month=args.month,
            dekad=args.dekad,
            output_path=args.output_dir / f"acmad_cdi_{args.year}_{args.month:02d}_{args.dekad:02d}.tif",
            base_url=args.acmad_api_base_url,
        )

    outputs = build_agropastoral_risk_rasters(
        cdi_raster=cdi_path,
        boundary_geojson=boundary_path,
        output_dir=args.output_dir,
        cultivated_raster=args.cultivated_raster,
        rangeland_raster=args.rangeland_raster,
        water_points_raster=args.water_points_raster,
        exposure_defaults=ExposureDefaults(
            cultivated=args.default_cultivated_score,
            rangeland=args.default_rangeland_score,
            water_points=args.default_water_score,
        ),
        cdi_code_scheme="one-based" if args.one_based_cdi else args.cdi_code_scheme,
    )

    print("Risk outputs written:")
    for name, path in outputs.items():
        print(f"- {name}: {path}")
    print("Risk class labels:")
    for value, label in risk_class_labels().items():
        print(f"- {value}: {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
