# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/). The project has no tagged releases yet.

## [Unreleased]

### Added

- When no exposure rasters exist, the panel now offers **Prepare exposure, then run** (and *Run as a test anyway*, *Cancel*) as buttons, and continues the run by itself once the exposure is ready. A failed preparation does not start the run. Before, it asked a Yes/No question and left the user to find the right button. Plugin version 0.3.2.
- Easier ways to open the panel: the first entry of the *FAO Niger Agroclimate* group in the Processing Toolbox (*Agroclimate Risk panel*), and a one-time message when the plugin loads, with an "Open the risk panel" button. Plugin version 0.3.1.
- The panel's period drop-down: it lists the CDI dekads and seasonal outlooks ACMAD has actually published, latest first, with the latest selected by default, a Refresh button, and an "Other date" entry for typing a date (also the fallback when offline). It replaces the free date box and the separate season fields.
- A [walkthrough of the panel](docs/using-the-panel.md), and the boundary source is now recorded in `run_metadata.json`.
- A QGIS panel (plugin version 0.3.0, with the period drop-down; 0.2.0 had a free date box): choose current conditions or the seasonal outlook and a date, run in the background with progress and cancel, and have the styled results added to the map. The Results tab shows class areas and shares as a chart and table, and a summary by region for any polygon layer. A button opens the results folder. Exposure can be prepared from the panel.
- An optional language model description of the results, off by default: needs a service address, key and model, asks before sending anything, sends only an allow-listed set of summary figures and marks every reply as a draft for expert review.
- `agroclimate_core.workflow` (`RunConfig`, `run_risk_workflow`), `hazard_selection`, `exposure_workflow`, `grid`, `risk_statistics`, `llm` and `cancellation`: the shared code that the script and the plugin both call.
- Plugin tests that build the real zip, load it into a headless QGIS and drive the panel (146 tests under QGIS's Python).
- Land cover exposure preparation: ESA WorldCover is aggregated to the hazard grid as cropland and rangeland fractions and binned into 0-3 scores (`scripts/prepare_exposure_rasters.py`). Only tiles and cells that touch the boundary are fetched, in parallel, and cached in `outputs/cache/worldcover`.
- MinIO upload of prepared layers (`scripts/upload_exposure_to_minio.py`, `agroclimate_core.storage`). Credentials come from `.env`; `.env.example` lists the names.
- Date selection from ACMAD's catalogue: the CDI dekad and the seasonal period are resolved from what is published. The latest period within `--max-fallback-dekads` (default 3) is used when the requested one is missing; `--strict-dates` refuses instead.
- `run_metadata.json` beside every run, recording the requested date, the period actually used, any fallback and its lag, and the exposure inputs.
- Combined monitoring and forecast hazard as a second hazard input (`--hazard combined`), resampled onto the exposure grid.
- Option to score only cells with cropland or rangeland exposure (on by default when exposure rasters are given; `--no-agropastoral-mask` turns it off).
- Summaries by administrative unit (`scripts/summarize_by_admin.py`): risk class shares, area-weighted mean score, worst class, and cropland and rangeland hectares in high-risk cells.
- QGIS style for the combined hazard and a plugin menu action for it.
- Documents: [data sources](docs/data-sources.md), [decision log](docs/decisions.md) and a [guide to reading the maps](docs/reading-the-maps.md).

### Changed

- The older Processing algorithm is renamed "Score a zonal layer (vector, advanced)" and its help now says it builds no raster and points to the panel. It was easy to mistake for the map tool.
- `scripts/build_agropastoral_risk_raster.py` is now a thin shell over the shared workflow; its options and results are unchanged.
- The code supports Python 3.9, the version QGIS 3.28 ships (it was declared 3.10 before).
- The plugin builder includes every module in `qgis/plugin/`; it used to copy four named files and would have dropped new ones.
- The menu action for the CDI style is now labelled as for the 0-3 hazard score only, because it misrenders the raw CDI codes.
- The CDI is downloaded unmasked (`mask_nodata=false`). Before, "no drought" areas were dropped from the map instead of scored low.
- QGIS styles use a sequential, colour-blind-safe ramp. Risk class labels now state the real score breaks.
- The docs now state the "consume, don't compute" principle and describe the prototype against the four ToR deliverables.

### Fixed

- The exposure status line under the folder box was clipped in a real QGIS window. It is now a short sentence, with the detail in a tooltip.
- The panel was hard to find: the Processing Toolbox, where most users look first, listed only the older vector tools. A step that fails while the plugin loads (menu, toolbar, styles, provider) is now reported in the message bar and the log, instead of silently leaving the panel out.
- Closing or disabling the plugin while a background request was still running could crash QGIS, because the finished task called into the deleted panel. The controller now cancels outstanding tasks and ignores late results.
- Supplying an exposure raster crashed the pipeline (it looked for a file name that was never written).
- Exposure rasters ignored their own nodata value and were resampled by nearest neighbour; they now keep their nodata and are averaged.
- The stack's `risk_class` band showed 255 instead of nodata where cells were invalid.

### Known problems

- The tools' CDI code bins (1-3 watch, 4-6 warning, 7-10 alert) differ from ACMAD's WMS legend (1-4 watch, 5-7 warning, 7-10 alert) at codes 4 and 7, and the legend does not cover recovery codes 11 to 14. Open question; see [decision log](docs/decisions.md#open-questions). The legend does confirm that code 0 means no drought.
- The raw ACMAD CDI for 2026-09-11 changes abruptly along a straight north-south line near 12.1 degrees east. It is in ACMAD's file, not the tools; to confirm with ACMAD. See [data sources](docs/data-sources.md).
- The plugin has been tested headless, not in an interactive QGIS session, and the language model path has not been tried against a real service.
- The default admin level 1 layer (`data_api_adminlevelone`) does not exist on ACMAD's GeoServer, so the QGIS boundary fetch for admin level 1 fails. Use the OCHA boundaries; see [data sources](docs/data-sources.md).
