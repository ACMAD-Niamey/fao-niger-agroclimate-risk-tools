# Project Plan and Current Status

## Purpose

This document summarizes the implementation plan for the FAO Niger agroclimate risk tools and records how far the current repository has progressed.

The immediate goal is to produce a working, transparent agropastoral drought risk map for Niger using ACMAD drought products, exposure layers, and QGIS-ready outputs. The preferred path is script-first: build and test an end-to-end workflow that produces GeoTIFF outputs, then wrap the stable workflow in a QGIS Processing tool and plugin UI.

## Product Direction

The first operational product is the Agropastoral Drought Risk Map.

The product should answer:

- where drought hazard overlaps with cultivated areas, rangelands, and water-access exposure
- which locations are low, moderate, high, or very high risk
- which outputs can be opened, styled, reviewed, and exported in QGIS

The current version focuses on CDI as the main drought hazard layer. fAPAR anomaly, soil moisture anomaly, vulnerability, and advisory/trigger logic remain planned extensions after the core raster workflow is stable.

## Current Architecture

The current workflow is:

```text
ACMAD CDI GeoTIFF
        +
Niger boundary from ACMAD WFS
        +
Exposure rasters or default exposure scores
        |
        v
Python/GDAL raster runner
        |
        v
QGIS-ready GeoTIFF outputs
        |
        v
QGIS styling and map production
```

The implementation keeps the risk logic in `src/agroclimate_core/` so it can be reused by command-line scripts, QGIS Processing algorithms, and a future plugin interface.

## Implemented So Far

### Documentation

Implemented:

- technical note defining products, data sources, formulas, implementation approach, and handover requirements
- first product specification for the Agropastoral Drought Risk Map
- QGIS integration notes
- implementation notes
- this plan/status document

Main files:

- `docs/technical-note.md`
- `docs/products/agropastoral-drought-risk-map.md`
- `docs/qgis-integration.md`
- `docs/implementation.md`
- `docs/project-plan-status.md`

### Core Scoring Logic

Implemented:

- CDI and anomaly class scoring on a `0-3` scale
- hazard score calculation
- exposure score calculation
- risk score calculation
- risk class thresholds
- CSV scoring harness for lightweight testing

Main files:

- `src/agroclimate_core/risk.py`
- `src/agroclimate_core/table.py`
- `scripts/score_agropastoral_risk_csv.py`

### ACMAD Boundary Integration

Implemented:

- ACMAD WFS boundary request helper
- Niger admin-0 defaults using:
  - layer: `data_api_adminlevelzero`
  - country field: `country_code`
  - Niger code: `181`
- editable GeoServer/WFS URL support
- optional workspace support

Main files:

- `src/agroclimate_core/acmad_boundaries.py`
- `qgis/processing/fetch_acmad_boundary.py`

### ACMAD CDI Raster Download

Implemented:

- ACMAD API `download_data` helper for raster products
- handling for immediate GeoTIFF responses
- handling for asynchronous download jobs
- live test against ACMAD CDI download

Main file:

- `src/agroclimate_core/acmad_download.py`

### End-to-End Raster Runner

Implemented:

- command-line runner for the first risk raster workflow
- analysis date selection using `--analysis-date YYYY-MM-DD`
- automatic dekad selection:
  - day `1-10` -> dekad `1`
  - day `11-20` -> dekad `11`
  - day `21-end` -> dekad `21`
- CDI download or local CDI override
- Niger boundary fetch
- CDI clipping to Niger
- ACMAD detailed CDI code remapping to `0-3` hazard scores:
  - `0` -> no drought -> `0`
  - `1-3` -> watch -> `1`
  - `4-6` -> warning -> `2`
  - `7-10` -> alert -> `3`
  - `11-12` -> partial recovery -> `1`
  - `13-14` -> full recovery -> `0`
- exposure score calculation using provided exposure rasters or transparent defaults
- GeoTIFF outputs for QGIS

Main files:

- `scripts/build_agropastoral_risk_raster.py`
- `src/agroclimate_core/raster_pipeline.py`

Example command:

```bash
python3 scripts/build_agropastoral_risk_raster.py --analysis-date 2026-05-24
```

Generated outputs:

```text
outputs/niger-risk-<analysis-date>/cdi_niger.tif
outputs/niger-risk-<analysis-date>/agropastoral_risk_score.tif
outputs/niger-risk-<analysis-date>/agropastoral_risk_class.tif
outputs/niger-risk-<analysis-date>/agropastoral_risk_stack.tif
```

The `outputs/` directory is intentionally ignored by Git.

### QGIS Plugin Scaffold

Implemented:

- installable QGIS plugin zip builder
- plugin metadata with FAO-Niger as author
- Processing provider registration
- risk scoring Processing algorithm for vector/zonal testing
- boundary fetch Processing algorithm
- plugin menu actions for applying raster styles

