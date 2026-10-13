# FAO Niger Agroclimate Risk Tools

Tools that turn ACMAD drought products and open land cover into agropastoral drought risk maps for Niger, and summarise them by region. They are built for FAO Niger and national counterparts, and run either from a QGIS panel or from the command line. Both use the same code.

**Status: working prototype.** One product, the Agropastoral Drought Risk Map, runs end to end on real ACMAD and land cover data, from a QGIS panel or the command line. Its thresholds and class mapping are placeholders awaiting review by FAO and ACMAD. The advisory, trigger and training deliverables are planned, not built. See [project plan and status](docs/project-plan-status.md).

## How it works

```text
ACMAD CDI (dekadal)  ─┐
ACMAD combined hazard ┴─> pick the period ACMAD has published
                              │
ESA WorldCover  ─> cropland / rangeland share per cell ─> exposure score 0-3
                              │
                              v
        risk score = 0.6 x hazard + 0.4 x exposure   (0-3 scale, 4 classes)
                              │
                              v
   GeoTIFF risk maps for QGIS  +  summary table by admin region  +  run_metadata.json
```

One rule runs through the design: **consume, don't compute.** Hazard and forecasts are ACMAD's published products, used as they are. The tools add the overlay with land cover and the summaries, not new climate indicators. See the [decision log](docs/decisions.md).

## What works today

| Part | State |
| --- | --- |
| Risk map from the current CDI | Working. Placeholder exposure thresholds; water-point exposure is a constant |
| Risk map from the seasonal combined hazard | Working. Class-to-score mapping is a proposal awaiting ACMAD |
| Date selection with fallback to the latest published period | Working |
| Exposure rasters from land cover, cached, shareable through MinIO | Working |
| Summary by admin region (CSV and GeoJSON) | Working, tested on OCHA admin level 1 |
| QGIS panel (plugin) | Working: runs the workflow in the background, adds styled layers to the map, shows statistics and a region summary. Tested in headless QGIS 3.28 with real data, and used interactively on macOS by the project developer, who reported it working well. Not yet tried on Windows or Linux |
| Optional language model description | Working, off by default. Needs a service address, key and model |
| QGIS styles | Rendered and checked headless; not yet reviewed by a person in QGIS |
| QGIS Processing algorithms | Score zonal vector layers; they do not run the raster workflow |
| Cropping-zone and pastoral maps, advisories, triggers | Planned |

## Quick start in QGIS

1. Download `fao_niger_agroclimate-<version>.zip` from the [Releases page](https://github.com/ACMAD-Niamey/fao-niger-agroclimate-risk-tools/releases) (do not unzip it). To build it yourself instead: `python3 scripts/build_qgis_plugin.py` writes `dist/qgis/fao_niger_agroclimate.zip`.
2. In QGIS 3.28 or later: `Plugins > Manage and Install Plugins > Install from ZIP`, choose the zip, and enable the plugin.
3. Check `Plugins > Manage and Install Plugins > Installed` shows version 0.3.2 or later, restart QGIS if you reinstalled over an older version, then open the panel: use the button in the message QGIS shows when it loads the plugin, the first entry of the *FAO Niger Agroclimate* group in the Processing Toolbox (*Agroclimate Risk panel*), the toolbar icon, or `Plugins > FAO Niger Agroclimate > Open Agroclimate Risk Panel`.
4. On the **Run** tab, pick a period and press **Run and add to map**. The first time, the panel offers **Prepare exposure, then run** (about 5 minutes, needs internet, once only) and carries on by itself. The **Results** tab shows the statistics; add a region layer there for a summary by region. The optional language model is set up in the **Settings** tab.

See [using the panel](docs/using-the-panel.md) for what to choose, and [reading the risk maps](docs/reading-the-maps.md) for what the layers mean. The Processing Toolbox also has older vector tools; they do not build the map.

## Quick start on the command line

You need Python 3.9 or later with GDAL bindings (`osgeo`). QGIS's own Python has them (QGIS 3.28 ships Python 3.9); a standalone Python may need GDAL installed.

```bash
# 1. Build exposure rasters once (about 5 minutes; land cover is cached)
python3 scripts/build_agropastoral_risk_raster.py --analysis-date 2026-09-05   # creates the boundary and CDI grid
python3 scripts/prepare_exposure_rasters.py \
  --template outputs/niger-risk-2026-09-01/cdi_niger.tif \
  --boundary outputs/niger-risk-2026-09-01/niger_boundary_admin0.geojson

# 2. Build a risk map for a date
python3 scripts/build_agropastoral_risk_raster.py --analysis-date 2026-10-12 \
  --cultivated-raster outputs/exposure/cultivated_exposure.tif \
  --rangeland-raster  outputs/exposure/rangeland_exposure.tif

# 3. The seasonal outlook instead of the current CDI
python3 scripts/build_agropastoral_risk_raster.py --hazard combined --analysis-date 2026-10-12 \
  --cultivated-raster outputs/exposure/cultivated_exposure.tif \
  --rangeland-raster  outputs/exposure/rangeland_exposure.tif

# 4. Summarise by region
python3 scripts/summarize_by_admin.py --risk-dir outputs/niger-risk-2026-09-11 \
  --admin-geojson path/to/ner_admin1.geojson --name-field adm1_name --code-field adm1_pcode
```

ACMAD publishes with a lag of about a month, so a run for today uses the latest CDI it has, says so in the log, and records it in `outputs/<run>/run_metadata.json`. Add `--strict-dates` to refuse instead.

Run the tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Build an installable QGIS plugin zip (`dist/qgis/fao_niger_agroclimate.zip`):

```bash
python3 scripts/build_qgis_plugin.py
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/agroclimate_core/` | The logic, with no QGIS dependency, shared by the scripts and the plugin: workflow, scoring, raster pipeline, exposure, dates, statistics, ACMAD clients, storage, optional language model |
| `scripts/` | Command-line entry points; thin shells over the shared workflow |
| `qgis/plugin/` | The QGIS panel: interface, background tasks, map layers, settings |
| `qgis/processing/`, `qgis/styles/` | Processing algorithms and map styles |
| `tests/` | Unit tests |
| `docs/` | Design, data sources, decisions, product specification |

## Documentation

- [Project plan and status](docs/project-plan-status.md): the four deliverables and where each stands.
- [Reading the risk maps](docs/reading-the-maps.md): what the values, classes and blank areas mean.
- [Data sources](docs/data-sources.md): every external input, with what was verified and when.
- [Decision log](docs/decisions.md): the choices behind the tools and which still need confirmation.
- [Implementation notes](docs/implementation.md): modules, the plugin's design, commands, outputs, formulas.
- [Agropastoral Drought Risk Map](docs/products/agropastoral-drought-risk-map.md): the product specification.
- [Technical note](docs/technical-note.md): the full design across all seven products.
- [QGIS integration](docs/qgis-integration.md)
- [Changelog](CHANGELOG.md) and [how to release](docs/releasing.md)

## Credits

Hazard data: ACMAD. Land cover: ESA WorldCover 2021 (CC BY 4.0). Administrative boundaries: OCHA Common Operational Dataset (CC BY-IGO).
