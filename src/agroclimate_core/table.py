"""CSV helpers for testing and non-QGIS batch scoring."""

from __future__ import annotations

import csv
from pathlib import Path

from .risk import RiskInputs, calculate_record


INPUT_COLUMNS = {
    "cdi",
    "cultivated_exposure",
    "rangeland_exposure",
    "water_point_exposure",
}

OPTIONAL_COLUMNS = {
    "fapar_anomaly",
    "soil_moisture_anomaly",
    "vulnerability",
}

OUTPUT_COLUMNS = [
    "hazard_score",
    "exposure_score",
    "risk_score",
    "risk_class",
]


def score_csv(input_path: str | Path, output_path: str | Path) -> None:
    """Score a CSV table and write the original fields plus risk outputs."""

    input_path = Path(input_path)
    output_path = Path(output_path)

    with input_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        missing = sorted(INPUT_COLUMNS - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"Missing required input columns: {', '.join(missing)}")

        fieldnames = list(reader.fieldnames or [])
        for column in OUTPUT_COLUMNS:
            if column not in fieldnames:
                fieldnames.append(column)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                result = calculate_record(
                    RiskInputs(
                        cdi=row.get("cdi"),
                        fapar_anomaly=row.get("fapar_anomaly"),
                        soil_moisture_anomaly=row.get("soil_moisture_anomaly"),
                        cultivated_exposure=row.get("cultivated_exposure"),
                        rangeland_exposure=row.get("rangeland_exposure"),
                        water_point_exposure=row.get("water_point_exposure"),
                        vulnerability=row.get("vulnerability"),
                    )
                )
                row.update({key: str(value) for key, value in result.items()})
                writer.writerow(row)
