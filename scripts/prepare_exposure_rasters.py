#!/usr/bin/env python3
"""Prepare 0-3 cultivated and rangeland exposure rasters on a hazard grid.

Reads ESA WorldCover straight from the open AWS bucket (no login, no GEE) and
aggregates it to the grid of a template raster, normally a clipped CDI file
such as outputs/niger-risk-<date>/cdi_niger.tif. Exposure is static, so run
this once and reuse the results for every dekad.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agroclimate_core.exposure import ExposureThresholds, prepare_exposure_rasters
from agroclimate_core.exposure_workflow import ExposureConfig, run_exposure_preparation

logger = logging.getLogger("prepare_exposure_rasters")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=("worldcover", "acmad"),
        default="worldcover",
        help=(
            "'worldcover' builds the rasters from ESA WorldCover (needs --template; minutes, hundreds of MB). "
            "'acmad' downloads the four small rasters ACMAD has already prepared (seconds)."
        ),
    )
    parser.add_argument("--template", type=Path, help="Raster whose grid the exposure layers must match.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/exposure"), help="Where to write the rasters.")
    parser.add_argument(
        "--landcover",
        type=Path,
        nargs="+",
        help="Local 8-bit land cover rasters (WorldCover legend). Defaults to the WorldCover tiles over the template.",
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        help="Boundary GeoJSON (for example niger_boundary_admin0.geojson). Only cells touching it are computed and downloaded.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("outputs/cache/worldcover"),
        help="Where downloaded land cover windows are kept and re-used. Pass an empty string to stream without saving.",
    )
    parser.add_argument("--workers", type=int, default=4, help="Parallel land cover downloads.")
    for group in ("cultivated", "rangeland"):
        defaults = ExposureThresholds()
        parser.add_argument(
            f"--{group}-thresholds",
            type=float,
            nargs=3,
            metavar=("LOW", "MODERATE", "HIGH"),
            default=[defaults.low, defaults.moderate, defaults.high],
            help=f"Cell fractions where the {group} score becomes 1, 2 and 3.",
        )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()
    if args.source == "acmad":
        outputs = run_exposure_preparation(ExposureConfig(output_dir=args.output_dir, source="acmad"))
        for name, path in outputs.items():
            logger.info("%s: %s", name, path)
        return 0
    if args.template is None:
        raise SystemExit("--template is required when building exposure from land cover (--source worldcover).")
    thresholds = {
        group: ExposureThresholds(*getattr(args, f"{group}_thresholds")) for group in ("cultivated", "rangeland")
    }
    outputs = prepare_exposure_rasters(
        template_path=args.template,
        output_dir=args.output_dir,
        source_paths=args.landcover,
        thresholds=thresholds,
        boundary_geojson=args.boundary,
        cache_dir=args.cache_dir if str(args.cache_dir) else None,
        workers=args.workers,
    )
    for name, path in outputs.items():
        logger.info("%s: %s", name, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
