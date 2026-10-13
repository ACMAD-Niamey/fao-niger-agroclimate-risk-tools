# Project Plan and Status

*Last reviewed: 2026-10-13.*

This page says what the project has to deliver, how far each part has come, and what is next. It is organised around the four deliverables in the terms of reference. The design principle is [consume, don't compute](decisions.md): use ACMAD's published products as they are and add the overlay with land cover, not new indicators.

## The four deliverables

| # | Deliverable | Approach | Status |
| --- | --- | --- | --- |
| 1 | **Spatial risk maps** combining drought hazard with cultivated areas, rangelands and water points | ACMAD CDI and combined hazard as hazard; WorldCover as exposure | **Prototype working** |
| 2 | **Forecast-based advisory** (crop calendars, seasonal notices) in QGIS-based tools | ACMAD seasonal forecast to rule-based advisory text; an LLM may phrase the text but never decides | Planned |
| 3 | **Training and knowledge transfer** for FAO staff and counterparts | User guide, exercises, short trainings | Planned |
| 4 | **Triggers for anticipatory action** | Watch, Warning and Alert thresholds on ACMAD products, with maps and tables | Planned |

## Deliverable 1: what exists

The Agropastoral Drought Risk Map is the first product. The prototype does the following.

1. Chooses the CDI dekad or the seasonal period from what ACMAD has published, falling back to the latest period within a limit and recording that.
2. Downloads the hazard (CDI, or the seasonal combined hazard) and clips it to Niger.
3. Prepares cultivated and rangeland exposure from ESA WorldCover on the same grid, as the share of each cell in the class.
4. Scores risk as `0.6 x hazard + 0.4 x exposure`, in four classes, only over cells with cropland or rangeland.
5. Writes GeoTIFFs for QGIS and a `run_metadata.json` recording what the map was built from.
6. Summarises risk by admin region: class shares, mean score, worst class, and cropland and rangeland hectares in high-risk cells.
7. Runs from a **QGIS panel**: runs in the background, adds the styled layers to the map, shows class statistics and a region table, and can optionally ask a language model to describe the results. The command-line script runs the same workflow.

Checked on real data on 2026-10-12: the current CDI (period 2026-09-11, used because October is not yet published) and the seasonal outlook (SON 2026), with exposure for all 10,376 cells in Niger and OCHA admin level 1.

### Not yet true of the prototype

- **Thresholds and class mapping are placeholders.** Exposure cut-offs (5%, 25%, 50% of a cell), the 1-9 to 0-3 hazard mapping and the weights have not been reviewed by FAO or ACMAD. See the open items in the [decision log](decisions.md).
- **Water-point exposure is a constant** (score 1). No water-point source has been chosen.
- **Vulnerability is not in the raster path.** The `0.5H + 0.3E + 0.2V` formula exists only in the vector scoring code.
- **Resolution is coarse.** The CDI is about 11 km. The seasonal hazard is 1 degree, so its cells repeat on the 0.1 degree grid. Very small units such as Niamey (361 km² on the grid, 557 km² officially) are poorly represented.
- **The panel has had limited real-world use.** It was tested by driving it in headless QGIS 3.28 with real data, and the project developer has used it in QGIS 3.28 on macOS and reported it working well (2026-10-13). It has not been tried on Windows or Linux, and FAO staff have not used it yet.
- **The language model description is untested against a real service.** The protocol and safeguards are tested with a fake service.

## Next steps

1. Review thresholds, class mapping and weights with FAO and ACMAD; move them into one configuration file.
2. Try the released plugin (0.3.2) with FAO staff and adjust the styles and wording from their feedback.
3. Choose water-point and vulnerability sources. Republish ACMAD's prepared exposure once the cut-offs are confirmed.
4. Raise the straight data edge in the CDI near 12.1 degrees east with ACMAD (see [data sources](data-sources.md)).
5. Deliverable 2: use the `combined_drought_forecast_era5` product (five classes, wetter to drier) with a message library to draft advisories.
6. Deliverable 4: define trigger rules over CDI, combined hazard and exposure, and test them on past seasons.
7. Deliverable 3: write the user guide while the workflow settles.

## Open questions

Tracked in the [decision log](decisions.md#open-questions): threshold sign-off, season start and heat stress availability, water-point and vulnerability layers, the output format FAO's monitoring system needs, and whether sparse vegetation counts as rangeland.

## Where to look

- Inputs and what was verified: [data sources](data-sources.md)
- Product specification: [Agropastoral Drought Risk Map](products/agropastoral-drought-risk-map.md)
- Full design of all seven products: [technical note](technical-note.md)
