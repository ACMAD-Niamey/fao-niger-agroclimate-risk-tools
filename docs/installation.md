# Installing the QGIS Plugin

*Last reviewed: 2026-10-13.* For people who will use the plugin. To open and use it, see [using the panel](using-the-panel.md).

## What you need

- **QGIS 3.28 or later.** The plugin runs on the Python that QGIS ships; nothing else needs installing.
- **An internet connection** when you run a map. The plugin reads ACMAD's published periods and hazard data. If you build exposure from land cover yourself instead of using ACMAD's prepared files, that needs internet too.
- About 10 MB of disk space for a full set of outputs (more if you build exposure from land cover, which caches about 430 MB).

It has been used on macOS. It should work the same on Windows and Linux, but that has not been tried.

## Install

1. Go to the [Releases page](https://github.com/ACMAD-Niamey/fao-niger-agroclimate-risk-tools/releases) and download `fao_niger_agroclimate-<version>.zip` from the latest release. **Do not unzip it.**
2. In QGIS, open `Plugins > Manage and Install Plugins > Install from ZIP`, choose the file, and press **Install Plugin**.
3. Make sure the plugin is ticked in the **Installed** tab. It is listed as *FAO Niger Agroclimate Risk Tools*.
4. Check the version shown matches the file you downloaded.
5. **Restart QGIS** if you are replacing an older version. QGIS keeps the old code loaded until it restarts.

QGIS then shows a message with an **Open the risk panel** button. You can also open the panel from the toolbar icon, from `Plugins > FAO Niger Agroclimate`, or from the first entry of the *FAO Niger Agroclimate* group in the Processing Toolbox.

## Update

Install the new zip over the old one in the same way, then restart QGIS. Your settings (output folder, ticked options, language model address) are kept. The language model key is kept only if you ticked "Remember the key".

## Uninstall

`Plugins > Manage and Install Plugins > Installed`, select the plugin, and press **Uninstall Plugin**. Your output folder is not deleted.

## Where files go

Everything the plugin writes goes under one **output folder** (shown on the Run tab; the default is `fao_niger_agroclimate_outputs` in your home folder):

```text
fao_niger_agroclimate_outputs/
  exposure/                       cropland and rangeland exposure, fetched once
    cultivated_exposure.tif, rangeland_exposure.tif      the 0-3 scores
    cultivated_fraction.tif, rangeland_fraction.tif      the share of each cell
    exposure_source.json                                 where they came from (with checksums)
  boundaries/                     Niger's admin level 1 regions, fetched for the region summary
    niger_admin1_ocha.geojson, niger_admin1_source.json
  niger-risk-2026-09-11/          one folder per map, named after the period actually used
    agropastoral_risk_class.tif, agropastoral_risk_score.tif, agropastoral_risk_stack.tif
    cdi_niger.tif (or combined_hazard_niger.tif)          the hazard, clipped to Niger
    run_metadata.json                                    what the map was built from
    admin_risk_summary.csv, admin_risk_summary.geojson   after "Summarise by region"
  cache/worldcover/               only if you built exposure from land cover
```

The map layers in QGIS point at these files, so keep them while a project uses them. They are ordinary GeoTIFF and GeoJSON files that any GIS can open.

## What the plugin downloads, and from where

| What | From | Size | When |
| --- | --- | --- | --- |
| The list of published periods | ACMAD (`ada.acmad.org`) | a few KB | When you open the panel or press Refresh |
| The hazard for the period you map | ACMAD | about 1 MB | Each run |
| Niger's country outline | ACMAD's GeoServer | about 65 KB | Each run |
| Prepared exposure | ACMAD's storage (`minio.acmad.org`) | about 66 KB | Once, on the first run |
| Niger's 8 regions | ACMAD's storage | about 180 KB | When you press *Summarise by region* |
| Land cover (only if you untick *Use ACMAD's prepared exposure*) | ESA WorldCover on AWS | about 430 MB | Once |
| A description of the results (only if you set up a language model) | The service you configure | summary figures only | When you press *Describe* |

Nothing else is sent anywhere, and nothing is uploaded except to a language model service you set up yourself. See [language model](language-model.md) for exactly what that sends.

If something does not work, see [troubleshooting](troubleshooting.md).
