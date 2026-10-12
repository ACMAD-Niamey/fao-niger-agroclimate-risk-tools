# QGIS Integration

## Direction

The QGIS implementation is designed in two layers:

1. QGIS Processing algorithms that perform the operational work.
2. A future QGIS plugin UI that registers and calls those algorithms.

The plugin should not duplicate the risk logic. It should provide a user-friendly interface around the same Processing algorithms used during development and testing.

## Current QGIS Components

| Path | Purpose |
| --- | --- |
| `qgis/processing/agropastoral_drought_risk.py` | QGIS Processing algorithm for the first product. |
| `qgis/processing/provider.py` | Processing provider that registers project algorithms in QGIS. |
| `qgis/processing/bootstrap.py` | Adds the repository `src/` directory to the QGIS Python path. |
| `qgis/processing/fields.py` | Shared output field definitions. |
| `qgis/plugin/` | Minimal plugin scaffold for registering the Processing provider. |

## Processing Algorithm

The first algorithm is:

```text
Agropastoral Drought Risk Map
```

It expects a vector layer where each feature already represents the reporting unit or analysis unit to be scored. This can be an administrative unit, FAO intervention zone, livelihood zone, or precomputed zonal overlay.

The algorithm adds:

```text
hazard_score
exposure_score
risk_score
risk_class
```

## Expected Workflow

1. Prepare or load a zonal input layer in QGIS.
2. Ensure the layer contains CDI, optional fAPAR anomaly, optional soil moisture anomaly, and exposure fields.
3. Run the Processing algorithm.
4. Review the output risk classes.
5. Apply QGIS styles and export maps/tables.

## Plugin-Ready Design

The plugin will eventually:

- register the Processing provider
- expose a simple product-selection UI
- collect inputs from the user
- call the Processing algorithm
- apply styles and layouts
- export a map package

The backend remains the Processing algorithm and the shared Python package under `src/`.

## Runtime Note

The repository includes a local folder named `qgis/` for project integration files. QGIS itself also provides a Python package named `qgis`. For that reason, plugin code loads the local Processing provider through explicit local paths rather than importing it as `qgis.processing.provider`.
