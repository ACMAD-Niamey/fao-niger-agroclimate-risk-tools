# Implementation Notes

## Current Scope

The first implemented workflow supports the Agropastoral Drought Risk Map.

Version 1 focuses on the scoring logic and a QGIS-ready wrapper. It does not yet fetch ACMAD API products directly or perform raster/vector zonal preparation. Those will be added after the scoring workflow and expected input fields are validated.

## Components

| Component | Path | Purpose |
| --- | --- | --- |
| Core scoring package | `src/fao_niger_agroclimate/` | Implements hazard, exposure, and risk scoring without QGIS dependencies. |
| CSV scoring script | `scripts/score_agropastoral_risk_csv.py` | Provides a lightweight way to test scoring on tabular/zonal data. |
| QGIS Processing wrapper | `qgis/processing/agropastoral_drought_risk.py` | Adds risk fields to a QGIS vector layer using the core scoring package. |
| Tests | `tests/` | Validates the scoring logic with Python's standard `unittest` framework. |

## Expected Input Fields

The first QGIS Processing wrapper expects a zonal vector layer with these fields:

| Field | Required | Example values |
| --- | --- | --- |
| CDI | Yes | `no drought`, `watch`, `warning`, `alert`, or `0`-`3` |
| fAPAR anomaly | No | `normal`, `mild`, `moderate`, `severe`, or `0`-`3` |
| soil moisture anomaly | No | `normal`, `mild`, `moderate`, `severe`, or `0`-`3` |
| cultivated exposure | Yes | `0`-`3` |
| rangeland exposure | Yes | `0`-`3` |
| water-point exposure | Yes | `0`-`3` |
| vulnerability | No | `0`-`3` |

## Output Fields

The scoring workflow adds:

| Field | Description |
| --- | --- |
| `hazard_score` | CDI-only or composite ACMAD hazard score. |
| `exposure_score` | Weighted agropastoral exposure score. |
| `risk_score` | Final risk score. |
| `risk_class` | `low`, `moderate`, `high`, or `very high`. |

## Formulas

Hazard score, CDI-only:

```text
Hazard Score = CDI class score
```

Hazard score, composite where fAPAR and soil moisture anomaly classes are available:

```text
Hazard Score = 0.60 CDI + 0.20 fAPAR anomaly + 0.20 soil moisture anomaly
```

Exposure score:

```text
Exposure Score = 0.45 cultivated exposure + 0.35 rangeland exposure + 0.20 water-point exposure
```

Risk score where vulnerability is available:

```text
Risk Score = 0.50H + 0.30E + 0.20V
```

Risk score fallback where vulnerability is unavailable:

```text
Risk Score = 0.60H + 0.40E
```

## Test Command

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Next Implementation Tasks

1. Confirm exact ACMAD API response formats for CDI, fAPAR anomaly, and soil moisture anomaly.
2. Add ACMAD API client and local cache.
3. Add zonal preparation scripts to combine ACMAD indicator layers with admin, FAO intervention, cultivated, rangeland, and water-point exposure layers.
4. Add QGIS styles for CDI, hazard score, exposure score, and risk class.
5. Validate the first output against sample Niger data.
6. Wrap the Processing algorithm in a plugin UI after the workflow stabilizes.
