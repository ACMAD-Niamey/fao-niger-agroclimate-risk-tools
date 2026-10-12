# Implementation Notes

## Current Scope

The first implemented workflow supports the Agropastoral Drought Risk Map.

Version 1 started with the scoring logic and a QGIS-ready wrapper. The workflow is now moving toward a simpler end-to-end raster runner that produces GeoTIFF outputs first, then wraps the same logic in QGIS once the result is validated.

## Components

| Component | Path | Purpose |
| --- | --- | --- |
| Core scoring package | `src/agroclimate_core/` | Implements hazard, exposure, and risk scoring without QGIS dependencies. |
| ACMAD boundary helpers | `src/agroclimate_core/acmad_boundaries.py` | Builds WFS boundary requests from country-info metadata, including Niger admin-0 defaults for `data_api_adminlevelzero` and `country_code = 181`. |
| ACMAD download helpers | `src/agroclimate_core/acmad_download.py` | Downloads ACMAD raster products through the API `download_data` endpoint and handles immediate or asynchronous responses. |
| Raster pipeline | `src/agroclimate_core/raster_pipeline.py` | Clips CDI to Niger, aligns exposure rasters, calculates exposure and risk, and writes QGIS-ready GeoTIFF outputs. |
| CSV scoring script | `scripts/score_agropastoral_risk_csv.py` | Provides a lightweight way to test scoring on tabular/zonal data. |
| End-to-end raster runner | `scripts/build_agropastoral_risk_raster.py` | Command-line runner for creating the first risk raster before wrapping it in the QGIS plugin. |
| QGIS Processing wrapper | `qgis/processing/agropastoral_drought_risk.py` | Adds risk fields to a QGIS vector layer using the core scoring package. |
| QGIS boundary fetcher | `qgis/processing/fetch_acmad_boundary.py` | Fetches Niger boundary layers from ACMAD WFS for users without a local zonal layer. |
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

## Current Raster Workflow

The fastest path for testing is:

1. Download or reuse ACMAD CDI as a GeoTIFF.
2. Fetch the Niger admin-0 boundary from ACMAD WFS.
3. Clip CDI to Niger.
4. Use 0-3 exposure rasters where available, or use explicit default exposure scores for a first test.
5. Write GeoTIFF outputs that can be opened directly in QGIS.

Run from the repository root:

```bash
python3 scripts/build_agropastoral_risk_raster.py \
  --year 2026 \
  --month 5 \
  --dekad 21 \
  --output-dir outputs/niger-risk-2026-05-21
```

The runner writes:

```text
cdi_niger.tif
agropastoral_risk_score.tif
agropastoral_risk_class.tif
agropastoral_risk_stack.tif
```

For testing with an already downloaded CDI file:

```bash
python3 scripts/build_agropastoral_risk_raster.py \
  --year 2026 \
  --month 5 \
  --dekad 21 \
  --cdi-raster path/to/cdi.tif \
  --output-dir outputs/niger-risk-test
```

The ACMAD CDI GeoTIFF stores detailed CDI codes, not final `0-3` scores. The runner defaults to:

```text
0 = no drought -> 0
1-3 = watch -> 1
4-6 = warning -> 2
7-10 = alert -> 3
11-12 = partial recovery -> 1
13-14 = full recovery -> 0
```

If a local CDI raster is already on the `0-3` score scale, add:

```bash
--cdi-code-scheme score
```

If a local CDI raster uses classes `1-4`, add:

```bash
--cdi-code-scheme one-based
```

Exposure rasters are optional in the first runner, but when supplied they must already be on the same 0-3 score scale:

```bash
python3 scripts/build_agropastoral_risk_raster.py \
  --year 2026 \
  --month 5 \
  --dekad 21 \
  --cultivated-raster outputs/exposure/cultivated_exposure.tif \
  --rangeland-raster outputs/exposure/rangeland_exposure.tif \
  --water-points-raster outputs/exposure/water_point_exposure.tif \
  --output-dir outputs/niger-risk-2026-05-21
```

Until those exposure rasters are generated from GEE or local datasets, the script uses transparent default scores:

```text
cultivated exposure = 2
rangeland exposure = 2
water-point exposure = 1
```

These defaults are for testing the pipeline only. They should be replaced by exposure rasters before the product is used operationally.

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

1. Test live ACMAD CDI downloads for the target year, month, and dekad.
2. Generate or collect 0-3 exposure rasters for cultivated areas, rangelands, and water points.
3. Add GEE export helpers for land-cover-based exposure layers.
4. Add QGIS styles for CDI, hazard score, exposure score, and risk class.
5. Wrap the end-to-end raster runner in a QGIS Processing algorithm.
6. Add plugin UI controls once the script output is validated.