Main files:

- `scripts/build_qgis_plugin.py`
- `qgis/plugin/`
- `qgis/processing/`

### QGIS Styling

Implemented:

- CDI hazard style
- risk score style
- risk class style
- plugin menu actions to apply styles to the selected raster layer

Main files:

- `qgis/styles/cdi_hazard.qml`
- `qgis/styles/risk_score.qml`
- `qgis/styles/risk_class.qml`

In QGIS, after loading an output raster:

1. Select the raster layer in the Layers panel.
2. Open `Plugins > FAO Niger Agroclimate`.
3. Choose the matching style action.

### Testing

Implemented tests cover:

- risk scoring formulas
- table scoring
- ACMAD boundary URL construction
- QGIS helper/plugin source checks
- raster pipeline using synthetic GeoTIFFs
- ACMAD CDI code remapping
- analysis-date to dekad conversion

Current test command:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Latest verified result:

```text
29 tests passing
```

## Current Limitations

### Exposure Data

Real exposure layers are not yet included.

The current raster runner can accept exposure rasters, but if they are not supplied it uses defaults:

```text
cultivated exposure = 2
rangeland exposure = 2
water-point exposure = 1
```

These defaults are for testing the pipeline only. They must be replaced with real exposure rasters before operational use.

Needed exposure layers:

- cultivated area exposure raster
- rangeland or pastoral exposure raster
- water-point or water-access exposure raster
- optional socioeconomic vulnerability raster

### Google Earth Engine

GEE integration is not yet implemented in the repo.

Expected GEE role:

- derive cultivated/rangeland masks from land cover data
- prepare rangeland or pastoral exposure proxies
- prepare water-access exposure layers where appropriate
- export rasters aligned to the CDI workflow or to a standard Niger grid

### QGIS Plugin UI

The plugin currently provides:

- Processing provider registration
- Processing tools
- style application menu actions

It does not yet provide a full end-to-end UI for choosing analysis date, downloading CDI, generating exposure, running the raster pipeline, and loading styled outputs automatically.

### Styling

QGIS style files are included and packaged, but they should still be visually reviewed in QGIS and refined after seeing the first real maps.

### Product Validation

The risk formula and thresholds are implemented, but the operational interpretation needs review with ACMAD/FAO Niger counterparts, especially:

- CDI remapping and recovery class handling
- exposure weights
- risk thresholds
- default exposure assumptions during testing
- eventual anticipatory action trigger thresholds

## Immediate Next Steps

1. Test the current raster outputs in QGIS.
2. Confirm that CDI download works for the target operational dates.
3. Review the risk class style in QGIS and refine colors/labels if needed.
4. Build exposure raster preparation.
5. Replace default exposure scores with real exposure rasters.
6. Add an end-to-end QGIS Processing algorithm around the raster runner.
7. Add a simple plugin UI after the script and Processing tool are stable.

## Exposure Preparation Plan

The next implementation block should create exposure rasters on the same `0-3` scale used by the risk formula.

Proposed approach:

```text
GEE or local exposure source
        |
        v
Reclassify to exposure score 0-3
        |
        v
Export GeoTIFF
        |
        v
Use as input to build_agropastoral_risk_raster.py
```

Candidate inputs:

- land cover for cultivated and rangeland masks
- water points or water bodies
- distance to water points
- FAO intervention zones, if available
- administrative boundaries for summarization

Expected exposure outputs:

```text
cultivated_exposure.tif
rangeland_exposure.tif
water_point_exposure.tif
```

Each raster should use:

```text
0 = no or very low exposure
1 = low exposure
2 = moderate exposure
3 = high exposure
```

## QGIS Plugin Plan

After exposure preparation is working, the plugin should expose a simple workflow:

1. Select analysis date.
2. Select output folder.
3. Choose whether to download CDI or use a local CDI raster.
4. Choose exposure rasters or generate/select defaults for testing.
5. Run the raster pipeline.
6. Load output rasters into QGIS.
7. Apply the appropriate styles automatically.

The plugin should continue to call the shared core code rather than duplicating processing logic.

## Git and Output Handling

Generated rasters and plugin builds should stay out of Git.

Ignored paths include:

```text
outputs/
dist/
build/
__pycache__/
*.pyc
.DS_Store
```

Source code, documentation, tests, and style files should be committed.

## Current Status Summary

The project has moved beyond documentation-only status.

Current status:

- product design exists
- core scoring exists
- ACMAD boundary fetch exists
- ACMAD CDI raster download exists
- end-to-end raster runner exists
- QGIS plugin scaffold exists
- QGIS raster styles exist
- generated outputs are ignored by Git
- tests pass

The main remaining gap is real exposure-layer preparation. Once cultivated, rangeland, and water-access exposure rasters are produced, the first risk map can move from technical demonstration to a more realistic product prototype.
