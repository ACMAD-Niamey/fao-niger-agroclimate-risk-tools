# QGIS Integration

## Direction

The QGIS implementation is designed in two layers:

1. QGIS Processing algorithms that perform the operational work.
2. A future QGIS plugin UI that registers and calls those algorithms.

The plugin should not duplicate the risk logic. It should provide a user-friendly interface around the same Processing algorithms used during development and testing.

The development symlink used by developers is not the installation method for ordinary QGIS users. End users should install a packaged plugin zip.

## Current QGIS Components

| Path | Purpose |
| --- | --- |
| `qgis/processing/agropastoral_drought_risk.py` | QGIS Processing algorithm for the first product. |
| `qgis/processing/provider.py` | Processing provider that registers project algorithms in QGIS. |
| `qgis/processing/bootstrap.py` | Adds the repository `src/` directory to the QGIS Python path. |
| `qgis/processing/fields.py` | Shared output field definitions. |
| `qgis/plugin/` | Minimal plugin scaffold for registering the Processing provider. |
| `scripts/build_qgis_plugin.py` | Builds an installable QGIS plugin zip. |

## Installing as a QGIS User

Build the plugin zip:

```bash
python3 scripts/build_qgis_plugin.py
```

The build command creates:

```text
dist/qgis/fao_niger_agroclimate.zip
```

In QGIS:

1. Open `Plugins > Manage and Install Plugins`.
2. Select `Install from ZIP`.
3. Select `dist/qgis/fao_niger_agroclimate.zip`.
4. Enable `FAO Niger Agroclimate Risk Tools`.
5. Open the Processing Toolbox and look for `FAO Niger Agroclimate`.

This packaged zip includes:

- plugin metadata and entry point
- QGIS Processing provider
- QGIS Processing algorithms
- the shared `agroclimate_core` scoring package

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

## Quick Test Layer

A small sample layer is available at:

```text
sample_data/agropastoral_units.geojson
```

Use it to test the Processing algorithm before connecting real ACMAD and FAO Niger layers.

Expected field mapping:

```text
CDI field = cdi
fAPAR anomaly field = fapar_anomaly
Soil moisture anomaly field = soil_moisture_anomaly
Cultivated exposure field = cultivated_exposure
Rangeland exposure field = rangeland_exposure
Water-point exposure field = water_point_exposure
Vulnerability field = vulnerability
```

## Plugin-Ready Design

The plugin will eventually:

- register the Processing provider
- expose a simple product-selection UI
- collect inputs from the user
- call the Processing algorithm
- apply styles and layouts
- export a map package

The backend remains the Processing algorithm and the shared Python package under `src/`.

## Boundary Source Direction

The zonal layer can be supplied in two ways:

1. User selects an existing QGIS vector layer.
2. User selects a country and admin level, and the plugin fetches the boundary from ACMAD WFS.

The second path should use the ACMAD country information API to resolve metadata such as:

- country code, for example `NER`
- WFS URL or GeoServer base URL
- boundary layer/type name for admin level 0 or 1
- country-code field used by the WFS layer

The plugin can then build a WFS GetFeature URL such as:

```text
{wfs_url}?service=WFS&version=1.0.0&request=GetFeature&typeName={admin_layer}&outputFormat=application/json&CQL_FILTER={country_field}='NER'
```

This should return GeoJSON that QGIS can load as the zonal boundary layer. The implementation should keep this boundary-fetch step separate from the risk scoring algorithm so that later products can reuse the same boundary source.

Planned QGIS boundary parameters:

```text
Boundary source:
- Existing QGIS layer
- Fetch from ACMAD WFS

Country code:
- NER

Admin level:
- 0 country
- 1 first administrative level

Boundary cache:
- Use cached boundary if available
- Refresh from ACMAD WFS
```

## Runtime Note

The repository includes a local folder named `qgis/` for project integration files. QGIS itself also provides a Python package named `qgis`. For that reason, plugin code loads the local Processing provider through explicit local paths rather than importing it as `qgis.processing.provider`.

The plugin supports two runtime layouts:

- development mode, where `qgis/plugin` is symlinked into the QGIS profile and imports from the repository
- packaged mode, where the plugin zip contains `processing/` and `agroclimate_core/` inside the plugin folder
