# Data Sources

Every external input the tools use, what it contains, and what we checked. Facts here were verified against the live services on **2026-10-12**. Availability changes over time, so check the "how to re-check" line before relying on a date.

## ACMAD products

All ACMAD calls go to `https://ada.acmad.org`.

### Combined Drought Indicator (CDI), dekadal

| | |
| --- | --- |
| Request | `GET /api/data_api/download_data/?data_name=cdi&year=Y&month=M&dekad=D&mask_nodata=false` |
| Grid | 0.1 degree, global (1800 x 3600), `int32`, nodata `-9999` |
| Values | Detailed codes 0 to 14: 0 no drought, 1-3 watch, 4-6 warning, 7-10 alert, 11-12 partial recovery, 13-14 full recovery |
| Dekad | `1`, `11` or `21`; the first day of the dekad, as in ACMAD file names |
| Publication lag | About one month. On 2026-10-12 the latest CDI was **2026-09-11** |
| How to re-check | `GET /api/data_api/rs_data/get_available_datasets/`, then read `cdi.latest_year`, `latest_month`, `latest_dekad` |

Two behaviours matter:

- **Always request `mask_nodata=false`.** With `true`, ACMAD turns code 0 ("no drought") into nodata, so every unaffected area drops out of the map. In September 2026 that hid 794 of 803 cropland cells, which simply had no drought.
- **A 202 "queued" answer does not mean the file exists.** Missing dates (future dates, invalid dekads) also return 202, and the job status address it gives returns 404. Decide availability from `get_available_datasets`, not from the download response. The per-year `months` and `dekads` lists in that catalogue are unreliable (they omit dekad 21 even where files exist); only the `latest_*` and `start_year` fields are used.

`cdi_era5` is a separate CDI product built on ERA5. On 2026-10-12 its latest was 2026-08-11, three dekads behind `cdi`.

### Combined monitoring and forecast hazard, seasonal

| | |
| --- | --- |
| Request | `GET /api/data_api/download_combined_product/?data_name=combined_drought_hazard_era5&forecast_period=SON&year=2026` |
| Grid | 1 degree over Africa (98 x 72, -25 to 73 E, -35 to 37 N), `uint8`, nodata `0` |
| Values | Classes 1 to 9 (legend below) |
| Description (from ACMAD) | `S = cdi_tier + forecast`: CDI monitoring fused with the combined ACMAD and UNWDC seasonal forecast, on the ERA5 CDI grid |
| Published | **SON 2026 only** on 2026-10-12 |
| How to re-check | `GET /api/data_api/rs_data/get_dataset_catalog/`, entry `combined_drought_hazard_era5`, field `available_periods` |

A missing period returns HTTP 404 with a JSON `error` such as "No combined_drought_hazard_era5 asset found for year=2026, period=JJA".

| Class | ACMAD label |
| --- | --- |
| 1 | No drought hazard |
| 2 | Very low |
| 3 | Low (Watch) |
| 4 | Low-moderate |
| 5 | Moderate (Warning) |
| 6 | Moderate-high |
| 7 | High (Alert) |
| 8 | Very high |
| 9 | Extreme |

The catalogue also lists `combined_drought_hazard_gpcc` (same product on the GPCC grid), `combined_drought_forecast_era5` and `combined_drought_forecast_gpcc`. The tools use the ERA5 hazard. The forecast products are not used yet; the ERA5 one has five classes from "Full-confidence wetter" to "Full-confidence drier" and is the natural input for the advisory and trigger products.

### Boundaries from ACMAD GeoServer

`https://ada.acmad.org/geoserver/wfs` serves Niger **admin level 0** as `data_api_adminlevelzero` with `country_code = 181`. It has **no admin level 1 layer**: the `data_api_adminlevelone` name the code once defaulted to is unknown to the server.

## Land cover: ESA WorldCover 2021 (v200)

| | |
| --- | --- |
| Source | Public AWS bucket `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/` |
| Files | One cloud-optimised GeoTIFF per 3 x 3 degree tile, named `ESA_WorldCover_10m_2021_v200_<N12E003>_Map.tif` |
| Resolution | 10 m, 8-bit classes, nodata `0` |
| Classes used | 40 cropland (cultivated exposure); 20 shrubland and 30 grassland (rangeland exposure) |
| Not used | 60 sparse vegetation. Pastoral use in the northern Sahel may need it; to be reviewed with FAO |
| Licence | CC BY 4.0. Credit ESA WorldCover on maps |
| Access | No login. Needs no Google Earth Engine account |

## Administrative boundaries

| Source | Units | Licence | Use |
| --- | --- | --- | --- |
| **OCHA Common Operational Dataset (HDX, `cod-ab-ner`)** | 8 regions, admin levels 0 to 3 | CC BY-IGO | **Recommended.** Updated 2026-01-26. Name field `adm1_name`, code field `adm1_pcode` (NE001 to NE008) |
| geoBoundaries `gbHumanitarian` / `gbAuthoritative` | 8 | Humanitarian / UN SALB | Acceptable fallback; older |
| geoBoundaries `gbOpen` | 6 (merged regions) | ODbL | Not suitable |
| GADM 4.1 | 8 | Non-commercial only | Avoid for FAO work |

Credit OCHA when publishing maps made with the COD boundaries.

## Shared storage (MinIO)

Prepared exposure rasters and the cached land cover windows are stored in the project MinIO bucket under `fao-niger-agroclimate/niger/`:

- `exposure/`: four small rasters (cultivated and rangeland, fraction and score)
- `landcover/worldcover_2021/`: 22 land cover windows covering Niger, about 430 MB

Connection settings come from `.env` (`MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`); see `.env.example`. Never commit `.env`.

## Not yet integrated

| Need | Candidate | Status |
| --- | --- | --- |
| Water points | National or OpenStreetMap boreholes and wells; JRC surface water as a proxy | No source chosen. The runner uses a constant default score |
| Vulnerability | Food security or poverty layer | No source chosen |
| Crop calendar | National calendar | Not available |
| Season start, dry spells, heat stress | ACMAD, if published | Not checked. Out of scope under "consume, don't compute" unless ACMAD provides them |
