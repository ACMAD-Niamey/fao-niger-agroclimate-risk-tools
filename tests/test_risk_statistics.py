from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from osgeo import gdal

from agroclimate_core.admin_summary import cell_area_km2
from agroclimate_core.risk_statistics import summarize_risk_map
from helpers import write_raster


class RiskStatisticsTests(unittest.TestCase):
    def test_class_areas_shares_and_mean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            classes = np.array([[1, 1, 2, 255], [3, 4, 255, 255], [1, 2, 3, 255], [255, 255, 255, 255]])
            scores = np.where(classes == 255, -9999.0, classes * 0.7)
            class_path = write_raster(root / "c.tif", classes, nodata=255, dtype=gdal.GDT_Byte)
            score_path = write_raster(root / "s.tif", scores, nodata=-9999.0)

            stats = summarize_risk_map(class_path, score_path)

            self.assertEqual(stats.scored_cells, 8)
            self.assertEqual(stats.total_cells, 16)
            by_name = {c.name: c for c in stats.classes}
            self.assertEqual([c.name for c in stats.classes], ["low", "moderate", "high", "very high"])
            self.assertEqual((by_name["low"].cells, by_name["moderate"].cells, by_name["high"].cells), (3, 2, 2))
            self.assertEqual(by_name["very high"].cells, 1)
            self.assertAlmostEqual(sum(c.share_pct for c in stats.classes), 100.0, places=6)
            self.assertAlmostEqual(stats.scored_area_km2, sum(c.area_km2 for c in stats.classes), places=3)
            # area-weighted mean over scored cells: classes 1,1,2,3,4,1,2,3 -> mean 2.125 * 0.7
            self.assertAlmostEqual(stats.mean_risk_score, 2.125 * 0.7, delta=0.02)
            self.assertEqual(stats.worst_class, "very high")
            self.assertGreater(by_name["low"].area_km2, cell_area_km2(1.0, 0.0, 1.0) * 2)

    def test_map_with_no_scored_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            class_path = write_raster(root / "c.tif", np.full((2, 2), 255), nodata=255, dtype=gdal.GDT_Byte)
            score_path = write_raster(root / "s.tif", np.full((2, 2), -9999.0), nodata=-9999.0)
            stats = summarize_risk_map(class_path, score_path)
            self.assertEqual(stats.scored_cells, 0)
            self.assertIsNone(stats.mean_risk_score)
            self.assertEqual(stats.worst_class, "n/a")
            self.assertEqual([c.share_pct for c in stats.classes], [0.0, 0.0, 0.0, 0.0])

    def test_as_dict_is_plain_data_for_display_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            class_path = write_raster(root / "c.tif", np.array([[1, 4]]), nodata=255, dtype=gdal.GDT_Byte)
            score_path = write_raster(root / "s.tif", np.array([[0.5, 2.8]]), nodata=-9999.0)
            data = summarize_risk_map(class_path, score_path).as_dict()
            self.assertEqual(set(data), {"scored_cells", "total_cells", "scored_area_km2", "mean_risk_score", "worst_class", "classes"})
            self.assertEqual(data["classes"][0]["name"], "low")


if __name__ == "__main__":
    unittest.main()
