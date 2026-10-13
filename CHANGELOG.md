# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/). Versions follow [Semantic Versioning](https://semver.org/); while the thresholds are placeholders the project stays below 1.0.

## [Unreleased]

## [0.3.2] - 2026-10-13

The first release. It is the QGIS plugin, the command-line script and the shared code behind them. Versions 0.2.0 to 0.3.1 were development builds. Its thresholds and class mapping are provisional, so treat the maps as a screening tool; see [Known problems](#known-problems).

### Added

- **A QGIS panel** (Run, Results and Settings tabs) that builds the agropastoral drought risk map and adds the styled layers to the map. It runs in the background with progress and cancel.
  - A **Period** drop-down lists the CDI dekads and seasonal outlooks ACMAD has actually published, latest first, with the latest selected by default, a Refresh button, and an "Other date" entry for typing a date (also the fallback when offline).
  - The **Results** tab shows class areas and shares as a chart and table, the mean score, and a note when the period shown is older than requested. A summary by region works for any polygon layer you choose.
  - When no exposure rasters exist, it offers **Prepare exposure, then run** and carries on by itself once the exposure is ready.
  - Four ways to open it: the first entry of the *FAO Niger Agroclimate* group in the Processing Toolbox, a one-time message when the plugin loads, the toolbar icon, and the Plugins menu. A step that fails while loading is reported in the message bar and the log.
  - An optional language model description of the results, off by default. It needs a service address, key and model, asks before sending anything, sends only an allow-listed set of summary figures, and marks every reply as a draft for expert review.
- **`agroclimate_core.workflow`** (`RunConfig`, `run_risk_workflow`) and its supporting modules: the one end-to-end run that the script and the plugin both call.
- **Date selection from ACMAD's catalogue.** The CDI dekad and the seasonal period are resolved from what is published. The latest period within `--max-fallback-dekads` (default 3) is used when the requested one is missing; `--strict-dates` refuses instead. Every run writes `run_metadata.json` with the requested date, the period used, any fallback and its lag, the boundary source and the exposure inputs.
- **The seasonal combined hazard** as a second hazard input (`--hazard combined`), resampled onto the exposure grid, with its own QGIS style.
- **Land cover exposure** from ESA WorldCover, aggregated to the hazard grid as cropland and rangeland fractions and binned into 0-3 scores (`scripts/prepare_exposure_rasters.py`). Only tiles and cells that touch the boundary are fetched, in parallel, and cached.
- An option to **score only cells with cropland or rangeland** exposure (on by default when exposure rasters are given).
- **Summaries by administrative unit** (`scripts/summarize_by_admin.py`): class shares, area-weighted mean score, worst class, and cropland and rangeland hectares in high-risk cells.
- **MinIO upload** of prepared layers (`scripts/upload_exposure_to_minio.py`). Credentials come from `.env`; `.env.example` lists the names.
- Documents: [using the panel](docs/using-the-panel.md), [reading the maps](docs/reading-the-maps.md), [data sources](docs/data-sources.md), the [decision log](docs/decisions.md) and [how to release](docs/releasing.md).
- Tests that build the real plugin zip, load it into a headless QGIS and drive the panel.

### Changed

- The CDI is downloaded unmasked (`mask_nodata=false`). Before, "no drought" areas were dropped from the map instead of scored low.
- QGIS styles use a sequential, colour-blind-safe ramp, and risk class labels state the real score breaks.
- The older Processing algorithm is renamed "Score a zonal layer (vector, advanced)"; its help says it builds no raster and points to the panel.
- `scripts/build_agropastoral_risk_raster.py` is a thin shell over the shared workflow; its options and results are unchanged.
- The code supports Python 3.9, the version QGIS 3.28 ships (it was declared 3.10 before).
- The plugin builder includes every module in `qgis/plugin/`; it used to copy four named files and would have dropped new ones.
- The menu action for the CDI style is labelled as for the 0-3 hazard score only, because it misrenders the raw CDI codes.
- The docs state the "consume, don't compute" principle and describe the work against the four ToR deliverables.

### Fixed

- Supplying an exposure raster crashed the pipeline (it looked for a file name that was never written).
- Exposure rasters ignored their own nodata value and were resampled by nearest neighbour; they now keep their nodata and are averaged.
- The stack's `risk_class` band showed 255 instead of nodata where cells were invalid.
- Closing or disabling the plugin while a background request was still running could crash QGIS. Outstanding tasks are now cancelled and late results ignored.

### Known problems

- **Thresholds, class mapping and weights are provisional.** The exposure cut-offs, the combined-hazard binning and the risk weights are placeholders until FAO and ACMAD review them. Water-point exposure is a constant and vulnerability is not applied to the raster.
- **The CDI code bins differ from ACMAD's WMS legend** at codes 4 and 7 (the tools use 1-3 watch, 4-6 warning, 7-10 alert; the legend uses 1-4, 5-7, 7-10), and the legend does not cover recovery codes 11 to 14. Open question; see the [decision log](docs/decisions.md#open-questions). The legend does confirm that code 0 means no drought.
- **The raw ACMAD CDI for 2026-09-11 changes abruptly along a straight north-south line near 12.1 degrees east.** It is in ACMAD's file, not the tools; to confirm with ACMAD. See [data sources](docs/data-sources.md).
- The plugin has been used in QGIS 3.28 on macOS by the project developer, who reported it working well. It has not been tried on Windows or Linux, or against a real language model service.
- The default admin level 1 layer in the QGIS boundary fetch tool does not exist on ACMAD's GeoServer, so that fetch fails. Use the OCHA boundaries; see [data sources](docs/data-sources.md).

[Unreleased]: https://github.com/ACMAD-Niamey/fao-niger-agroclimate-risk-tools/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/ACMAD-Niamey/fao-niger-agroclimate-risk-tools/releases/tag/v0.3.2
