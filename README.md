# FAO Niger Agroclimate Risk Tools

Documentation and implementation notes for agroclimatic risk mapping, agricultural advisory products, and anticipatory action support for FAO Niger.

The repository is documentation-first. It defines the products, data inputs, formulas, workflows, and implementation direction before scripts or QGIS plugin components are developed.

## Purpose

This work supports the development of operational products that combine ACMAD drought and forecast information, Google Earth Engine indicators, QGIS workflows, land use and land cover data, and socioeconomic exposure layers.

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

## Implementation Direction

The proposed implementation path is:

1. Define and validate the products.
2. Confirm ACMAD API products and response formats.
3. Identify complementary GEE-derived indicators.
4. Build QGIS Processing scripts for each product.
5. Keep scripts plugin-ready through clean parameters and outputs.
6. Wrap stable scripts in a simple QGIS plugin interface when the workflow is mature.

## Core Architecture

```text
ACMAD API + GEE + local exposure layers
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

## Repository Status

Current status: documentation and product design.

Implementation scripts, QGIS templates, styles, and plugin components will be added after the product specifications are reviewed and accepted.

