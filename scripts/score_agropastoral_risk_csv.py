#!/usr/bin/env python3
"""Score agropastoral drought risk for a CSV table.

This command is a lightweight test harness for the risk formula. The QGIS
Processing script and future plugin should use the same core module.
"""

from __future__ import annotations

import argparse

from agroclimate_core.table import score_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Score agropastoral drought risk from a CSV table.")
    parser.add_argument("input_csv", help="Input CSV with CDI and exposure columns.")
    parser.add_argument("output_csv", help="Output CSV path.")
    args = parser.parse_args()
    score_csv(args.input_csv, args.output_csv)


if __name__ == "__main__":
    main()
