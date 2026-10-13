# Troubleshooting

*Last reviewed: 2026-10-13.* Find the message or symptom, and what to try. For the language model, the table in [language model](language-model.md) has more.

## Finding and opening the panel

| Symptom | What to try |
| --- | --- |
| I cannot find the panel | Use the **Open the risk panel** button in the message QGIS shows when it loads the plugin, or the first entry of the *FAO Niger Agroclimate* group in the Processing Toolbox (*Agroclimate Risk panel*), or `Plugins > FAO Niger Agroclimate > Open Agroclimate Risk Panel`, or the toolbar icon (tick `View > Toolbars > Plugins Toolbar` if you cannot see it) |
| The Processing Toolbox only shows tools that ask for zones, fields and scores | Those are the older, advanced vector tools. They do not build the map. Open the panel instead |
| The panel looks like an older version | `Plugins > Manage and Install Plugins > Installed` shows the version. Reinstall the newest zip and **restart QGIS**: QGIS keeps old code loaded until it restarts |
| A red message says part of the plugin could not load | It names the part. The details are in `View > Panels > Log Messages`, tab *FAO Niger Agroclimate*. Send that text with your report |
| Part of the panel is cut off | Every tab scrolls: use the scroll bar on its right. You can also make the panel taller or wider |

## Running a map

| Message or symptom | What it means and what to try |
| --- | --- |
| The Period list only has "Other date…", and a note says it could not read the periods | The plugin could not reach ACMAD. Check your connection and press **Refresh**. You can still pick "Other date…" and type a date |
| An orange note says the period shown is older than requested | You typed a date that ACMAD has not published yet (publication lags by about a month), so the latest published period was used. This is normal. Pick a period from the list to avoid it |
| *ACMAD has no data for this period* | That period is not published. Press **Refresh** and choose one from the list |
| *Could not reach ACMAD…* during a run | Your internet connection, or ACMAD's server is down. Try again in a few minutes |
| A dialog says exposure data is needed | See *Exposure* below |
| The whole map is "low" | That can be true: in September 2026 about 95% of the scored area was low. Open the CDI hazard layer to see where ACMAD reports drought |
| Large parts of Niger are blank | Blank cells are not scored. They are outside cropland and rangeland (mostly the north), or ACMAD has no value there. They are not "low risk". See [reading the maps](reading-the-maps.md) |
| The seasonal outlook looks blocky | It is a 1 degree product, so its cells are about 110 km wide. Nothing is interpolated |
| A run seems stuck | Long steps (ACMAD's download) show in the log under the progress bar. **Cancel** stops it between steps |

## Exposure

| Message or symptom | What to try |
| --- | --- |
| *Could not reach ACMAD's server to get the prepared exposure* | Check your connection and try again, or untick **Use ACMAD's prepared exposure** to build it from land cover instead (about 5 minutes and 430 MB, once) |
| *ACMAD's server does not have …*, or a file has values outside its range | ACMAD's prepared files are missing or wrong. Untick **Use ACMAD's prepared exposure**, and tell the maintainers |
| "No exposure rasters in this folder yet" | Press **Get exposure from ACMAD**, or run and choose **Prepare exposure, then run**. Or point the folder box at a folder that already has `cultivated_exposure.tif` and `rangeland_exposure.tif` |
| The results say "No cropland and rangeland mask was applied… Treat this as a test" | You chose **Run as a test anyway**, or unticked *Map only cropland and rangeland*. Prepare exposure for a real run |
| Building from land cover is slow | It downloads about 430 MB once and takes around 5 minutes; later runs reuse it. ACMAD's prepared files take seconds |

## The region summary

| Message or symptom | What to try |
| --- | --- |
| The table shows only a few columns | The table scrolls sideways. Press **Larger table (copy to a spreadsheet)** for every column in a window of its own |
| I want the numbers in a spreadsheet | Open the larger table and press **Copy table**, then paste. The same figures are in `admin_risk_summary.csv` in the map's folder (**Open results folder**) |
| *Could not reach ACMAD's server to get the regions* | Check your connection, or untick **Use ACMAD's admin level 1 regions** and pick a polygon layer of your own |
| Nothing happens when I press the button with my own layer | The layer must be loaded in QGIS and be a polygon layer, and you must choose its **name** field |
| Niamey's figures look odd | Niamey is a very small region (a few cells on a 0.1 degree grid), so its figures are rough. Treat them with care |

## Text and display

| Symptom | What to try |
| --- | --- |
| Spaces after commas and full stops look squeezed together | This is a Qt drawing quirk with the macOS system font in QGIS 3.28. It does not change the text or the results |
| The map colours look different from the legend | Check you are looking at the **Risk class** layer, and not the hazard layer or the score layer. Each has its own colours; see [reading the maps](reading-the-maps.md) |

## Reporting a problem

Please send:

1. The **plugin version** (`Plugins > Manage and Install Plugins > Installed`) and the **QGIS version** (`Help > About`), and your operating system.
2. The **exact message** you saw (copy the text; a screenshot is fine too).
3. The text in `View > Panels > Log Messages`, tab *FAO Niger Agroclimate*.
4. If a map was built, the map folder's `run_metadata.json`. It records which periods and files were used, and contains no secrets.

**Never send an API key.** The plugin's messages do not contain your key, and neither does `run_metadata.json`.

Open an issue at <https://github.com/ACMAD-Niamey/fao-niger-agroclimate-risk-tools/issues>.
