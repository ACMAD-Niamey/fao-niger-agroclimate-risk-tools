# Releasing

*Last reviewed: 2026-10-13.* How to publish a new version of the QGIS plugin on GitHub. Releases so far are listed in the [changelog](../CHANGELOG.md).

## Versioning

[Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`. The project stays below 1.0 while the thresholds and class mapping are provisional.

- **Patch** (0.3.2 to 0.3.3): fixes and documentation.
- **Minor** (0.3.x to 0.4.0): new features or changed behaviour.
- **1.0.0**: when FAO and ACMAD have signed off the thresholds, class mapping and weights.

The version lives in one place that the code uses: `version=` in `qgis/plugin/metadata.txt`. QGIS shows it in the Plugin Manager, and the plugin reads it to show its one-time message once per release. Bump it for every release so users can tell builds apart.

## Steps

1. **Update the version and the changelog.**
   - Set `version=` and the `changelog=` line in `qgis/plugin/metadata.txt`.
   - In `CHANGELOG.md`, move the `[Unreleased]` entries under a new `## [X.Y.Z] - date` heading, and update the two links at the bottom.
   - Write `docs/releases/vX.Y.Z.md`, the text for the GitHub release page.
2. **Run both test suites.** They must pass.
   - System Python with GDAL: `PYTHONPATH=src:tests python3 -m unittest discover -s tests -t tests`
   - QGIS's Python, which also runs the plugin tests; see [implementation notes](implementation.md#testing-the-plugin) for the environment.
3. **Build the zip** and give it a versioned name:
   ```bash
   python3 scripts/build_qgis_plugin.py
   cp dist/qgis/fao_niger_agroclimate.zip dist/qgis/fao_niger_agroclimate-X.Y.Z.zip
   ```
   Check that `metadata.txt` inside it shows the right version and that it lists every plugin module. QGIS needs the folder inside the zip to be `fao_niger_agroclimate`; the file name itself can be anything.
4. **Commit, tag and push.**
   ```bash
   git commit -am "chore: release X.Y.Z"
   git tag -a vX.Y.Z -m "X.Y.Z"
   git push origin main vX.Y.Z
   ```
5. **Publish the release** with the zip attached, and add its SHA-256 so people can check their download:
   ```bash
   shasum -a 256 dist/qgis/fao_niger_agroclimate-X.Y.Z.zip
   gh release create vX.Y.Z dist/qgis/fao_niger_agroclimate-X.Y.Z.zip \
     --title "FAO Niger Agroclimate Risk Tools X.Y.Z" --notes-file docs/releases/vX.Y.Z.md
   ```
6. **Check it.** Download the zip from the release page and install it in QGIS from a clean state. Confirm the Plugin Manager shows the new version and the panel opens.

Build the zip from the tagged commit. `dist/` is not in git, so the zip on the release page is the only copy of exactly what was released.

## Before the first public use

- **A licence.** The repository has no licence file, so by default nobody else may legally reuse the code. Choose one with the owners (FAO and ACMAD) and add a `LICENSE` file.
- **The QGIS plugin repository** (plugins.qgis.org) is optional. It would let people install from inside QGIS without downloading a zip. It needs a licence and a clean metadata file.
