"""Core utilities for FAO Niger agroclimatic risk products."""

from .risk import (
    DEFAULT_EXPOSURE_WEIGHTS,
    DEFAULT_HAZARD_WEIGHTS,
    RiskInputs,
    calculate_exposure_score,
    calculate_hazard_score,
    calculate_risk_score,
    classify_risk,
    score_cdi,
    score_indicator,
)

__all__ = [
    "DEFAULT_EXPOSURE_WEIGHTS",
    "DEFAULT_HAZARD_WEIGHTS",
    "RiskInputs",
    "calculate_exposure_score",
    "calculate_hazard_score",
    "calculate_risk_score",
    "classify_risk",
    "score_cdi",
    "score_indicator",
]
