# Decision Log

Choices that shape the tools, with the reason. Newest at the bottom. "Confirm" means a person outside the code still needs to agree.

| # | Date | Decision | Why | Status |
| --- | --- | --- | --- | --- |
| D1 | 2026-10 | **Consume, don't compute.** Use ACMAD products as published for hazard, forecast and triggers; join them with open land cover. New indicators are future proposals. | Keeps the tools transparent and avoids duplicating ACMAD's validated science. | Agreed |
| D2 | 2026-10 | Build a script-first **raster** runner before wrapping it in QGIS. The earlier plan scored zonal vector units. | Raster output can be opened and checked in QGIS right away, and the plugin stays a thin wrapper over the same code. | Agreed |
| D3 | 2026-10 | Hazard comes from two products kept **separate**: the current CDI (dekadal, 0.1 degree) and the seasonal combined hazard (1 degree). | They differ in time and grid, so they cannot be summed into one score. | Agreed |
| D4 | 2026-10 | Do not add fAPAR or soil moisture anomaly into a composite hazard score. | CDI already combines precipitation, soil moisture and fAPAR, so the composite would count them twice. They remain possible as context layers. | Agreed |
| D5 | 2026-10 | One common output grid: the 0.1 degree CDI grid over Niger. The 1 degree hazard is repeated onto it, not interpolated. Exposure is aggregated to it as class fractions. | One exposure set serves both maps, and visibly blocky hazard cells do not claim detail the data lacks. | Agreed |
| D6 | 2026-10 | Exposure comes from ESA WorldCover read straight from AWS, not through Google Earth Engine. Cultivated = class 40; rangeland = classes 20 and 30. | No login, reproducible, cached. GEE stays an option. | Class choice: confirm with FAO |
| D7 | 2026-10 | Exposure score = share of a cell in the class, binned at 5%, 25% and 50% for both layers. | Needs a starting point so the pipeline runs. | **Placeholder: confirm with FAO** |
| D8 | 2026-10 | Score risk **only** where cropland or rangeland exposure is above zero. Other cells are "not applicable". Switch off with `--no-agropastoral-mask`. | The map is about agropastoral systems. Scoring bare ground "low" makes it look safe. | Agreed |
| D9 | 2026-10 | Download the **unmasked** CDI (`mask_nodata=false`). | The masked file treats "no drought" as no data and hides unaffected areas. | Agreed |
| D10 | 2026-10 | Pick input dates from ACMAD's catalogue. If the requested period is not published, use the latest one within 3 dekads, say so in the log and in `run_metadata.json`. `--strict-dates` refuses instead. An explicit `--year/--month` is always exact. | Publication lags by about a month, so "today" has no data. Silent substitution would mislabel the map. | Limit of 3: confirm |
| D11 | 2026-10 | Combined hazard classes 1-2 score 0, 3-4 score 1, 5-6 score 2, 7-9 score 3. | The named levels Watch (3), Warning (5) and Alert (7) each begin a bin; in-between classes join the lower bin. | **Proposal: confirm with ACMAD and FAO** |
| D12 | 2026-10 | Risk score is an additive weighted score: `0.6H + 0.4E`, or `0.5H + 0.3E + 0.2V` when vulnerability exists. `Hazard x Exposure x Vulnerability` is the concept, not the arithmetic. | A weighted sum is transparent and keeps a zero in one factor from erasing the others. | Confirm with FAO |
| D13 | 2026-10 | Map colours: ColorBrewer yellow-orange-red, darker with severity, grey for "no hazard", no red-green pairs. Class labels state the real breaks. | Ordered data needs ordered lightness; the ramp is colour-blind safe and survives greyscale printing. | Review in QGIS |
| D14 | 2026-10 | Summarise by admin unit using OCHA COD boundaries; a cell belongs to the unit holding its centre. | The official UN set with a suitable licence. Cell-centre assignment is simple but undercounts very small units (Niamey). | Agreed |

## Open questions

1. FAO and ACMAD to confirm D7, D11 and D12 (thresholds, class binning, weights).
2. Does ACMAD publish season start, dry spells or heat stress? Needed for the trigger deliverable.
3. Which water-point and vulnerability layers are acceptable?
4. Which format does FAO's Climate Intelligence-Agro system expect for outputs?
5. Is sparse vegetation (WorldCover 60) part of rangeland in the north?
