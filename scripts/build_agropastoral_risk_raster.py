#!/usr/bin/env python3
"""Build an end-to-end agropastoral drought risk raster for QGIS.

This is a thin command-line shell. The workflow itself lives in
``agroclimate_core.workflow`` and is shared with the QGIS plugin.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agroclimate_core.acmad_download import AcmadProductNotFound, DEFAULT_ACMAD_API_BASE_URL
from agroclimate_core.hazard_selection import ConfigError, dekad_from_day
from agroclimate_core.periods import PeriodUnavailableError
from agroclimate_core.raster_pipeline import ExposureDefaults, risk_class_labels
from agroclimate_core.workflow import DEFAULT_GEOSERVER_URL, RunConfig, run_risk_workflow

logger = logging.getLogger("build_agropastoral_risk_raster")


def resolve_analysis_period(args: argparse.Namespace) -> tuple[int, int, int, str]:
    """Year, month, dekad and label for a CDI period (kept for the existing tests and callers)."""

    if args.analysis_date:
        analysis_date = date.fromisoformat(args.analysis_date)
        return analysis_date.year, analysis_date.month, dekad_from_day(analysis_date.day), analysis_date.isoformat()
    if args.year is None or args.month is None:
        raise SystemExit("Either --analysis-date or both --year and --month are required.")
    return args.year, args.month, args.dekad, f"{args.year}-{args.month:02d}-{args.dekad:02d}"


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
    parser.add_argument("--acmad-geoserver-url", default=DEFAULT_GEOSERVER_URL, help="ACMAD GeoServer base URL.")
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


def config_from_args(args: argparse.Namespace) -> RunConfig:
    return RunConfig(
        output_dir=args.output_dir,
        analysis_date=date.fromisoformat(args.analysis_date) if args.analysis_date else None,
        year=args.year,
        month=args.month,
        dekad=args.dekad,
        hazard=args.hazard,
        cdi_product=args.cdi_product,
        combined_product=args.combined_product,
        forecast_period=args.forecast_period,
        forecast_year=args.forecast_year,
        max_fallback_dekads=args.max_fallback_dekads,
        strict_dates=args.strict_dates,
        cdi_code_scheme="one-based" if args.one_based_cdi else args.cdi_code_scheme,
        cdi_raster=args.cdi_raster,
        combined_hazard_raster=args.combined_hazard_raster,
        cultivated_raster=args.cultivated_raster,
        rangeland_raster=args.rangeland_raster,
        water_points_raster=args.water_points_raster,
        exposure_defaults=ExposureDefaults(
            cultivated=args.default_cultivated_score,
            rangeland=args.default_rangeland_score,
            water_points=args.default_water_score,
        ),
        mask_to_agropastoral=False if args.no_agropastoral_mask else None,
        grid_template=args.grid_template,
        acmad_api_base_url=args.acmad_api_base_url,
        acmad_geoserver_url=args.acmad_geoserver_url,
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()
    try:
        result = run_risk_workflow(config_from_args(args))
    except (ConfigError, PeriodUnavailableError) as exc:
        raise SystemExit(f"Cannot select a hazard period: {exc}")
    except AcmadProductNotFound as exc:
        raise SystemExit(f"ACMAD has no data for this period: {exc}")

    for name, path in result.outputs.items():
        logger.info("Risk output %s: %s", name, path)
    logger.info("Run metadata: %s", result.metadata_path)
    for value, label in risk_class_labels().items():
        logger.info("Risk class %d: %s", value, label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
