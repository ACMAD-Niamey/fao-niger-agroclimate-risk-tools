import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QgisHelperTests(unittest.TestCase):
    def test_output_field_names_are_stable(self):
        fields = load_module("qgis_fields", REPO_ROOT / "qgis" / "processing" / "fields.py")
        self.assertEqual(
            fields.output_field_names(),
            ["hazard_score", "exposure_score", "risk_score", "risk_class"],
        )

    def test_fetch_boundary_algorithm_source_mentions_actual_niger_defaults(self):
        source = (REPO_ROOT / "qgis" / "processing" / "fetch_acmad_boundary.py").read_text()
        self.assertIn("Fetch ACMAD Boundary Layer", source)
        self.assertIn("GeoServer workspace", source)
        self.assertIn("data_api_adminlevelzero", source)
        self.assertIn("DEFAULT_ACMAD_GEOSERVER_URL", source)

    def test_risk_algorithm_exposes_boundary_source_controls(self):
        source = (REPO_ROOT / "qgis" / "processing" / "agropastoral_drought_risk.py").read_text()
        self.assertIn("Zonal boundary source", source)
        self.assertIn("Fetch Niger boundary from ACMAD WFS", source)
        self.assertIn("ACMAD GeoServer/WFS URL", source)
        self.assertIn("GeoServer workspace", source)
        self.assertIn("DEFAULT_ACMAD_GEOSERVER_URL", source)
        self.assertIn("Default CDI score", source)
        self.assertIn("Default cultivated exposure score", source)
        self.assertIn("Default rangeland exposure score", source)
        self.assertIn("Default water-point exposure score", source)

    def test_plugin_exposes_raster_style_actions(self):
        source = (REPO_ROOT / "qgis" / "plugin" / "plugin.py").read_text()
        self.assertIn("Apply Risk Class Style", source)
        self.assertIn("risk_class.qml", source)
        self.assertIn("risk_score.qml", source)
        self.assertIn("cdi_hazard.qml", source)

    def test_plugin_builder_packages_qgis_styles(self):
        source = (REPO_ROOT / "scripts" / "build_qgis_plugin.py").read_text()
        self.assertIn("qgis\" / \"styles", source)
        self.assertIn("build_root / \"styles", source)

    def test_qgis_style_files_exist(self):
        style_dir = REPO_ROOT / "qgis" / "styles"
        self.assertTrue((style_dir / "risk_class.qml").exists())
        self.assertTrue((style_dir / "risk_score.qml").exists())
        self.assertTrue((style_dir / "cdi_hazard.qml").exists())

    def test_bootstrap_adds_src_path(self):
        bootstrap = load_module("qgis_bootstrap", REPO_ROOT / "qgis" / "processing" / "bootstrap.py")
        src_path = str(REPO_ROOT / "src")
        original_path = list(sys.path)
        try:
            sys.path = [path for path in sys.path if path != src_path]
            bootstrap.ensure_src_path()
            self.assertIn(src_path, sys.path)
        finally:
            sys.path = original_path


if __name__ == "__main__":
    unittest.main()
