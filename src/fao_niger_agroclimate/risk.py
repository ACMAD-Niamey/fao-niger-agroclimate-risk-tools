"""Risk scoring logic for the first agropastoral drought risk product.

The functions in this module deliberately avoid QGIS dependencies. QGIS
Processing scripts and future plugin UI code should call these functions rather
than reimplementing the scoring logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Mapping


DEFAULT_HAZARD_WEIGHTS = {
    "cdi": 0.60,
    "fapar_anomaly": 0.20,
    "soil_moisture_anomaly": 0.20,
}

DEFAULT_EXPOSURE_WEIGHTS = {
    "cultivated": 0.45,
    "rangeland": 0.35,
    "water_points": 0.20,
}

CDI_SCORE_MAP = {
    "no drought": 0.0,
    "none": 0.0,
    "normal": 0.0,
    "watch": 1.0,
    "warning": 2.0,
    "alert": 3.0,
}

ANOMALY_SCORE_MAP = {
    "none": 0.0,
    "normal": 0.0,
    "near normal": 0.0,
    "mild": 1.0,
    "moderate": 2.0,
    "severe": 3.0,
    "extreme": 3.0,
    "negative": 2.0,
    "strong negative": 3.0,
}


@dataclass(frozen=True)
class RiskInputs:
    """Inputs required to compute an agropastoral drought risk score."""

    cdi: object
    cultivated_exposure: object
    rangeland_exposure: object
    water_point_exposure: object
    fapar_anomaly: object | None = None
    soil_moisture_anomaly: object | None = None
    vulnerability: object | None = None


def _clean_label(value: object) -> str:
    return str(value).strip().lower().replace("_", " ").replace("-", " ")


def _score_from_map(value: object, score_map: Mapping[str, float], field_name: str) -> float:
    if value is None or value == "":
        raise ValueError(f"{field_name} is required")

    if isinstance(value, Real):
        return clamp_score(float(value), field_name)

    label = _clean_label(value)
    if label in score_map:
        return score_map[label]

    try:
        return clamp_score(float(label), field_name)
    except ValueError as exc:
        valid = ", ".join(sorted(score_map))
        raise ValueError(f"Unsupported {field_name} value {value!r}. Expected 0-3 or one of: {valid}") from exc


def clamp_score(value: float, field_name: str = "score") -> float:
    """Validate a score on the 0-3 scale."""

    if value < 0 or value > 3:
        raise ValueError(f"{field_name} must be between 0 and 3; got {value}")
    return value


def score_cdi(value: object) -> float:
    """Convert an ACMAD CDI class or numeric score to the 0-3 hazard scale."""

    return _score_from_map(value, CDI_SCORE_MAP, "CDI")


def score_indicator(value: object | None, *, field_name: str) -> float | None:
    """Convert an anomaly or exposure value to the 0-3 scale.

    Missing values are returned as ``None`` so callers can decide whether to
    calculate a composite score or fall back to CDI-only logic.
    """

    if value is None or value == "":
        return None
    return _score_from_map(value, ANOMALY_SCORE_MAP, field_name)


def _weighted_average(scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total_weight = sum(weights[name] for name in scores)
    if total_weight <= 0:
        raise ValueError("At least one weighted score is required")
    return sum(scores[name] * weights[name] for name in scores) / total_weight


def calculate_hazard_score(
    cdi: object,
    fapar_anomaly: object | None = None,
    soil_moisture_anomaly: object | None = None,
    *,
    weights: Mapping[str, float] = DEFAULT_HAZARD_WEIGHTS,
) -> float:
    """Calculate hazard score from CDI and optional ACMAD anomaly products.

    If fAPAR and soil moisture anomaly are not supplied, the function uses CDI
    alone. If one supporting indicator is supplied, weights are renormalized
    over the available indicators.
    """

    scores = {"cdi": score_cdi(cdi)}
    fapar_score = score_indicator(fapar_anomaly, field_name="fAPAR anomaly")
    soil_score = score_indicator(soil_moisture_anomaly, field_name="soil moisture anomaly")

    if fapar_score is not None:
        scores["fapar_anomaly"] = fapar_score
    if soil_score is not None:
        scores["soil_moisture_anomaly"] = soil_score

    return round(_weighted_average(scores, weights), 3)


def calculate_exposure_score(
    cultivated_exposure: object,
    rangeland_exposure: object,
    water_point_exposure: object,
    *,
    weights: Mapping[str, float] = DEFAULT_EXPOSURE_WEIGHTS,
) -> float:
    """Calculate agropastoral exposure score from component scores."""

    scores = {
        "cultivated": _score_from_map(cultivated_exposure, ANOMALY_SCORE_MAP, "cultivated exposure"),
        "rangeland": _score_from_map(rangeland_exposure, ANOMALY_SCORE_MAP, "rangeland exposure"),
        "water_points": _score_from_map(water_point_exposure, ANOMALY_SCORE_MAP, "water-point exposure"),
    }
    return round(_weighted_average(scores, weights), 3)


def calculate_risk_score(hazard_score: float, exposure_score: float, vulnerability: object | None = None) -> float:
    """Calculate final risk score.

    Uses the documented 0.50H + 0.30E + 0.20V formula when vulnerability is
    available, otherwise uses the documented 0.60H + 0.40E fallback.
    """

    hazard = clamp_score(float(hazard_score), "hazard score")
    exposure = clamp_score(float(exposure_score), "exposure score")
    vulnerability_score = score_indicator(vulnerability, field_name="vulnerability")

    if vulnerability_score is None:
        return round(0.60 * hazard + 0.40 * exposure, 3)
    return round(0.50 * hazard + 0.30 * exposure + 0.20 * vulnerability_score, 3)


def classify_risk(risk_score: float) -> str:
    """Classify a 0-3 risk score into the documented risk classes."""

    score = clamp_score(float(risk_score), "risk score")
    if score < 1.0:
        return "low"
    if score < 1.7:
        return "moderate"
    if score < 2.4:
        return "high"
    return "very high"


def calculate_record(inputs: RiskInputs) -> dict[str, float | str]:
    """Calculate hazard, exposure, risk score, and class for one record."""

    hazard_score = calculate_hazard_score(
        inputs.cdi,
        inputs.fapar_anomaly,
        inputs.soil_moisture_anomaly,
    )
    exposure_score = calculate_exposure_score(
        inputs.cultivated_exposure,
        inputs.rangeland_exposure,
        inputs.water_point_exposure,
    )
    risk_score = calculate_risk_score(hazard_score, exposure_score, inputs.vulnerability)
    return {
        "hazard_score": hazard_score,
        "exposure_score": exposure_score,
        "risk_score": risk_score,
        "risk_class": classify_risk(risk_score),
    }
