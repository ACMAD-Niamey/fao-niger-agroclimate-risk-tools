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
from .acmad_boundaries import (
    BoundaryRequest,
    boundary_request_from_country_info,
    build_wfs_getfeature_url,
)

__all__ = [
    "DEFAULT_EXPOSURE_WEIGHTS",
    "DEFAULT_HAZARD_WEIGHTS",
    "RiskInputs",
    "BoundaryRequest",
    "boundary_request_from_country_info",
    "build_wfs_getfeature_url",
    "calculate_exposure_score",
    "calculate_hazard_score",
    "calculate_risk_score",
    "classify_risk",
    "score_cdi",
    "score_indicator",
]
