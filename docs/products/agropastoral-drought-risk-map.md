# Agropastoral Drought Risk Map

*Last reviewed: 2026-10-12. Status: prototype running on real data; thresholds awaiting review.*

## Purpose

The map shows where drought hazard, as published by ACMAD, overlaps cropland and rangeland in Niger. It is a screening tool to decide where to look first, and where monitoring, advisories or anticipatory action discussions deserve attention.

It answers:

- where drought conditions threaten cultivated or grazed land
- which regions have the largest share of their agropastoral land at high risk
- how much cropland and rangeland sits in high-risk cells

It does not predict yield or livestock losses, and it does not replace ACMAD's own drought maps.

## Primary users

- FAO Niger technical staff
- National meteorological and agricultural counterparts
- Food security and early warning partners
- Field teams supporting agricultural and pastoral advisory work

## Design rule

Hazard is taken from ACMAD's published products and used as they are. The product adds exposure from land cover and the overlay. It does not compute new climate indicators; those are listed under [future extensions](#future-extensions).

## Inputs

| Input | Source | Role |
| --- | --- | --- |
| Combined Drought Indicator (CDI), dekadal, 0.1 degree | ACMAD | **Current** hazard |
| Combined monitoring and forecast hazard, seasonal, 1 degree | ACMAD | **Seasonal outlook** hazard |
| Cropland (class 40) | ESA WorldCover 2021 | Cultivated exposure |
| Shrubland and grassland (classes 20, 30) | ESA WorldCover 2021 | Rangeland exposure |
| Administrative boundaries | OCHA Common Operational Dataset | Regional summaries |
| Water points | None chosen yet | Constant default until a source exists |
| Vulnerability | None chosen yet | Not used in the raster path |

The sources, formats and what was verified are in [data sources](../data-sources.md).

The CDI and the combined hazard are used as **two separate maps**. They differ in time (dekad against season) and grid (0.1 against 1 degree), so they are not added together.

## Processing logic

1. **Choose the period.** The requested date is mapped to the CDI dekad or the seasonal period and checked against what ACMAD has published. ACMAD publishes about a month behind, so the latest period within three dekads is used when the requested one is missing, and the run says so. `--strict-dates` refuses instead.
2. **Hazard score, 0 to 3.**
   - CDI codes: no drought or full recovery 0; watch or partial recovery 1; warning 2; alert 3 (full mapping in [implementation notes](../implementation.md#method)).
   - Combined hazard classes 1 to 9: 1-2 score 0, 3-4 score 1, 5-6 score 2, 7-9 score 3. **A proposal; to be confirmed with ACMAD and FAO.**
3. **Exposure score, 0 to 3.** For each cell, the share of land cover in the class, binned at 5%, 25% and 50%. **Placeholder cut-offs.**
4. **Risk score and class** from the formulas below.
5. **Mask.** Only cells with cropland or rangeland are scored. Elsewhere the map is blank ("not applicable"), because scoring bare ground low would make it look safe.

All outputs share one grid, the 0.1 degree CDI grid over Niger. The 1 degree hazard is repeated onto it, so those cells look blocky; that is the true resolution of the data.

## Formulas and classes

```text
Exposure = 0.45 cultivated + 0.35 rangeland + 0.20 water points
Risk     = 0.60 Hazard + 0.40 Exposure
```

Where a vulnerability layer exists, the vector scoring path uses `0.50 Hazard + 0.30 Exposure + 0.20 Vulnerability`. The raster path does not yet.

`Risk = Hazard x Exposure x Vulnerability` is the conceptual framing (IPCC AR6), not the arithmetic. A weighted sum is used because it is transparent and a zero in one factor does not erase the others.

| Class | Score |
| --- | --- |
| Low | below 1.0 |
| Moderate | 1.0 to below 1.7 |
| High | 1.7 to below 2.4 |
| Very high | 2.4 and above |

## Outputs

| Output | State |
| --- | --- |
| Risk score and risk class rasters, hazard and exposure stack, QGIS styles | Available |
| `run_metadata.json` (requested date, period used, fallback, inputs) | Available |
| Summary table by admin region (class shares, mean score, worst class, exposed hectares), CSV and GeoJSON | Available |
| Print-ready layout, FAO intervention-zone summary, water points in high-risk zones | Planned |

## Update frequency

The CDI updates every dekad (about every ten days) with a lag of about a month. The seasonal hazard updates once per season. Exposure is static and is rebuilt only if the land cover class choice, thresholds or grid change.

## Quality control

Before using a map, check:

- the period in `run_metadata.json` matches what you intended, and `fallback` is understood
- hazard and exposure share the grid (the runner enforces this)
- risk scores fall within 0 to 3 (the runner enforces this)
- regional totals look sensible against ACMAD's own map for the same period
- the style reads clearly in QGIS

## Known limitations

- Cut-offs, class mapping and weights are placeholders until FAO and ACMAD review them.
- Water-point exposure is a constant, and vulnerability is not applied to the raster.
- The seasonal hazard is 1 degree; the CDI is about 11 km. Units smaller than a few cells, such as Niamey, are poorly represented.
- Land cover is a 2021 snapshot. Sparse vegetation (class 60), grazed in parts of the north, is not counted as rangeland.
- The score is a screening tool and should be validated against local knowledge and past seasons.

## Future extensions

These add information beyond what ACMAD publishes, so they stay proposals under the design rule:

- fAPAR and soil moisture anomaly as context layers (not added into hazard, because the CDI already combines them)
- NDVI anomaly, surface water change, heat stress, start of season
- A vulnerability layer in the raster path
- The combined drought forecast (`combined_drought_forecast_era5`) as an input to advisories and triggers

## Handover notes

Keep the method transparent and repeatable. Anyone should be able to rerun a map from `run_metadata.json` plus the command. Review thresholds and class mapping with counterparts before the product is used for decisions.
