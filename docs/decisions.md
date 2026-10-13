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
| D15 | 2026-10 | The end-to-end run lives in `agroclimate_core.workflow`. The script and the QGIS plugin are thin shells over it. | One implementation cannot drift between the command line and QGIS, and the script stays usable on its own. | Agreed |
| D16 | 2026-10 | The plugin runs workflows in a background `QgsTask`, with progress and cancellation, and adds results to the map itself. | Runs take seconds to minutes; the interface must stay responsive. | Agreed |
| D17 | 2026-10 | The language model is optional and off by default. It only phrases results, receives a fixed allow-list of summary figures after the user confirms the host, and every reply is marked as a draft for expert review. The key stays in memory unless the user chooses to remember it. | Keeps decisions with the rules and experts, and keeps data and credentials under the user's control. | Agreed |
| D18 | 2026-10 | Support Python 3.9. | QGIS 3.28 LTR bundles Python 3.9 and GDAL 3.3, and the plugin runs inside it. | Agreed |
| D21 | 2026-10 | The language model answer is streamed, and the request is bounded to 2000 tokens. Reasoning-model options go in an optional "Extra request fields" JSON setting, not in the defaults. | A gateway can cut a silent request at about a minute, and a reasoning model can think for longer than that; streaming keeps data flowing. Turning thinking off needs a field some services reject (OpenAI refuses unknown fields), so it is opt-in. | Agreed |
| D19 | 2026-10 | The panel gets exposure from ACMAD's prepared files by default (a few seconds); building it from WorldCover is the option behind an unticked box. The downloaded files are validated structurally and their hashes recorded, not pinned in the code. | A new user should reach a real map in seconds, not after 430 MB and 5 minutes. Pinning hashes would force a plugin release for every exposure update, while checking range, grid and format still rejects a wrong or partial file. The prepared files carry the provisional thresholds, so they must be republished when FAO and ACMAD confirm them. | Agreed |
| D20 | 2026-10 | The region summary uses ACMAD's published copy of the OCHA admin level 1 regions by default, and keeps the choice of any polygon layer behind an unticked box. | Summarising by region should be one click for a new user, with no file to find or load, and the data is open (CC BY-IGO) and tiny. Keeping the user's own layer as an option avoids locking users to one set of regions. | Agreed |

## Open questions

1. FAO and ACMAD to confirm D7, D11 and D12 (thresholds, class binning, weights).
2. Does ACMAD publish season start, dry spells or heat stress? Needed for the trigger deliverable.
3. Which water-point and vulnerability layers are acceptable?
4. Which format does FAO's Climate Intelligence-Agro system expect for outputs?
5. Is sparse vegetation (WorldCover 60) part of rangeland in the north?
6. **CDI code bins.** ACMAD's WMS legend gives watch = 1 to 4, warning = 5 to 7, alert = 7 to 10, no drought = 0, and lists nothing for 11 to 14. The tools bin 1-3 / 4-6 / 7-10 and treat 11-12 as partial and 13-14 as full recovery. Which is authoritative for codes 4 and 7, and what do 11 to 14 mean? (Raised 2026-10-13; the tools have not been changed.)
