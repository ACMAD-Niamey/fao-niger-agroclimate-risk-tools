#!/usr/bin/env python3
"""Build an end-to-end agropastoral drought risk raster for QGIS."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agroclimate_core.acmad_boundaries import build_wfs_getfeature_url, niger_boundary_request
from agroclimate_core.acmad_download import DEFAULT_ACMAD_API_BASE_URL, download_acmad_raster
from agroclimate_core.acmad_availability import (
    combined_product_seasons,
    fetch_available_datasets,
    fetch_dataset_catalog,
    latest_dekad_range,
)
from agroclimate_core.acmad_download import AcmadProductNotFound, download_combined_product
from agroclimate_core.periods import (
    DekadPeriod,
    PeriodUnavailableError,
    SeasonPeriod,
    resolve_dekad,
    resolve_season,
)
from agroclimate_core.raster_pipeline import ExposureDefaults, build_agropastoral_risk_rasters, risk_class_labels
from agroclimate_core.run_metadata import write_run_metadata

logger = logging.getLogger("build_agropastoral_risk_raster")


def dekad_from_day(day: int) -> int:
    if day <= 10:
        return 1
    if day <= 20:
        return 11
    return 21


def resolve_analysis_period(args: argparse.Namespace) -> tuple[int, int, int, str]:
    if args.analysis_date:
        analysis_date = date.fromisoformat(args.analysis_date)
        return (
            analysis_date.year,
            analysis_date.month,
            dekad_from_day(analysis_date.day),
            analysis_date.isoformat(),
        )

    if args.year is None or args.month is None:
        raise SystemExit("Either --analysis-date or both --year and --month are required.")

    analysis_label = f"{args.year}-{args.month:02d}-{args.dekad:02d}"
    return args.year, args.month, args.dekad, analysis_label


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download or reuse ACMAD CDI, clip it to Niger, combine it with exposure scores, "
            "and write GeoTIFF risk outputs for QGIS."
        )
    )
    parser.add_argument(
        "--analysis-date",
        help="Analysis date as YYYY-MM-DD. The script derives year, month, and dekad from the day.",
    )
    parser.add_argument("--year", type=int, help="ACMAD product year. Required if --analysis-date is not used.")
    parser.add_argument("--month", type=int, help="ACMAD product month, 1-12. Required if --analysis-date is not used.")
    parser.add_argument("--dekad", type=int, default=1, choices=(1, 11, 21), help="Dekad for CDI/SMA/FAPAR products.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory. Defaults to outputs/niger-risk-<analysis-date-or-period>.",
    )
    parser.add_argument("--acmad-api-base-url", default=DEFAULT_ACMAD_API_BASE_URL, help="ACMAD API base URL.")
    parser.add_argument("--acmad-geoserver-url", default="https://ada.acmad.org/geoserver", help="ACMAD GeoServer base URL.")
    parser.add_argument(
        "--hazard",
        choices=("cdi", "combined"),
        default="cdi",
        help=(
            "Hazard input: 'cdi' is the current dekadal CDI; 'combined' is ACMAD's seasonal combined "
            "monitoring and forecast hazard (1 degree, classes 1-9)."
        ),
    )
    parser.add_argument("--combined-product", default="combined_drought_hazard_era5", help="ACMAD combined product name.")
    parser.add_argument("--forecast-period", help="Season for --hazard combined, for example SON. Default: chosen from the date.")
    parser.add_argument("--forecast-year", type=int, help="Year of the first month of --forecast-period.")
    parser.add_argument("--combined-hazard-raster", type=Path, help="Use an existing combined hazard GeoTIFF.")
    parser.add_argument(
        "--grid-template",
        type=Path,
        help=(
            "Raster whose grid the outputs use. Defaults to the first exposure raster given, so a coarse "
            "combined hazard is shown on the finer exposure grid."
        ),
    )
    parser.add_argument(
        "--cdi-product",
        default="cdi",
        help="ACMAD CDI product to download, as named by get_available_datasets (cdi or cdi_era5).",
    )
    parser.add_argument(
        "--max-fallback-dekads",
        type=int,
        default=3,
        help="If the requested dekad is not published yet, use the latest one provided it is at most this many dekads older.",
    )
    parser.add_argument(
        "--strict-dates",
        action="store_true",
        help="Fail instead of falling back to the latest published dekad. Always on when --year/--month are given.",
    )
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
    parser.add_argument(
        "--no-agropastoral-mask",
        action="store_true",
        help=(
            "Score every cell. By default, when exposure rasters are given, only cells with cultivated or "
            "rangeland exposure above zero are scored; the rest are left as no data."
        ),
    )
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


@dataclass
class HazardSelection:
    """Which hazard data a run uses, decided before anything is downloaded."""

    name: str  # key of the clipped hazard in the outputs: "cdi" or "combined_hazard"
    label: str  # goes into the default output folder name
    code_scheme: str
    metadata: dict[str, Any]
    fetch: Callable[[Path], Path]  # downloads into the output folder, returns the raster path


def requested_date(args: argparse.Namespace, year: int, month: int, dekad: int) -> date:
    return date.fromisoformat(args.analysis_date) if args.analysis_date else date(year, month, dekad)


def select_cdi_hazard(args: argparse.Namespace) -> HazardSelection:
    """Choose the CDI dekad from what ACMAD has actually published.

    Publication lags behind the calendar, so "today" usually has no CDI yet. An
    explicit --year/--month is an exact request and is never silently replaced.
    """

    year, month, dekad, analysis_label = resolve_analysis_period(args)
    requested = requested_date(args, year, month, dekad)
    code_scheme = "one-based" if args.one_based_cdi else args.cdi_code_scheme

    if args.cdi_raster is not None:
        return HazardSelection(
            name="cdi",
            label=analysis_label,
            code_scheme=code_scheme,
            metadata={"source": "local file", "requested_date": requested, "code_scheme": code_scheme},
            fetch=lambda _output_dir: args.cdi_raster,
        )

    availability = fetch_available_datasets(args.acmad_api_base_url)
    earliest, latest = latest_dekad_range(availability, args.cdi_product)
    resolved = resolve_dekad(
        requested,
        latest,
        earliest,
        max_fallback_dekads=args.max_fallback_dekads,
        strict=args.strict_dates or args.analysis_date is None,
    )
    if resolved.fallback:
        logger.warning(
            "CDI for %s is not published yet; using %s (%d dekads older). The map shows that earlier period.",
            resolved.requested.label,
            resolved.period.label,
            resolved.lag_dekads,
        )
    period = resolved.period

    def fetch(output_dir: Path) -> Path:
        return download_acmad_raster(
            data_name=args.cdi_product,
            year=period.year,
            month=period.month,
            dekad=period.dekad,
            output_path=output_dir / f"acmad_{args.cdi_product}_{period.year}_{period.month:02d}_{period.dekad:02d}.tif",
            base_url=args.acmad_api_base_url,
            # With mask_nodata=true ACMAD turns CDI code 0 ("no drought") into nodata, which would
            # drop every unaffected area from the risk map instead of scoring it low.
            mask_nodata=False,
        )

    return HazardSelection(
        name="cdi",
        label=period.label,
        code_scheme=code_scheme,
        metadata={
            "source": f"ACMAD {args.cdi_product}",
            "requested_date": requested,
            "period_used": period,
            "period_requested": resolved.requested,
            "fallback": resolved.fallback,
            "lag_dekads": resolved.lag_dekads,
            "mask_nodata": False,
            "code_scheme": code_scheme,
        },
        fetch=fetch,
    )


def select_combined_hazard(args: argparse.Namespace) -> HazardSelection:
    """Choose the seasonal combined hazard.

    The season is picked from the periods ACMAD lists for the product in its
    dataset catalogue. An explicit --forecast-period skips the catalogue, and the
    download itself then confirms whether ACMAD has it.
    """

    explicit = args.forecast_period is not None
    if explicit:
        if args.forecast_year is None:
            raise SystemExit("--forecast-period needs --forecast-year")
        try:
            season = SeasonPeriod(args.forecast_year, args.forecast_period.upper())
        except ValueError as exc:
            raise SystemExit(str(exc))
        requested, fallback = season.start, False
    else:
        if not args.analysis_date:
            raise SystemExit("--hazard combined needs --analysis-date or --forecast-period with --forecast-year")
        requested = date.fromisoformat(args.analysis_date)
        try:
            published = combined_product_seasons(fetch_dataset_catalog(args.acmad_api_base_url), args.combined_product)
        except KeyError as exc:
            raise SystemExit(str(exc.args[0]))
        resolved = resolve_season(requested, published, strict=args.strict_dates)
        season, fallback = resolved.period, resolved.fallback
        if fallback:
            logger.warning("No published season covers %s; using %s.", requested.isoformat(), season.text)

    def fetch(output_dir: Path) -> Path:
        if args.combined_hazard_raster is not None:
            return args.combined_hazard_raster
        return download_combined_product(
            data_name=args.combined_product,
            forecast_period=season.label,
            year=season.year,
            output_path=output_dir / f"acmad_{args.combined_product}_{season.year}_{season.label}.tif",
            base_url=args.acmad_api_base_url,
        )

    return HazardSelection(
        name="combined_hazard",
        label=f"combined-{season.year}-{season.label}",
        code_scheme="combined-hazard",
        metadata={
            "source": "local file" if args.combined_hazard_raster else f"ACMAD {args.combined_product}",
            "requested_date": requested,
            "season_used": season.text,
            "fallback": fallback,
            "resolution_note": "1 degree grid; each cell is repeated on the exposure grid, not interpolated",
            "code_scheme": "combined-hazard",
        },
        fetch=fetch,
    )


def resolve_grid_template(args: argparse.Namespace) -> Path | None:
    if args.grid_template is not None:
        return args.grid_template
    if args.hazard == "combined":
        for candidate in (args.cultivated_raster, args.rangeland_raster, args.water_points_raster):
            if candidate is not None:
                return candidate
        logger.warning("No grid template or exposure raster given; the combined hazard stays on its native 1 degree grid.")
    return None


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()
    try:
        hazard = select_combined_hazard(args) if args.hazard == "combined" else select_cdi_hazard(args)
    except PeriodUnavailableError as exc:
        raise SystemExit(f"Cannot select a hazard period: {exc}")

    output_dir = args.output_dir or Path("outputs") / f"niger-risk-{hazard.label}"
    output_dir.mkdir(parents=True, exist_ok=True)

    boundary_path = download_niger_boundary(output_dir / "niger_boundary_admin0.geojson", args.acmad_geoserver_url)
    try:
        hazard_path = hazard.fetch(output_dir)
    except AcmadProductNotFound as exc:
        raise SystemExit(f"ACMAD has no data for this period: {exc}")

    grid_template = resolve_grid_template(args)
    # Masking needs real land cover: with the constant default scores every cell would pass anyway.
    has_exposure_rasters = any((args.cultivated_raster, args.rangeland_raster))
    mask_to_agropastoral = has_exposure_rasters and not args.no_agropastoral_mask
    outputs = build_agropastoral_risk_rasters(
        cdi_raster=hazard_path,
        boundary_geojson=boundary_path,
        output_dir=output_dir,
        cultivated_raster=args.cultivated_raster,
        rangeland_raster=args.rangeland_raster,
        water_points_raster=args.water_points_raster,
        exposure_defaults=ExposureDefaults(
            cultivated=args.default_cultivated_score,
            rangeland=args.default_rangeland_score,
            water_points=args.default_water_score,
        ),
        cdi_code_scheme=hazard.code_scheme,
        grid_template=grid_template,
        hazard_name=hazard.name,
        mask_to_agropastoral=mask_to_agropastoral,
    )

    metadata_path = write_run_metadata(
        output_dir,
        {
            "hazard": {"input": args.hazard, "file": hazard_path, "grid_template": grid_template, **hazard.metadata},
            "exposure": {
                "agropastoral_mask": mask_to_agropastoral,
                "cultivated": args.cultivated_raster or f"default score {args.default_cultivated_score}",
                "rangeland": args.rangeland_raster or f"default score {args.default_rangeland_score}",
                "water_points": args.water_points_raster or f"default score {args.default_water_score}",
            },
            "outputs": outputs,
        },
    )
    for name, path in outputs.items():
        logger.info("Risk output %s: %s", name, path)
    logger.info("Run metadata: %s", metadata_path)
    for value, label in risk_class_labels().items():
        logger.info("Risk class %d: %s", value, label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
