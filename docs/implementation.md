# Implementation Notes

*Last reviewed: 2026-10-12.* For developers. The overview is in the [README](../README.md); what is decided and what is still a placeholder is in the [decision log](decisions.md).

## Modules

All logic lives in `src/agroclimate_core/` and has no QGIS dependency, so scripts, QGIS Processing algorithms and a future plugin call the same code.

| Module | Purpose |
| --- | --- |
| `risk.py` | Scoring of single records: hazard, exposure, risk score, class. Used by the vector (zonal) path |
| `raster_pipeline.py` | Clips the hazard to Niger, aligns exposure, scores risk, writes the GeoTIFFs |
| `exposure.py` | WorldCover to class fractions per cell, bins fractions to 0-3 scores, fetches and caches tiles |
| `periods.py` | Dekad and season arithmetic; chooses a period from what is published, with a fallback limit |
| `acmad_availability.py` | Reads ACMAD's availability and dataset catalogues |
| `acmad_download.py` | Downloads CDI (`download_data`) and combined products (`download_combined_product`) |
| `acmad_boundaries.py` | WFS requests for ACMAD boundary layers (admin level 0 only works; see [data sources](data-sources.md)) |
| `admin_summary.py` | Risk summary per administrative unit |
| `run_metadata.py` | Writes `run_metadata.json` |
| `storage.py` | MinIO upload helpers; credentials from the environment |
| `table.py` | CSV scoring harness |

Entry points are in `scripts/`; QGIS code is in `qgis/`.

## Commands

| Script | Does |
| --- | --- |
| `build_agropastoral_risk_raster.py` | Builds a risk map for a date |
| `prepare_exposure_rasters.py` | Builds cultivated and rangeland exposure on a template grid |
| `summarize_by_admin.py` | Summarises a risk map by admin unit |
| `upload_exposure_to_minio.py` | Uploads prepared layers to MinIO (`--dry-run` lists first) |
| `build_qgis_plugin.py` | Builds the plugin zip |
| `score_agropastoral_risk_csv.py` | Scores a CSV table |

Run any of them with `--help` for every option. The main ones for the risk runner:

| Option | Meaning |
| --- | --- |
| `--analysis-date YYYY-MM-DD` | The date to map. The period is chosen from what ACMAD has published |
| `--year --month --dekad` | An exact CDI period; never replaced by a fallback |
| `--hazard cdi` or `combined` | Current CDI (default) or the seasonal combined hazard |
| `--forecast-period SON --forecast-year 2026` | An exact season for `--hazard combined` |
| `--max-fallback-dekads N` | How far back to fall back when the requested dekad is not published (default 3) |
| `--strict-dates` | Refuse instead of falling back |
| `--cultivated-raster`, `--rangeland-raster`, `--water-points-raster` | Exposure rasters on the 0-3 scale. Without them a constant default is used |
| `--no-agropastoral-mask` | Score every cell, not only cells with cropland or rangeland |
| `--grid-template` | Raster whose grid the outputs use. Defaults to the first exposure raster when `--hazard combined` |
| `--cdi-product` | `cdi` (default) or `cdi_era5` |

## Outputs of a risk run

Written to `outputs/niger-risk-<period>/` unless `--output-dir` is given. The folder name uses the period actually used, not the date requested.

| File | Content |
| --- | --- |
| `cdi_niger.tif` or `combined_hazard_niger.tif` | The hazard, clipped to Niger (raw ACMAD codes) |
| `agropastoral_risk_score.tif` | Risk score, 0 to 3, float, nodata -9999 |
| `agropastoral_risk_class.tif` | 1 low, 2 moderate, 3 high, 4 very high; nodata 255 |
| `agropastoral_risk_stack.tif` | Four bands: `hazard_score`, `exposure_score`, `risk_score`, `risk_class` |
| `run_metadata.json` | Requested date, period used, fallback and lag, source files, exposure inputs, mask setting |
| `niger_boundary_admin0.geojson` | Boundary used for clipping |
| `*_aligned.tif` | Intermediate exposure rasters on the output grid |

`outputs/` is ignored by Git.

## Method

**Hazard score, 0 to 3.**

- CDI, ACMAD detailed codes: 0 to 0; 1-3 to 1 (watch); 4-6 to 2 (warning); 7-10 to 3 (alert); 11-12 to 1 (partial recovery); 13-14 to 0 (full recovery).
- Combined hazard, classes 1-9: 1-2 to 0; 3-4 to 1; 5-6 to 2; 7-9 to 3. This is a proposal awaiting ACMAD and FAO.
- The CDI is requested unmasked, so code 0 stays a real value.

**Exposure score, 0 to 3.** For each hazard-grid cell, the share of 10 m WorldCover pixels in the class (cropland 40 for cultivated; shrubland 20 and grassland 30 for rangeland), binned at 5%, 25% and 50%: below 5% scores 0, then 1, 2, 3. Both layers use the same placeholder cut-offs. Nodata pixels are left out of the denominator.

```text
Exposure = 0.45 cultivated + 0.35 rangeland + 0.20 water points
```

Water points use a constant default (1) until a source exists.

**Risk score and class.**

```text
Risk = 0.60 Hazard + 0.40 Exposure         (raster path)
Risk = 0.50 Hazard + 0.30 Exposure + 0.20 Vulnerability   (vector path, when V exists)
```

Classes: below 1.0 low; 1.0 to below 1.7 moderate; 1.7 to below 2.4 high; 2.4 and above very high.

**Agropastoral mask.** With exposure rasters supplied, only cells where cultivated or rangeland exposure is above zero are scored; the rest are no data. This is a modelling choice, recorded as D8 in the [decision log](decisions.md).

**Grid.** The 0.1 degree CDI grid over Niger. A 1 degree combined hazard is resampled by nearest neighbour, so each coarse cell repeats. Exposure is always aggregated, never resampled, because it is categorical land cover.

**Dates.** The CDI dekad containing the date is looked up against ACMAD's `latest_*` fields. If it is later than the latest published, the latest is used when within `--max-fallback-dekads`. Seasons are chosen from the product's `available_periods` in the dataset catalogue, preferring the latest-starting published season that contains the date.

**Admin summary.** Polygons are rasterised onto the risk grid and a cell belongs to the unit holding its centre. Areas use spherical cell areas. Means are area-weighted over scored cells only. "High-risk hectares" are cropland or rangeland fractions times cell area, summed over cells classed high or very high.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

90 tests passed on 2026-10-12. Several need the GDAL Python bindings and error without them, so run the tests with a Python that has `osgeo`. The tests use small synthetic rasters; the live ACMAD, WorldCover and MinIO services are not called in tests.

Syntax check without writing bytecode:

```bash
python3 -c "import ast, pathlib; files=[p for root in ['qgis','src','scripts','tests'] for p in pathlib.Path(root).rglob('*.py')]; [ast.parse(p.read_text(), filename=str(p)) for p in files]; print(f'AST syntax OK: {len(files)} files')"
```
