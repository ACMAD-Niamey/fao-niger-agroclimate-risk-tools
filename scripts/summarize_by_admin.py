#!/usr/bin/env python3
"""Summarise a risk map by administrative unit (for example admin level 1).

Writes admin_risk_summary.csv and admin_risk_summary.geojson next to the risk
rasters. Any admin GeoJSON works as long as you say which fields hold the name
(and optionally a code).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agroclimate_core.admin_summary import summarize_by_admin, write_summary_csv, write_summary_geojson

logger = logging.getLogger("summarize_by_admin")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--risk-dir", type=Path, required=True, help="Folder written by build_agropastoral_risk_raster.py.")
    parser.add_argument("--admin-geojson", type=Path, required=True, help="Admin boundaries, for example admin level 1.")
    parser.add_argument("--name-field", required=True, help="Property holding the unit name.")
    parser.add_argument("--code-field", help="Property holding a unit code (optional).")
    parser.add_argument(
        "--exposure-dir",
        type=Path,
        default=Path("outputs/exposure"),
        help="Folder with cultivated_fraction.tif and rangeland_fraction.tif; adds exposed hectares when present.",
    )
    parser.add_argument("--output-dir", type=Path, help="Defaults to --risk-dir.")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()
    output_dir = args.output_dir or args.risk_dir

    def optional(name: str) -> Path | None:
        path = args.exposure_dir / name
        return path if path.exists() else None

    rows = summarize_by_admin(
        args.risk_dir / "agropastoral_risk_class.tif",
        args.risk_dir / "agropastoral_risk_score.tif",
        args.admin_geojson,
        name_field=args.name_field,
        code_field=args.code_field,
        cultivated_fraction_path=optional("cultivated_fraction.tif"),
        rangeland_fraction_path=optional("rangeland_fraction.tif"),
    )
    csv_path = write_summary_csv(rows, output_dir / "admin_risk_summary.csv")
    geojson_path = write_summary_geojson(
        args.admin_geojson, rows, output_dir / "admin_risk_summary.geojson", key_field=args.name_field
    )
    logger.info("Wrote %s and %s", csv_path, geojson_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
