from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np

import qgis_support
from agroclimate_core.workflow import RunConfig, run_risk_workflow
from helpers import write_raster
from test_workflow import fake_services

STYLES_DIR = qgis_support.REPO_ROOT / "qgis" / "styles"


def _load_styles_module():
    spec = importlib.util.spec_from_file_location("plugin_styles", qgis_support.REPO_ROOT / "qgis" / "plugin" / "styles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StyleColourTests(unittest.TestCase):
    """Pure Python: runs everywhere."""

    def test_risk_class_colours_come_from_the_style_file_the_map_uses(self):
        styles = _load_styles_module()
        colours = styles.class_colors(STYLES_DIR / "risk_class.qml")
        self.assertEqual(sorted(colours), [1, 2, 3, 4])
        self.assertEqual(colours[1][0], "Low (< 1.0)")  # XML entities are decoded
        self.assertEqual(colours[4][1], "#e31a1c")

    def test_missing_style_is_a_clear_error(self):
        styles = _load_styles_module()
        with self.assertRaises(FileNotFoundError):
            styles.style_file(STYLES_DIR, "nope.qml")


class AddRunToProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        qgis_support.init_qgis()
        cls.plugin = qgis_support.load_plugin_package()
        from fao_niger_agroclimate import layers

        cls.layers = layers

    def setUp(self):
        from qgis.core import QgsProject

        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        from helpers import write_boundary

        self.services, _ = fake_services(self.root, boundary=write_boundary(self.root / "b.geojson"))
        self.project = QgsProject()

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, **overrides):
        values = dict(output_dir=self.root / "run", analysis_date=date(2026, 10, 12))
        values.update(overrides)
        return run_risk_workflow(RunConfig(**values), services=self.services)

    def test_cdi_run_adds_a_styled_group_with_the_risk_class_on_top(self):
        result = self._run()
        added = self.layers.add_run_to_project(result, self.project, STYLES_DIR)
        self.assertEqual(added.warnings, [])
        root = self.project.layerTreeRoot()
        group = root.findGroup("Agropastoral risk - 2026-09-11")
        self.assertIsNotNone(group)
        self.assertIs(root.children()[0], group)  # first in the tree, so drawn on top
        self.assertEqual([n.name() for n in group.children()][0], "Risk class (2026-09-11)")

        risk_class = added.layers["risk_class"]
        self.assertTrue(risk_class.isValid())
        self.assertEqual(risk_class.renderer().type(), "paletted")
        classes = {c.value: c.color.name() for c in risk_class.renderer().classes()}
        self.assertEqual(classes[4], "#e31a1c")
        self.assertEqual(classes[1], "#ffffb2")

        hazard = added.layers["hazard"]
        self.assertEqual(hazard.renderer().type(), "singlebandpseudocolor")
        self.assertEqual(hazard.renderer().band(), 1)  # the 0-3 hazard score, not the raw CDI codes

        visible = {n.name(): n.itemVisibilityChecked() for n in group.children()}
        self.assertTrue(visible["Risk class (2026-09-11)"])
        self.assertFalse(visible["Risk score (2026-09-11)"])

    def test_running_the_same_period_again_replaces_the_group(self):
        result = self._run()
        self.layers.add_run_to_project(result, self.project, STYLES_DIR)
        self.layers.add_run_to_project(result, self.project, STYLES_DIR)
        groups = [n for n in self.project.layerTreeRoot().children() if n.name().startswith("Agropastoral risk")]
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(self.project.mapLayers()), 3)

    def test_combined_hazard_run_uses_the_nine_class_style(self):
        cultivated = write_raster(self.root / "cult.tif", np.full((8, 8), 2.0), cell=0.5, nodata=-9999.0)
        result = self._run(hazard="combined", cultivated_raster=cultivated, output_dir=self.root / "run2")
        added = self.layers.add_run_to_project(result, self.project, STYLES_DIR)
        self.assertEqual(added.warnings, [])
        self.assertEqual(len(added.layers["hazard"].renderer().classes()), 9)
        self.assertIn("Combined hazard", added.layers["hazard"].name())

    def test_missing_style_directory_is_reported_not_swallowed(self):
        result = self._run()
        with self.assertRaises(FileNotFoundError):
            self.layers.add_run_to_project(result, self.project, self.root / "no_styles")


if __name__ == "__main__":
    unittest.main()
