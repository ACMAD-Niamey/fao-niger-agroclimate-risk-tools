import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from osgeo import gdal

from agroclimate_core.exposure import (
    ExposureThresholds,
    aggregate_class_fractions,
    cache_raster_window,
    cells_touching_boundary,
    fetch_worldcover_tiles,
    fraction_to_score,
    prepare_exposure_rasters,
    worldcover_tile_urls,
)


def _write_class_raster(path: Path, array: np.ndarray, origin: tuple[float, float], pixel: float) -> None:
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(str(path), array.shape[1], array.shape[0], 1, gdal.GDT_Byte)
    dataset.SetGeoTransform((origin[0], pixel, 0, origin[1], 0, -pixel))
    dataset.SetProjection("EPSG:4326")
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(0)
    data = array.astype("uint8")
    band.WriteRaster(0, 0, data.shape[1], data.shape[0], data.tobytes(), buf_type=gdal.GDT_Byte)
    dataset.FlushCache()


def _write_template(path: Path, width: int, height: int, origin: tuple[float, float], cell: float) -> None:
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(str(path), width, height, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((origin[0], cell, 0, origin[1], 0, -cell))
    dataset.SetProjection("EPSG:4326")
    dataset.FlushCache()


class WorldCoverTileTests(unittest.TestCase):
    def test_tiles_cover_bounds_with_three_degree_names(self):
        urls = worldcover_tile_urls((0.2, 11.7, 15.9, 23.5))
        names = {url.rsplit("_", 2)[-2] for url in urls}
        self.assertIn("N12E000", names)
        self.assertIn("N12E015", names)
        self.assertIn("N21E012", names)
        # lon 0-18 -> 6 columns, lat 9-24 -> 5 rows
        self.assertEqual(len(urls), 6 * 5)

    def test_southern_and_western_hemisphere_names(self):
        urls = worldcover_tile_urls((-2.0, -2.0, -1.0, -1.0))
        self.assertTrue(urls[0].endswith("ESA_WorldCover_10m_2021_v200_S03W003_Map.tif"))


class FractionToScoreTests(unittest.TestCase):
    def test_bins_and_nodata(self):
        thresholds = ExposureThresholds(low=0.05, moderate=0.25, high=0.5)
        fractions = np.array([0.0, 0.049, 0.05, 0.249, 0.25, 0.5, 1.0, np.nan], dtype="float32")
        scores = fraction_to_score(fractions, thresholds, nodata=-9999.0)
        self.assertEqual(scores.tolist(), [0, 0, 1, 1, 2, 3, 3, -9999])

    def test_thresholds_must_increase(self):
        with self.assertRaises(ValueError):
            ExposureThresholds(low=0.3, moderate=0.2, high=0.5)


class AggregateFractionTests(unittest.TestCase):
    def test_fractions_per_cell_ignore_nodata_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 4x4 source px at 0.5 deg -> 2x2 template cells at 1 deg (each cell = 2x2 px).
            source = np.array(
                [
                    [40, 40, 30, 20],  # cell(0,0): 40,40 / 40,10 -> 3/4 crop
                    [40, 10, 30, 60],  # cell(0,1): 30,20 / 30,60 -> 3/4 rangeland (20+30)
                    [10, 10, 40, 0],   # cell(1,0): all 10 -> 0 crop ; cell(1,1): 40,0 / 0,0 -> 1 valid px
                    [10, 10, 0, 0],
                ]
            )
            source_path = tmp_path / "wc.tif"
            template_path = tmp_path / "template.tif"
            _write_class_raster(source_path, source, origin=(0.0, 2.0), pixel=0.5)
            _write_template(template_path, 2, 2, origin=(0.0, 2.0), cell=1.0)

            result = aggregate_class_fractions(
                [source_path],
                template_path,
                {"cultivated": (40,), "rangeland": (20, 30)},
            )

            self.assertAlmostEqual(float(result["cultivated"][0, 0]), 0.75)
            self.assertAlmostEqual(float(result["rangeland"][0, 1]), 0.75)
            self.assertAlmostEqual(float(result["cultivated"][1, 0]), 0.0)
            # nodata (0) pixels are excluded from the denominator -> 1 valid crop px = 100 %
            self.assertAlmostEqual(float(result["cultivated"][1, 1]), 1.0)

    def test_cells_without_coverage_are_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "wc.tif"
            template_path = tmp_path / "template.tif"
            _write_class_raster(source_path, np.full((2, 2), 40), origin=(0.0, 2.0), pixel=0.5)
            _write_template(template_path, 3, 2, origin=(0.0, 2.0), cell=1.0)

            result = aggregate_class_fractions([source_path], template_path, {"cultivated": (40,)})
            self.assertAlmostEqual(float(result["cultivated"][0, 0]), 1.0)
            self.assertTrue(math.isnan(float(result["cultivated"][0, 2])))
            self.assertTrue(math.isnan(float(result["cultivated"][1, 1])))

    def test_misaligned_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "wc.tif"
            template_path = tmp_path / "template.tif"
            _write_class_raster(source_path, np.full((4, 4), 40), origin=(0.3, 2.0), pixel=0.5)
            _write_template(template_path, 2, 2, origin=(0.0, 2.0), cell=1.0)
            with self.assertRaises(ValueError):
                aggregate_class_fractions([source_path], template_path, {"cultivated": (40,)})


class PrepareExposureTests(unittest.TestCase):
    def test_writes_fraction_and_score_rasters_on_template_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = np.array([[40, 40, 30, 20], [40, 40, 30, 60], [10, 10, 0, 0], [10, 10, 0, 0]])
            _write_class_raster(tmp_path / "wc.tif", source, origin=(0.0, 2.0), pixel=0.5)
            _write_template(tmp_path / "template.tif", 2, 2, origin=(0.0, 2.0), cell=1.0)

            outputs = prepare_exposure_rasters(
                template_path=tmp_path / "template.tif",
                output_dir=tmp_path / "exposure",
                source_paths=[tmp_path / "wc.tif"],
            )

            self.assertEqual(
                set(outputs), {"cultivated_fraction", "cultivated_exposure", "rangeland_fraction", "rangeland_exposure"}
            )
            dataset = gdal.Open(str(outputs["cultivated_exposure"]))
            self.assertEqual((dataset.RasterXSize, dataset.RasterYSize), (2, 2))
            self.assertEqual(dataset.GetGeoTransform(), (0.0, 1.0, 0.0, 2.0, 0.0, -1.0))
            raw = dataset.GetRasterBand(1).ReadRaster(0, 0, 2, 2, buf_type=gdal.GDT_Float32)
            scores = np.frombuffer(raw, dtype=np.float32).reshape(2, 2)
            # cultivated fraction: [[1.0, 0.0], [0, no data]] -> [[3, 0], [0, -9999]]
            self.assertEqual(scores.tolist(), [[3.0, 0.0], [0.0, -9999.0]])


def _write_boundary(path: Path, ring: list[list[float]]) -> None:
    path.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},'
        '"geometry":{"type":"Polygon","coordinates":[' + str(ring) + "]}}]}",
        encoding="utf-8",
    )


