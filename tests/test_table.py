import csv
import tempfile
import unittest
from pathlib import Path

from agroclimate_core.table import score_csv


class TableScoringTests(unittest.TestCase):
    def test_score_csv_writes_risk_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.csv"
            output_path = tmp_path / "output.csv"
            input_path.write_text(
                "admin,cdi,fapar_anomaly,soil_moisture_anomaly,cultivated_exposure,rangeland_exposure,water_point_exposure\n"
                "A,warning,severe,moderate,3,2,1\n",
                encoding="utf-8",
            )

            score_csv(input_path, output_path)

            with output_path.open(newline="", encoding="utf-8") as source:
                rows = list(csv.DictReader(source))

            self.assertEqual(rows[0]["admin"], "A")
            self.assertEqual(rows[0]["hazard_score"], "2.2")
            self.assertEqual(rows[0]["exposure_score"], "2.25")
            self.assertEqual(rows[0]["risk_score"], "2.22")
            self.assertEqual(rows[0]["risk_class"], "high")


if __name__ == "__main__":
    unittest.main()
