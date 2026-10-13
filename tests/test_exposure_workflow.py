from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from osgeo import gdal

from agroclimate_core.cancellation import WorkflowCancelled
from agroclimate_core.exposure_workflow import ExposureConfig, exposure_files_exist, run_exposure_preparation
from agroclimate_core.grid import make_grid_template
from agroclimate_core.workflow import WorkflowServices
from helpers import write_boundary, write_raster


def _services(boundary: Path) -> WorkflowServices:
    def download_boundary(path: Path, _url: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(boundary.read_text(encoding="utf-8"), encoding="utf-8")
        return path

    unused = lambda *a, **k: (_ for _ in ()).throw(AssertionError("not used"))  # noqa: E731
    return WorkflowServices(unused, unused, unused, unused, download_boundary)


class GridTemplateTests(unittest.TestCase):
    def test_grid_snaps_outward_to_the_tenth_of_a_degree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            boundary = write_boundary(root / "b.geojson", west=0.17, south=11.69, east=15.99, north=23.52)
            path = make_grid_template(boundary, root / "grid.tif")
            grid = gdal.Open(str(path))
            gt = grid.GetGeoTransform()
            self.assertAlmostEqual(gt[0], 0.1)
            self.assertAlmostEqual(gt[3], 23.6)
            self.assertAlmostEqual(gt[1], 0.1)
            self.assertEqual((grid.RasterXSize, grid.RasterYSize), (159, 120))

    def test_boundary_already_on_the_grid_is_not_padded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            boundary = write_boundary(root / "b.geojson", west=0.2, south=1.0, east=0.5, north=1.3)
            grid = gdal.Open(str(make_grid_template(boundary, root / "grid.tif")))
            self.assertEqual((grid.RasterXSize, grid.RasterYSize), (3, 3))


class ExposureWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # 0.1-degree template cells: x 0.1-0.4 (3 cols), y 0.5-0.9 (4 rows); land cover at 0.05 degrees.
        self.boundary = write_boundary(self.root / "boundary.geojson", west=0.12, south=0.52, east=0.38, north=0.88)
        classes = np.full((20, 20), 40)  # all cropland
        classes[0:10, 10:20] = 30  # top-right quarter grassland
        self.landcover = write_raster(self.root / "wc.tif", classes, origin=(0.0, 1.0), cell=0.05, nodata=0, dtype=gdal.GDT_Byte)

    def tearDown(self):
        self.tmp.cleanup()

    def _config(self, **overrides) -> ExposureConfig:
        values = dict(output_dir=self.root / "exposure", cache_dir=None, landcover=[self.landcover])
        values.update(overrides)
        return ExposureConfig(**values)

    def test_prepares_the_four_rasters_on_the_boundary_grid(self):
        outputs = run_exposure_preparation(self._config(), services=_services(self.boundary))
        self.assertEqual(set(outputs), {"cultivated_fraction", "cultivated_exposure", "rangeland_fraction", "rangeland_exposure"})
        self.assertTrue(exposure_files_exist(self.root / "exposure"))
        grid = gdal.Open(str(outputs["cultivated_exposure"]))
        self.assertEqual((grid.RasterXSize, grid.RasterYSize), (3, 4))

    def test_exposure_files_exist_is_false_until_both_scores_are_present(self):
        self.assertFalse(exposure_files_exist(self.root / "nothing"))
        run_exposure_preparation(self._config(), services=_services(self.boundary))
        (self.root / "exposure" / "rangeland_exposure.tif").unlink()
        self.assertFalse(exposure_files_exist(self.root / "exposure"))

    def test_progress_is_ordered_and_finishes_at_one_hundred(self):
        seen: list[float] = []
        run_exposure_preparation(self._config(), services=_services(self.boundary), progress=lambda p, m: seen.append(p))
        self.assertEqual(seen, sorted(seen))
        self.assertEqual(seen[-1], 100)

    def test_cancellation_stops_the_run_and_writes_no_exposure(self):
        with self.assertRaises(WorkflowCancelled):
            run_exposure_preparation(self._config(), services=_services(self.boundary), is_cancelled=lambda: True)
        self.assertFalse(exposure_files_exist(self.root / "exposure"))


if __name__ == "__main__":
    unittest.main()
