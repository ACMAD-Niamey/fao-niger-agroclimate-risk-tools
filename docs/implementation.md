# Implementation Notes

## Current Scope

The first implemented workflow supports the Agropastoral Drought Risk Map.

Version 1 focuses on the scoring logic and a QGIS-ready wrapper. It does not yet fetch ACMAD API products directly or perform raster/vector zonal preparation. Those will be added after the scoring workflow and expected input fields are validated.

## Components

| Component | Path | Purpose |
| --- | --- | --- |
| Core scoring package | `src/agroclimate_core/` | Implements hazard, exposure, and risk scoring without QGIS dependencies. |
| ACMAD boundary helpers | `src/agroclimate_core/acmad_boundaries.py` | Builds WFS boundary requests from country-info metadata, including Niger admin-0 defaults for `data_api_adminlevelzero` and `country_code = 181`. |
| CSV scoring script | `scripts/score_agropastoral_risk_csv.py` | Provides a lightweight way to test scoring on tabular/zonal data. |
| QGIS Processing wrapper | `qgis/processing/agropastoral_drought_risk.py` | Adds risk fields to a QGIS vector layer using the core scoring package. |
| QGIS Processing provider | `qgis/processing/provider.py` | Registers the risk algorithm in the QGIS Processing registry. |
| QGIS plugin scaffold | `qgis/plugin/` | Minimal plugin shell for registering the Processing provider. |
| QGIS plugin builder | `scripts/build_qgis_plugin.py` | Builds an installable plugin zip for ordinary QGIS users. |
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

Syntax check without writing bytecode:

```bash
python3 -c "import ast, pathlib; files=[p for root in ['qgis','src','scripts','tests'] for p in pathlib.Path(root).rglob('*.py')]; [ast.parse(p.read_text(), filename=str(p)) for p in files]; print(f'AST syntax OK: {len(files)} files')"
```

## Next Implementation Tasks

1. Confirm exact ACMAD API response formats for CDI, fAPAR anomaly, and soil moisture anomaly.
2. Confirm exact ACMAD country-info API fields for WFS URL, boundary layer/type names, and country-code filters.
3. Add ACMAD API client and local cache.
4. Add WFS boundary fetch support for users who do not want to provide a local vector zonal layer.
5. Add zonal preparation scripts to combine ACMAD indicator layers with admin, FAO intervention, cultivated, rangeland, and water-point exposure layers.
6. Add QGIS styles for CDI, hazard score, exposure score, and risk class.
7. Validate the first output against sample Niger data.
8. Wrap the Processing algorithm in a plugin UI after the workflow stabilizes.
