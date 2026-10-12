import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from osgeo import gdal

from agroclimate_core.admin_summary import (
    cell_area_km2,
    summarize_by_admin,
    write_summary_csv,
    write_summary_geojson,
)


def _write_raster(path: Path, array: np.ndarray, dtype: int, nodata: float) -> None:
    rows, cols = array.shape
    dataset = gdal.GetDriverByName("GTiff").Create(str(path), cols, rows, 1, dtype)
    dataset.SetGeoTransform((0, 1, 0, 4, 0, -1))
    dataset.SetProjection("EPSG:4326")
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(nodata)
    data = array.astype("uint8" if dtype == gdal.GDT_Byte else "float32")
    band.WriteRaster(0, 0, cols, rows, data.tobytes(), buf_type=dtype)
    dataset.FlushCache()


def _polygon(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def _write_admin(path: Path) -> None:
    features = [
        {"type": "Feature", "properties": {"name": "West", "code": "W"}, "geometry": _polygon(0, 0, 2, 4)},
        {"type": "Feature", "properties": {"name": "East", "code": "E"}, "geometry": _polygon(2, 0, 4, 4)},
    ]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")


class CellAreaTests(unittest.TestCase):
    def test_one_degree_cell_at_the_equator(self):
        self.assertAlmostEqual(cell_area_km2(1.0, 0.0, 1.0), 12364, delta=15)

    def test_cells_shrink_towards_the_pole(self):
        self.assertLess(cell_area_km2(61.0, 60.0, 1.0), cell_area_km2(1.0, 0.0, 1.0) * 0.52)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        # classes: 1 low .. 4 very high, 255 = not scored
        classes = np.array(
            [
                [1, 1, 4, 3],
                [2, 255, 3, 255],
                [255, 255, 1, 255],
                [1, 2, 255, 255],
            ]
        )
        scores = np.where(classes == 255, -9999.0, classes * 0.75)
        self.classes_path, self.scores_path = tmp / "class.tif", tmp / "score.tif"
        _write_raster(self.classes_path, classes, gdal.GDT_Byte, 255)
        _write_raster(self.scores_path, scores, gdal.GDT_Float32, -9999)
        self.cultivated = tmp / "cultivated.tif"
        _write_raster(self.cultivated, np.full((4, 4), 0.5), gdal.GDT_Float32, -9999)
        self.admin_path = tmp / "admin.geojson"
        _write_admin(self.admin_path)

    def tearDown(self):
        self.tmp.cleanup()

    def _rows(self, **kwargs):
        rows = summarize_by_admin(
            self.classes_path, self.scores_path, self.admin_path, name_field="name", code_field="code", **kwargs
        )
        return {row["admin_name"]: row for row in rows}

    def test_counts_shares_and_max_class_per_region(self):
        rows = self._rows()
        west, east = rows["West"], rows["East"]
        # West = columns 0-1: classes 1,1,2,1,2 scored (5 cells), three unscored
        self.assertEqual((west["cells_total"], west["cells_scored"]), (8, 5))
        self.assertEqual(west["max_risk_class"], "moderate")
        # East = columns 2-3: 4,3,3,1 scored (4 cells)
        self.assertEqual(east["cells_scored"], 4)
        self.assertEqual(east["max_risk_class"], "very high")
        self.assertAlmostEqual(east["pct_high"] + east["pct_very_high"], 75.0, delta=2.0)
        self.assertAlmostEqual(
            west["pct_low"] + west["pct_moderate"] + west["pct_high"] + west["pct_very_high"], 100.0, delta=0.01
        )

    def test_mean_risk_score_is_area_weighted_over_scored_cells_only(self):
        west = self._rows()["West"]
        self.assertAlmostEqual(west["mean_risk_score"], (1 + 1 + 2 + 1 + 2) / 5 * 0.75, delta=0.05)

    def test_exposed_area_uses_fractions_in_high_risk_cells_only(self):
        rows = self._rows(cultivated_fraction_path=self.cultivated)
        east = rows["East"]
        self.assertGreaterEqual(east["cultivated_ha_total"], east["cultivated_ha_high_risk"])
        self.assertGreater(east["cultivated_ha_high_risk"], 0)
        # East has 3 high/very-high cells of 4 scored; fraction 0.5 everywhere
        self.assertAlmostEqual(east["cultivated_ha_high_risk"] / east["high_risk_area_km2"], 50.0, delta=0.5)  # 0.5 * 100 ha/km2
        self.assertEqual(rows["West"]["cultivated_ha_high_risk"], 0.0)

    def test_region_with_no_scored_cells_reports_not_applicable(self):
        classes = np.full((4, 4), 255)
        _write_raster(self.classes_path, classes, gdal.GDT_Byte, 255)
        _write_raster(self.scores_path, np.full((4, 4), -9999.0), gdal.GDT_Float32, -9999)
        row = self._rows()["West"]
        self.assertEqual(row["cells_scored"], 0)
        self.assertEqual(row["max_risk_class"], "n/a")
        self.assertIsNone(row["mean_risk_score"])

    def test_missing_name_field_is_a_clear_error(self):
        with self.assertRaises(KeyError) as caught:
            summarize_by_admin(self.classes_path, self.scores_path, self.admin_path, name_field="nope")
        self.assertIn("name", str(caught.exception))

    def test_writes_csv_and_joined_geojson(self):
        rows = list(self._rows().values())
        csv_path = Path(self.tmp.name) / "summary.csv"
        geojson_path = Path(self.tmp.name) / "summary.geojson"
        write_summary_csv(rows, csv_path)
        write_summary_geojson(self.admin_path, rows, geojson_path, key_field="name")
        with csv_path.open(encoding="utf-8") as fp:
            parsed = list(csv.DictReader(fp))
        self.assertEqual({r["admin_name"] for r in parsed}, {"West", "East"})
        joined = json.loads(geojson_path.read_text(encoding="utf-8"))
        east = next(f for f in joined["features"] if f["properties"]["name"] == "East")
        self.assertEqual(east["properties"]["max_risk_class"], "very high")
        self.assertEqual(east["properties"]["code"], "E")  # original attributes are kept


if __name__ == "__main__":
    unittest.main()
