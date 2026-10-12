import importlib.util
import unittest
from argparse import Namespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_runner():
    path = REPO_ROOT / "scripts" / "build_agropastoral_risk_raster.py"
    spec = importlib.util.spec_from_file_location("build_agropastoral_risk_raster", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RasterRunnerTests(unittest.TestCase):
    def test_dekad_from_day(self):
        runner = load_runner()
        self.assertEqual(runner.dekad_from_day(1), 1)
        self.assertEqual(runner.dekad_from_day(10), 1)
        self.assertEqual(runner.dekad_from_day(11), 11)
        self.assertEqual(runner.dekad_from_day(20), 11)
        self.assertEqual(runner.dekad_from_day(21), 21)
        self.assertEqual(runner.dekad_from_day(31), 21)

    def test_analysis_date_resolves_period(self):
        runner = load_runner()
        args = Namespace(analysis_date="2026-05-24", year=None, month=None, dekad=1)
        self.assertEqual(runner.resolve_analysis_period(args), (2026, 5, 21, "2026-05-24"))

    def test_year_month_resolves_period(self):
        runner = load_runner()
        args = Namespace(analysis_date=None, year=2026, month=5, dekad=11)
        self.assertEqual(runner.resolve_analysis_period(args), (2026, 5, 11, "2026-05-11"))


if __name__ == "__main__":
    unittest.main()
