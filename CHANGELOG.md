# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/). Versions follow [Semantic Versioning](https://semver.org/); while the thresholds are placeholders the project stays below 1.0.

## [Unreleased]

## [0.5.0] - 2026-10-13

The second release. A new user can now go from installing the plugin to a finished map and a region summary in seconds, with nothing to download by hand: ACMAD's prepared exposure and Niger's regions are fetched automatically. The optional language model description works against real services and explains its errors. Versions 0.4.x were development builds. Thresholds and class mapping are still provisional; see [Known problems](#known-problems).

### Added

- **Every tab scrolls**, so nothing is cut off in a short panel, and the region table is sized to its rows and scrolls sideways. **Larger table (copy to a spreadsheet)** opens every figure of the region summary (17 columns) in a window of its own, sortable, with a **Copy table** button that puts it on the clipboard as tab-separated text.
- Guides: [installation](docs/installation.md) (install, update, where files go, what is downloaded), [troubleshooting](docs/troubleshooting.md) (messages and symptoms, how to report a problem) and [language model](docs/language-model.md) (setup, exactly what is sent, reasoning models, errors).
- **ACMAD's prepared exposure, ticked by default.** The panel's Exposure box has a *Use ACMAD's prepared exposure* option. It downloads four small rasters (about 66 KB) from ACMAD's public storage in a few seconds instead of building exposure from land cover (about 430 MB and 5 minutes). The files are checked (readable, values in range, one common grid) and installed atomically, so a failed download never leaves a broken exposure folder. Their origin and SHA-256 are recorded in `exposure_source.json` and in `run_metadata.json`. Untick the box to build from land cover as before. The command-line script has the same choice: `scripts/prepare_exposure_rasters.py --source acmad`. A first run from a brand-new state takes about 11 seconds.
- When a language model key is rejected, the message now says how long the key you entered is, its last four characters, and where the easy-to-confuse characters (0/O, 1/l/I) are, so a mistyped key can be spotted without showing it.
- **Extra request fields** (optional JSON) in the Settings tab for language model services that need them. For a reasoning model, `{"chat_template_kwargs": {"enable_thinking": false}}` turns thinking off; on the Qwen model we tried this cut a description from a minute or more (or no answer) to about 15 seconds. A troubleshooting table is in [using the panel](docs/using-the-panel.md).
- **Test connection** in the Settings tab. It checks the language model's address, key and model one at a time, using what is typed (no need to save first), and says which is wrong: address not found (and the exact address the plugin called), key rejected, or model not offered by the service (with the models it does offer). It never shows the key or the service's own error text.
- **Region summary with one click.** The Results tab's *Summarise by region* now defaults to *Use ACMAD's admin level 1 regions*: it fetches Niger's 8 regions (OCHA, CC BY-IGO, about 180 KB) from ACMAD's public storage in the background, checks the file, summarises, and shows the OCHA credit. Untick the box to summarise by any polygon layer of your own, as before. `scripts/upload_exposure_to_minio.py` publishes the regions file and refuses to upload one the plugin would reject.
- The choice is remembered, and when a download fails the panel says to untick the box to build from land cover instead.
- A test guard that makes any test using the real network fail, after one test quietly started a real download.

### Changed

- Language model errors now say what to check for each failure, instead of "answered with HTTP 404": a rejected key, a service address that was not found (showing the address called and that it should end with /v1), a model name problem, rate limiting, or a fault on the service's side. The service's own reply text is never shown, because services often echo parts of the key in it.
- The class table in the Results tab is sized to its four rows. It was clipped to three with a scrollbar when the font was larger.
- The "no exposure data" dialog describes the quick route (a few seconds) when ACMAD's files are selected, and the land cover build otherwise. Fetching ACMAD's files needs no confirmation because they are tiny; the land cover build still asks first.

### Known problems

- **Thresholds, class mapping and weights are provisional**, as in 0.3.2. ACMAD's prepared exposure carries the provisional cut-offs and will be republished when they are confirmed.
- The CDI code bins differ from ACMAD's WMS legend at codes 4 and 7 (see the [decision log](docs/decisions.md#open-questions)), and the raw ACMAD CDI for 2026-09-11 has a straight north-south edge near 12.1 degrees east (see [data sources](docs/data-sources.md)).
- The prepared exposure and the regions file are read from ACMAD's public storage at fixed addresses. If ACMAD moves them, the plugin needs updating; until then, unticking the two *Use ACMAD's…* options builds exposure from land cover or lets you use your own region layer.
- Used in QGIS 3.28 on macOS by the project developer, with a real language model service (a LiteLLM proxy serving a Qwen model). Not tried on Windows or Linux.

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

- A language model key pasted with a leading space or a non-breaking space was rejected by the service as invalid, and one with a line break or an invisible character could not be sent at all (with a confusing error). Spaces, line breaks and invisible characters are now removed from the key, and stray spaces from the address and model name. A key with accented or other non-ASCII characters gets a plain message instead of an error.
- Language model descriptions from slow reasoning models failed after about a minute, because a gateway cut the silent connection. The answer is now streamed, so data keeps flowing; the model's thinking is never shown; a model that spends its whole allowance thinking gets a plain explanation of what to change; and an overall limit stops a request that never finishes.
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

[Unreleased]: https://github.com/ACMAD-Niamey/fao-niger-agroclimate-risk-tools/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/ACMAD-Niamey/fao-niger-agroclimate-risk-tools/compare/v0.3.2...v0.5.0
[0.3.2]: https://github.com/ACMAD-Niamey/fao-niger-agroclimate-risk-tools/releases/tag/v0.3.2
