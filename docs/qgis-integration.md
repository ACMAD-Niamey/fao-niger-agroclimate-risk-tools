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
| `qgis/processing/fetch_acmad_boundary.py` | QGIS Processing algorithm to fetch Niger boundary layers from ACMAD WFS. |
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

The risk algorithm now exposes the zonal boundary source directly:

```text
Zonal boundary source:
- Use existing QGIS vector layer
- Fetch Niger boundary from ACMAD WFS
```

When the ACMAD WFS option is selected, the tool fetches the Niger boundary geometry using:

```text
typeName = data_api_adminlevelzero
CQL_FILTER = country_code=181
```

The fetched boundary still needs CDI and exposure fields before risk scoring can run. Until the overlay/join workflow is implemented, users should either select an existing layer that already contains the scoring fields or fetch the boundary first and then join/calculate the required fields.

The algorithm adds:

```text
hazard_score
exposure_score
risk_score
risk_class
```

The boundary fetch algorithm is:

```text
Fetch ACMAD Boundary Layer
```

It exposes the API/WFS boundary option in QGIS. Use it before the risk algorithm when the user does not want to provide a local zonal vector layer.

Parameters:

```text
ACMAD GeoServer/WFS URL, defaults to https://ada.acmad.org/geoserver
GeoServer workspace, optional
Boundary admin level
Override WFS typeName/layer name (optional)
Boundary output
```

The URL remains editable. The code normalizes `https://ada.acmad.org/geoserver` to `https://ada.acmad.org/geoserver/wfs` when building the WFS GetFeature request. If a workspace is provided, the layer name is qualified as `workspace:layer_name`; if the layer name already includes a workspace, it is left unchanged.

Tested Niger admin-0 request:

```text
https://ada.acmad.org/geoserver/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=data_api_adminlevelzero&outputFormat=application/json&CQL_FILTER=country_code='181'
```

The endpoint returns GeoJSON for Niger. The QGIS tool loads the WFS URL directly through QGIS/GDAL rather than Python `urllib`, avoiding local Python certificate-store issues.

For Niger admin level 0, it defaults to:

```text
typeName = data_api_adminlevelzero
CQL_FILTER = country_code=181
```

For Niger admin level 1, it currently defaults to:

```text
typeName = data_api_adminlevelone
CQL_FILTER = country_code=181
```

The admin level 1 layer name should still be validated against ACMAD WFS capabilities or country information API metadata.

## Expected Workflow

1. Prepare or load a zonal input layer in QGIS.
2. If no local zonal layer is available, run `Fetch ACMAD Boundary Layer` to create one from ACMAD WFS.
3. Ensure the zonal layer contains CDI, optional fAPAR anomaly, optional soil moisture anomaly, and exposure fields.
4. Run the risk Processing algorithm.
5. Review the output risk classes.
6. Apply QGIS styles and export maps/tables.

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
2. User runs the `Fetch ACMAD Boundary Layer` algorithm to create a boundary layer from ACMAD WFS.

The second path should use the ACMAD country information API to resolve metadata such as:

- country code, for example Niger uses `country_code = 181`
- WFS URL or GeoServer base URL
- boundary layer/type name for admin level 0 or 1
- country-code field used by the WFS layer

The plugin can then build a WFS GetFeature URL such as:

```text
{wfs_url}?service=WFS&version=1.0.0&request=GetFeature&typeName={admin_layer}&outputFormat=application/json&CQL_FILTER=country_code=181
```

This should return GeoJSON that QGIS can load as the zonal boundary layer. The implementation should keep this boundary-fetch step separate from the risk scoring algorithm so that later products can reuse the same boundary source.

From the current ACMAD country boundary layer, admin level 0 uses:

```text
Layer: data_api_adminlevelzero
Country field: country_code
Niger country_code: 181
Niger country_name: Niger
Region: Western Africa
region_code: 6
```

Admin level 1 should follow the same pattern once its exact layer name is confirmed. The code currently defaults to `data_api_adminlevelone`, but that should be validated against the ACMAD WFS capabilities or country information API response.

Planned QGIS boundary parameters:

```text
Boundary source:
- Existing QGIS layer
- Fetch from ACMAD WFS

ACMAD WFS URL:
- https://ada.acmad.org/geoserver

GeoServer workspace:
- optional

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
