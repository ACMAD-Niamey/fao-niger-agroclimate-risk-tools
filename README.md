# FAO Niger Agroclimate Risk Tools

Documentation and implementation notes for agroclimatic risk mapping, agricultural advisory products, and anticipatory action support for FAO Niger.

The repository is documentation-first. It defines the products, data inputs, formulas, workflows, and implementation direction before scripts or QGIS plugin components are developed.

## Purpose

This work supports the development of operational products that combine ACMAD drought and forecast information, QGIS workflows, land use and land cover data, and socioeconomic exposure layers. Google Earth Engine indicators are treated as future extensions, not dependencies for the initial implementation.

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

- `src/fao_niger_agroclimate/`: core Python package for risk scoring.
- `scripts/score_agropastoral_risk_csv.py`: command-line CSV scoring harness.
- `qgis/processing/agropastoral_drought_risk.py`: QGIS Processing wrapper designed to be wrapped later by a plugin UI.
- `qgis/processing/provider.py`: QGIS Processing provider for plugin registration.
- `qgis/plugin/`: minimal plugin scaffold for the future QGIS plugin.
- `tests/`: standard-library unit tests for the core scoring logic.

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Score a CSV table:

```bash
PYTHONPATH=src python3 scripts/score_agropastoral_risk_csv.py input.csv output.csv
```

## Implementation Direction

The proposed implementation path is:

1. Define and validate the products.
2. Confirm ACMAD API products and response formats.
3. Build the first product using ACMAD CDI, fAPAR anomaly, soil moisture anomaly, and local exposure layers.
4. Build QGIS Processing scripts for each product.
5. Keep scripts plugin-ready through clean parameters and outputs.
6. Add GEE-derived indicators later only where ACMAD products do not cover the required indicator.
7. Wrap stable scripts in a simple QGIS plugin interface when the workflow is mature.

## Core Architecture

```text
ACMAD API + local exposure layers
        |
        v
QGIS Processing scripts
        |
        v
Risk maps + advisory products + trigger matrices
        |
        v
QGIS layouts, reports, tables, and handover materials
```

Future extensions may add GEE-derived indicators such as NDVI anomaly, surface water, land cover refinements, heat stress, or start-of-season metrics.

## Repository Status

Current status: documentation and product design.

The first risk-scoring implementation has been added. ACMAD API fetch logic, QGIS templates, styles, zonal layer preparation, and plugin components will be added after the first scoring workflow is validated.
