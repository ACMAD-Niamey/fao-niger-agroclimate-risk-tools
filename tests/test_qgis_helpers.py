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
        self.assertIn("country_code=181", source)
        self.assertIn("data_api_adminlevelzero", source)

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
