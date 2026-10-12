"""QGIS Processing algorithms and provider."""

from .agropastoral_drought_risk import AgropastoralDroughtRiskAlgorithm
from .fetch_acmad_boundary import FetchAcmadBoundaryAlgorithm

__all__ = ["AgropastoralDroughtRiskAlgorithm", "FetchAcmadBoundaryAlgorithm"]
