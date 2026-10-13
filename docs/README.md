# Documentation Index

This folder contains the technical and product documentation for the FAO Niger agroclimate risk tools.

## Core Documents

- [Technical note](technical-note.md): the main design document describing the proposed products, data sources, formulas, implementation architecture, and phased development plan.
- [Project plan and current status](project-plan-status.md): the four deliverables, how far each has come, and next steps.
- [Installation](installation.md): install, update, uninstall; where files go; what the plugin downloads.
- [Using the panel](using-the-panel.md): what to choose in the QGIS panel, step by step.
- [Language model](language-model.md): the optional plain-language description: setup, what is sent, reasoning models, errors.
- [Troubleshooting](troubleshooting.md): messages and symptoms, and how to report a problem.
- [Releasing](releasing.md): how to version, build and publish a plugin release.
- [Reading the risk maps](reading-the-maps.md): a guide for people who open the outputs in QGIS.
- [Data sources](data-sources.md): every external input, what it contains and what was verified.
- [Decision log](decisions.md): the choices behind the tools, and which still need confirmation.
- [Implementation notes](implementation.md): modules, commands, outputs, method and tests.
- [QGIS integration](qgis-integration.md): QGIS Processing structure and plugin-ready design notes.
- [Agropastoral Drought Risk Map](products/agropastoral-drought-risk-map.md): the first product selected for implementation.

## Product Documentation

- [Products index](products/README.md): product-level documentation for maps, advisory outputs, trigger matrices, and summary tables.

Each product document should define:

- purpose
- users
- input datasets
- processing logic
- formulas and thresholds
- outputs
- update frequency
- quality-control requirements
- known limitations
- handover notes

## Planned Documentation

The ACMAD API notes and the data inventory now live in [data sources](data-sources.md).

- Future Google Earth Engine indicator note
- QGIS Processing script design
- QGIS plugin wrapper design
- Water-point and vulnerability source note (no source chosen yet)
- Threshold validation note
- Advisory message library
