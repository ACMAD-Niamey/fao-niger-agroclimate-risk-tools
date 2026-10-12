import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from agroclimate_core.periods import DekadPeriod
from agroclimate_core.run_metadata import write_run_metadata


class RunMetadataTests(unittest.TestCase):
    def test_serialises_dates_paths_and_dataclasses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_run_metadata(
                tmp,
                {"requested": date(2026, 10, 12), "cdi_period": DekadPeriod(2026, 9, 11), "raster": Path("/x/y.tif")},
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["requested"], "2026-10-12")
            self.assertEqual(data["cdi_period"], {"year": 2026, "month": 9, "dekad": 11})
            self.assertEqual(data["raster"], "/x/y.tif")
            self.assertTrue(data["generated_at_utc"].endswith("+00:00"))

    def test_unsupported_values_fail_loudly(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(TypeError):
            write_run_metadata(tmp, {"bad": object()})


if __name__ == "__main__":
    unittest.main()