class BoundaryMaskTests(unittest.TestCase):
    def test_cells_touching_boundary_includes_edge_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_template(tmp_path / "template.tif", 4, 4, origin=(0.0, 4.0), cell=1.0)
            # Triangle-ish polygon inside the left two columns, top two rows (+ a sliver into col 2).
            _write_boundary(tmp_path / "b.geojson", [[0.1, 3.9], [2.2, 3.9], [2.2, 2.1], [0.1, 2.1], [0.1, 3.9]])
            mask = cells_touching_boundary(tmp_path / "b.geojson", tmp_path / "template.tif")
            self.assertEqual(mask.shape, (4, 4))
            self.assertEqual(mask.astype(int).tolist(), [[1, 1, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]])

    def test_mask_skips_cells_and_leaves_them_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_class_raster(tmp_path / "wc.tif", np.full((4, 4), 40), origin=(0.0, 2.0), pixel=0.5)
            _write_template(tmp_path / "template.tif", 2, 2, origin=(0.0, 2.0), cell=1.0)
            mask = np.array([[True, False], [False, False]])
            result = aggregate_class_fractions(
                [tmp_path / "wc.tif"], tmp_path / "template.tif", {"cultivated": (40,)}, cell_mask=mask
            )
            self.assertEqual(float(result["cultivated"][0, 0]), 1.0)
            self.assertTrue(np.isnan(result["cultivated"][0, 1]))
            self.assertTrue(np.isnan(result["cultivated"][1, 0]))


class CacheTests(unittest.TestCase):
    def test_cache_raster_window_writes_once_and_keeps_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_class_raster(tmp_path / "wc.tif", np.full((8, 8), 40), origin=(0.0, 4.0), pixel=0.5)
            destination = tmp_path / "cache" / "wc_window.tif"
            cache_raster_window(tmp_path / "wc.tif", destination, (1.0, 1.0, 3.0, 3.0))
            dataset = gdal.Open(str(destination))
            self.assertEqual((dataset.RasterXSize, dataset.RasterYSize), (4, 4))
            self.assertEqual(dataset.GetGeoTransform()[:1] + dataset.GetGeoTransform()[3:4], (1.0, 3.0))
            modified = destination.stat().st_mtime_ns
            cache_raster_window(tmp_path / "wc.tif", destination, (1.0, 1.0, 3.0, 3.0))
            self.assertEqual(destination.stat().st_mtime_ns, modified)
            self.assertEqual([p.name for p in destination.parent.iterdir()], ["wc_window.tif"])

    def test_fetch_worldcover_tiles_only_fetches_tiles_with_masked_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 6 cells wide at 1 deg: lon 0-6 -> two 3-degree tiles; only cells in the first are needed.
            _write_template(tmp_path / "template.tif", 6, 3, origin=(0.0, 12.0), cell=1.0)
            mask = np.zeros((3, 6), dtype=bool)
            mask[1, 1:3] = True
            fetched: list[str] = []

            def fake_translate(source: str, destination: Path, bounds):
                fetched.append(Path(source).name)
                return cache_raster_window(_make_tile(tmp_path / Path(source).name, bounds), destination, bounds)

            def _make_tile(path: Path, bounds):
                _write_class_raster(path, np.full((12, 12), 40), origin=(0.0, 12.0), pixel=0.25)
                return path

            paths = fetch_worldcover_tiles(
                template_path=tmp_path / "template.tif",
                cache_dir=tmp_path / "cache",
                cell_mask=mask,
                workers=2,
                fetch=fake_translate,
            )
            self.assertEqual(len(paths), 1)
            self.assertEqual(len(fetched), 1)
            window = gdal.Open(str(paths[0]))
            # tight window: one row, two cells wide at 4 px per cell
            self.assertEqual((window.RasterXSize, window.RasterYSize), (8, 4))


if __name__ == "__main__":
    unittest.main()
