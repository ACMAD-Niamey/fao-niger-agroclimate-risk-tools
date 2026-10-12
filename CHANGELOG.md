# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/). The project has no tagged releases yet.

## [Unreleased]

### Added

- Land cover exposure preparation: ESA WorldCover is aggregated to the hazard grid as cropland and rangeland fractions and binned into 0-3 scores (`scripts/prepare_exposure_rasters.py`). Only tiles and cells that touch the boundary are fetched, in parallel, and cached in `outputs/cache/worldcover`.
- MinIO upload of prepared layers (`scripts/upload_exposure_to_minio.py`, `agroclimate_core.storage`). Credentials come from `.env`; `.env.example` lists the names.
- Date selection from ACMAD's catalogue: the CDI dekad and the seasonal period are resolved from what is published. The latest period within `--max-fallback-dekads` (default 3) is used when the requested one is missing; `--strict-dates` refuses instead.
- `run_metadata.json` beside every run, recording the requested date, the period actually used, any fallback and its lag, and the exposure inputs.
- Combined monitoring and forecast hazard as a second hazard input (`--hazard combined`), resampled onto the exposure grid.
- Option to score only cells with cropland or rangeland exposure (on by default when exposure rasters are given; `--no-agropastoral-mask` turns it off).
- Summaries by administrative unit (`scripts/summarize_by_admin.py`): risk class shares, area-weighted mean score, worst class, and cropland and rangeland hectares in high-risk cells.
- QGIS style for the combined hazard and a plugin menu action for it.
- Documents: [data sources](docs/data-sources.md) and [decision log](docs/decisions.md).

### Changed

- The CDI is downloaded unmasked (`mask_nodata=false`). Before, "no drought" areas were dropped from the map instead of scored low.
- QGIS styles use a sequential, colour-blind-safe ramp. Risk class labels now state the real score breaks.
- The docs now state the "consume, don't compute" principle and describe the prototype against the four ToR deliverables.

### Fixed

- Supplying an exposure raster crashed the pipeline (it looked for a file name that was never written).
- Exposure rasters ignored their own nodata value and were resampled by nearest neighbour; they now keep their nodata and are averaged.
- The stack's `risk_class` band showed 255 instead of nodata where cells were invalid.

### Known problems

- The default admin level 1 layer (`data_api_adminlevelone`) does not exist on ACMAD's GeoServer, so the QGIS boundary fetch for admin level 1 fails. Use the OCHA boundaries; see [data sources](docs/data-sources.md).
