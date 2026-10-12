# FAO Niger Agroclimate Risk Tools

Documentation and implementation notes for agroclimatic risk mapping, agricultural advisory products, and anticipatory action support for FAO Niger.

The repository is product-first. It defines the products, data inputs, formulas, workflows, and implementation direction, then implements the workflows as testable scripts before wrapping them in QGIS plugin components.

## Purpose

This work supports the development of operational products that combine ACMAD drought and forecast information, QGIS workflows, land use and land cover data, and socioeconomic exposure layers. The first raster workflow downloads ACMAD CDI and can consume exposure rasters prepared from Google Earth Engine or other local sources.

The intended outputs include:

- agropastoral drought risk maps
- cropping-zone drought risk maps
- pastoral and rangeland stress maps
- seasonal agricultural advisory products
- anticipatory action trigger matrices
- administrative risk summary tables
- map and advisory export packages

## Documentation

- [Technical note](docs/technical-note.md): product architecture, inputs, outputs, formulas, implementation approach, and references.
- [Documentation index](docs/README.md): entry point for all technical and product documentation.
- [Product documentation](docs/products/README.md): index for each product specification as it is developed.
- [Agropastoral Drought Risk Map](docs/products/agropastoral-drought-risk-map.md): first implementation product specification.
- [QGIS integration](docs/qgis-integration.md): Processing algorithm and future plugin wrapper notes.

## Implementation

The first implementation separates tested scoring logic from QGIS-specific code:

- `src/agroclimate_core/`: core Python package for risk scoring.
- `src/agroclimate_core/acmad_boundaries.py`: ACMAD WFS boundary request helpers, including Niger admin-0 defaults.
- `src/agroclimate_core/acmad_download.py`: ACMAD raster download helper for the `download_data` API endpoint.
- `src/agroclimate_core/raster_pipeline.py`: GDAL/NumPy raster pipeline for clipping CDI, aligning exposure rasters, and writing risk GeoTIFFs.
- `scripts/build_agropastoral_risk_raster.py`: end-to-end raster runner that produces QGIS-ready outputs.
- `scripts/score_agropastoral_risk_csv.py`: command-line CSV scoring harness.
- `qgis/processing/agropastoral_drought_risk.py`: QGIS Processing wrapper designed to be wrapped later by a plugin UI.
- `qgis/processing/fetch_acmad_boundary.py`: QGIS Processing tool for fetching Niger boundaries from ACMAD WFS.
- `qgis/processing/provider.py`: QGIS Processing provider for plugin registration.
- `qgis/plugin/`: minimal plugin scaffold for the future QGIS plugin.
- `tests/`: standard-library unit tests for the core scoring logic.
- `sample_data/agropastoral_units.geojson`: small sample layer for testing the QGIS Processing algorithm.

Build an installable QGIS plugin zip:

```bash
python3 scripts/build_qgis_plugin.py
```

This creates:

```text
dist/qgis/fao_niger_agroclimate.zip
```

QGIS users can install that zip from `Plugins > Manage and Install Plugins > Install from ZIP`.

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The raster runner requires GDAL Python bindings through `osgeo.gdal`. A QGIS Python environment usually provides this; a standalone Python environment may need GDAL installed separately.

Score a CSV table:

```bash
PYTHONPATH=src python3 scripts/score_agropastoral_risk_csv.py input.csv output.csv
```

Build a first risk raster output for QGIS:

```bash
python3 scripts/build_agropastoral_risk_raster.py \
  --year 2026 \
  --month 5 \
  --dekad 21 \
  --output-dir outputs/niger-risk-2026-05-21
```

The script downloads ACMAD CDI unless `--cdi-raster` is supplied, fetches the Niger boundary from ACMAD WFS, clips CDI to Niger, combines it with exposure scores, and writes GeoTIFF outputs.
ACMAD CDI detailed codes are remapped to the `0-3` hazard scale by default.

## Implementation Direction

The proposed implementation path is:

1. Define and validate the products.
2. Test ACMAD CDI downloads and local GeoTIFF outputs.
3. Build the first product using ACMAD CDI and exposure layers prepared from GEE or local datasets.
4. Keep scripts plugin-ready through clean parameters and outputs.
5. Add QGIS styles for CDI, exposure, risk score, and risk class.
6. Wrap stable scripts in a simple QGIS plugin interface when the workflow is mature.

## Core Architecture

```text
ACMAD CDI raster + GEE/local exposure layers
        |
        v
End-to-end Python/GDAL scripts
        |
        v
Risk maps + advisory products + trigger matrices
        |
        v
QGIS layouts, reports, tables, and handover materials
```

Future extensions may add GEE-derived indicators such as NDVI anomaly, surface water, land cover refinements, heat stress, or start-of-season metrics.

## Repository Status

Current status: documentation, scoring logic, QGIS plugin scaffold, ACMAD boundary fetch, and first end-to-end raster runner.

The next implementation step is exposure preparation: cultivated areas, rangelands, water points, and optional vulnerability rasters on a 0-3 score scale.
