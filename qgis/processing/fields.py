"""Shared field names and field helpers for QGIS Processing algorithms."""

from __future__ import annotations


OUTPUT_FIELD_DEFINITIONS = (
    ("hazard_score", "double"),
    ("exposure_score", "double"),
    ("risk_score", "double"),
    ("risk_class", "string"),
)


def output_field_names() -> list[str]:
    """Return output field names added by the risk scoring algorithm."""

    return [name for name, _field_type in OUTPUT_FIELD_DEFINITIONS]
