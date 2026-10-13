# Reading the Risk Maps

*Last reviewed: 2026-10-13.* For people who open the outputs in QGIS, whether through the plugin panel or by hand. The method behind them is in the [implementation notes](implementation.md#method).

## What the map shows

Where drought hazard published by ACMAD sits on cropland or rangeland in Niger. It is a screening tool: it tells you where to look first. It does not forecast crop yield or livestock losses, and the thresholds behind it are still placeholders awaiting review by FAO and ACMAD.

## In the QGIS panel

Press **Run and add to map**. A group named `Agropastoral risk - <period>` appears at the top of the Layers panel with three layers:

| Layer | Shown | What it is |
| --- | --- | --- |
| Risk class | on | The four classes |
| Risk score | off | The continuous 0 to 3 score |
| CDI hazard score, or Combined hazard | off | The hazard on its own: for the CDI, the 0-3 score (watch, warning, alert); for the seasonal outlook, ACMAD's nine classes |

The **Results** tab gives the area and share of each class, the mean score, and a table by region once you pick a region layer. If the date you asked for was not published yet, an orange note says which period the map shows instead.

## Which file to open

Each run writes a folder `outputs/niger-risk-<period>/`.

| File | Use it to |
| --- | --- |
| `agropastoral_risk_class.tif` | See the four classes. Start here |
| `agropastoral_risk_score.tif` | See the continuous score, 0 to 3 |
| `agropastoral_risk_stack.tif` | See why a cell scores as it does. Four bands: 1 hazard score, 2 exposure score, 3 risk score, 4 risk class |
| `combined_hazard_niger.tif` | See the seasonal outlook alone, in ACMAD's nine classes |
| `cdi_niger.tif` | The raw CDI codes (0 to 14). It is not on the 0-3 scale, so the CDI hazard style does not fit it; use band 1 of the stack for the 0-3 hazard score |
| `run_metadata.json` | Check which period and inputs the map was built from |

If you open a file by hand, select the layer and use `Plugins > FAO Niger Agroclimate` to apply the matching style.

## The four classes

| Class | Colour | Score | Reading |
| --- | --- | --- | --- |
| Low | pale yellow | below 1.0 | No hazard, or little hazard on little farmland or rangeland |
| Moderate | light orange | 1.0 to below 1.7 | Some drought signal on land that matters |
| High | orange | 1.7 to below 2.4 | Warning or alert hazard on exposed land |
| Very high | red | 2.4 and above | Alert hazard on heavily exposed land |

The colours get darker as risk rises.

## The score

The score runs from **0 to 3**:

```text
Risk = 0.60 x Hazard + 0.40 x Exposure
```

- **Hazard** is ACMAD's class, scored 0 (no drought), 1 (watch), 2 (warning), 3 (alert).
- **Exposure** is how much of the cell is cropland or rangeland, scored 0 to 3. A cell with at least half its area in one class scores 3 for that class.

The hazard sets the band and exposure moves a cell within it:

| Hazard | Result |
| --- | --- |
| 0, none | Low |
| 1, watch | Low if exposure is under 1.0; moderate above that |
| 2, warning | Moderate if exposure is under 1.25; high above that |
| 3, alert | High if exposure is under 1.5; very high above that |

So a high score means hazard and exposure coincide. It does not by itself mean the drought is severe: an alert over very sparse land can score lower than a watch over dense cropland. To see which one drives a cell, open the stack and compare band 1 (hazard) with band 2 (exposure).

## Blank areas

A blank (transparent) cell is **not scored**. It is not "low risk". Cells are blank when:

- they lie outside Niger,
- ACMAD has no hazard value there, or
- they hold no cropland or rangeland. Most of the north is blank for this reason. The map covers agropastoral systems, and scoring bare ground "low" would make it look safe.

Sparse vegetation in the northern Sahel is not counted as rangeland, so some grazed land there is blank. This is a known gap.

## Which period you are looking at

- The folder name and `run_metadata.json` give the period **actually used**. ACMAD publishes about a month behind, so a map asked for today often shows the latest published dekad. `run_metadata.json` says `"fallback": true` and gives the lag when that happens.
- **Current CDI map** (`cdi_niger.tif`): conditions in one ten-day period, at about 11 km resolution.
- **Seasonal outlook** (`combined_hazard_niger.tif`): ACMAD's combined monitoring and forecast hazard for a whole season, at 1 degree. Its cells appear as large blocks of about 110 km because that is the real resolution of the data. Nothing is interpolated.
- Do not compare the two maps cell by cell. They differ in time span and detail. Read the current CDI map as "what is happening now" and the seasonal outlook as "what the season is expected to bring".

## Region summaries

`admin_risk_summary.csv` and `.geojson` summarise a map by region. Only scored cells count, so empty desert does not dilute a region's average.

| Column | Meaning |
| --- | --- |
| `cells_scored`, `scored_area_km2` | How much of the region is cropland or rangeland that was scored |
| `mean_risk_score` | Average score, weighted by area |
| `max_risk_class` | The worst class present in the region |
| `pct_low`, `pct_moderate`, `pct_high`, `pct_very_high` | Share of the scored area in each class |
| `high_risk_area_km2` | Area in the high and very high classes |
| `cultivated_ha_total`, `rangeland_ha_total` | Cropland and rangeland in the region |
| `cultivated_ha_high_risk`, `rangeland_ha_high_risk` | Cropland and rangeland inside high and very high cells |

Treat very small regions with care. Niamey has only a few cells at this resolution (361 km² on the grid against 557 km² officially), so its figures are rough.

## Cautions

- Class breaks, exposure cut-offs, the hazard mapping and the weights are placeholders until FAO and ACMAD review them. Use the pattern, not a single cell's class, for decisions.
- Water-point exposure is a constant, and vulnerability is not used.
- Check the picture against local knowledge and ACMAD's own drought map for the same period.
- Land cover is a 2021 snapshot.
