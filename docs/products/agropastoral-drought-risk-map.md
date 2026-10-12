# Agropastoral Drought Risk Map

## Purpose

The Agropastoral Drought Risk Map is the first product selected for implementation. It identifies areas where ACMAD drought indicators overlap with agricultural and pastoral exposure layers in FAO Niger areas of interest.

The product should answer:

- where drought conditions are currently affecting or threatening agropastoral systems
- which administrative units or FAO intervention zones have the highest combined risk
- which exposed assets are affected, including cultivated areas, rangelands, and water points
- where monitoring, advisory messaging, or anticipatory action discussions should be prioritized

## Initial Scope

The initial implementation will use ACMAD drought indicators only. It will not calculate NDVI anomaly or other custom GEE indicators in the first version.

Initial ACMAD indicators:

- Combined Drought Indicator
- fAPAR anomaly
- soil moisture anomaly

Future versions may add GEE-derived indicators where they provide value beyond ACMAD products, such as NDVI anomaly, surface water change, heat stress, land cover refinement, or start-of-season metrics.

## Primary Users

- FAO Niger technical staff
- national meteorological and agricultural counterparts
- food security and early warning partners
- field teams supporting agricultural and pastoral advisory work

## Input Datasets

### ACMAD Inputs

| Input | Role |
| --- | --- |
| Combined Drought Indicator | Primary drought hazard classification. |
| fAPAR anomaly | Vegetation stress evidence, especially relevant for crop and rangeland conditions. |
| Soil moisture anomaly | Agricultural moisture stress evidence. |

Optional ACMAD inputs, if available:

- drought hazard forecast
- rainfall anomaly
- seasonal forecast

### Local and Partner Inputs

| Input | Role |
| --- | --- |
| Niger administrative boundaries | Reporting and aggregation. |
| FAO intervention zones | Operational prioritization. |
| Cultivated areas | Crop exposure. |
| Rangelands or pastoral zones | Pastoral exposure. |
| Water points | Water-access exposure and pastoral relevance. |
| Vulnerability or food security layer | Optional risk modifier. |
| Livelihood zones | Optional interpretation layer. |

## Processing Logic

The product uses a transparent risk framing:

```text
Risk = Hazard x Exposure x Vulnerability
```

For version 1, hazard is derived from ACMAD indicators, exposure is derived from local agropastoral layers, and vulnerability is optional.

## Hazard Score

The Combined Drought Indicator is the primary hazard layer.

Suggested CDI scoring:

```text
0 = no drought
1 = watch
2 = warning
3 = alert
```

fAPAR anomaly and soil moisture anomaly should be used as supporting evidence. They can either be retained as separate diagnostic layers or included in a composite hazard score after validation.

Suggested first composite hazard formula:

```text
Hazard Score = 0.60 CDI + 0.20 fAPAR anomaly class + 0.20 soil moisture anomaly class
```

If fAPAR or soil moisture anomaly classifications are not directly comparable with CDI classes, the first version should keep them as diagnostic layers and use CDI alone for the hazard score:

```text
Hazard Score = CDI class score
```

## Exposure Score

Exposure combines cultivated areas, rangelands, and water points.

Suggested formula:

```text
Exposure Score = 0.45 cultivated exposure + 0.35 rangeland exposure + 0.20 water-point exposure
```

Exposure classes:

```text
0 = no relevant exposure
1 = low exposure
2 = moderate exposure
3 = high exposure
```

## Risk Formula

If a vulnerability layer is available:

```text
Risk Score = 0.50H + 0.30E + 0.20V
```

Where:

- H = hazard score
- E = exposure score
- V = vulnerability score

If vulnerability is not available:

```text
Risk Score = 0.60H + 0.40E
```

Risk classes:

```text
0.0-0.9 = low risk
1.0-1.6 = moderate risk
1.7-2.3 = high risk
2.4-3.0 = very high risk
```

## Outputs

The QGIS Processing script should generate:

- agropastoral drought risk layer
- CDI layer styled by drought class
- fAPAR anomaly diagnostic layer
- soil moisture anomaly diagnostic layer
- administrative risk summary table
- FAO intervention-zone summary table, where relevant
- water points in high-risk zones table
- print-ready map export
- metadata file documenting inputs, dates, formulas, and thresholds

## Implementation Location

The first implementation should run as a QGIS Processing script.

The script should be written so it can later be wrapped by a QGIS plugin. The plugin should not duplicate processing logic; it should provide a simple user interface over the same backend algorithm.

Initial QGIS Processing parameters:

```text
reporting_period
admin_boundary_layer
fao_intervention_layer
cultivated_area_layer
rangeland_layer
water_points_layer
vulnerability_layer, optional
acmad_cdi_source
acmad_fapar_source
acmad_soil_moisture_source
use_acmad_api
use_cached_data
output_folder
```

## Plugin Wrapper Direction

The future plugin should expose a simple interface:

```text
Product: Agropastoral Drought Risk Map
Period: dekad/month/season
Hazard source: fetch from ACMAD API or use cached files
Exposure layers: cultivated areas, rangelands, water points
Reporting geography: admin unit or FAO intervention zone
Generate outputs
Export package
```

## Quality Control

Before use, each output should be checked for:

- correct reporting period
- successful ACMAD product download or cache selection
- correct spatial alignment between hazard and exposure layers
- valid risk-score range
- complete administrative summaries
- readable map symbology
- metadata completeness

## Known Limitations

- The first version does not calculate NDVI anomaly or other GEE-derived indicators.
- The risk score is a screening tool and should be validated with local experts.
- Vulnerability data may be incomplete or unavailable.
- ACMAD indicator classes and anomaly classes may require harmonization before they are combined into a composite hazard score.

## Handover Notes

The first operational version should prioritize transparency and repeatability. CDI should remain the main hazard indicator until fAPAR anomaly and soil moisture anomaly scoring is validated with ACMAD and FAO Niger counterparts.

