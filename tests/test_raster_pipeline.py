import tempfile
import unittest
from pathlib import Path

import numpy as np
from osgeo import gdal

from agroclimate_core.raster_pipeline import ExposureDefaults, _normalize_cdi, build_agropastoral_risk_rasters


class RasterPipelineTests(unittest.TestCase):
    def test_acmad_cdi_codes_are_mapped_to_hazard_scores(self):
        raw = np.array([[0, 1, 3, 4, 6, 7, 10, 11, 12, 13, 14]], dtype="float32")
        scores = _normalize_cdi(raw, cdi_code_scheme="acmad")
        self.assertEqual(scores.tolist()[0], [0, 1, 1, 2, 2, 3, 3, 1, 1, 0, 0])

    def _write_band_array(self, band, array, dtype=gdal.GDT_Float32):
        output = array.astype("uint8") if dtype == gdal.GDT_Byte else array.astype("float32")
        band.WriteRaster(
            0,
            0,
            output.shape[1],
            output.shape[0],
            output.tobytes(),
            buf_xsize=output.shape[1],
            buf_ysize=output.shape[0],
            buf_type=dtype,
        )

    def _read_band_array(self, dataset, dtype=np.float32, gdal_type=gdal.GDT_Float32):
        raw = dataset.GetRasterBand(1).ReadRaster(
            0,
            0,
            dataset.RasterXSize,
            dataset.RasterYSize,
            buf_xsize=dataset.RasterXSize,
            buf_ysize=dataset.RasterYSize,
            buf_type=gdal_type,
        )
        return np.frombuffer(raw, dtype=dtype).reshape(dataset.RasterYSize, dataset.RasterXSize)

    def _write_test_raster(self, path: Path):
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(str(path), 4, 4, 1, gdal.GDT_Float32)
        dataset.SetGeoTransform((0, 1, 0, 4, 0, -1))
        dataset.SetProjection("EPSG:4326")
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(-9999)
        self._write_band_array(
            band,
            np.array(
                [
                    [0, 1, 2, 3],
                    [1, 2, 3, 0],
                    [2, 3, 0, 1],
                    [3, 0, 1, 2],
                ],
                dtype="float32",
            )
        )
        dataset.FlushCache()
        dataset = None

    def _write_boundary(self, path: Path):
        path.write_text(
            """
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {"name": "test"},
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[0,0],[4,0],[4,4],[0,4],[0,0]]]
      }
    }
  ]
}
""".strip(),
            encoding="utf-8",
        )

    def test_build_agropastoral_risk_rasters_with_default_exposure(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cdi_path = tmp_path / "cdi.tif"
            boundary_path = tmp_path / "boundary.geojson"
            self._write_test_raster(cdi_path)
            self._write_boundary(boundary_path)

            outputs = build_agropastoral_risk_rasters(
                cdi_raster=cdi_path,
                boundary_geojson=boundary_path,
                output_dir=tmp_path / "out",
                exposure_defaults=ExposureDefaults(cultivated=2, rangeland=2, water_points=1),
            )

            risk_dataset = gdal.Open(str(outputs["risk_score"]))
            self.assertIsNotNone(risk_dataset)
            risk = self._read_band_array(risk_dataset)
            self.assertAlmostEqual(float(risk[0, 0]), 0.72, places=2)
            self.assertAlmostEqual(float(risk[0, 3]), 2.52, places=2)

            class_dataset = gdal.Open(str(outputs["risk_class"]))
            risk_class = self._read_band_array(class_dataset, dtype=np.uint8, gdal_type=gdal.GDT_Byte)
            self.assertEqual(int(risk_class[0, 0]), 1)
            self.assertEqual(int(risk_class[0, 3]), 4)

    def _write_exposure_raster(self, path: Path, value: float, *, nodata: float, masked_corner: bool = False):
        """Write an 8x8 raster over the same extent as the 4x4 CDI (finer grid, own nodata tag)."""
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(str(path), 8, 8, 1, gdal.GDT_Float32)
        dataset.SetGeoTransform((0, 0.5, 0, 4, 0, -0.5))
        dataset.SetProjection("EPSG:4326")
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(nodata)
        array = np.full((8, 8), value, dtype="float32")
        if masked_corner:
            array[0:2, 0:2] = nodata
        self._write_band_array(band, array)
        dataset.FlushCache()
        dataset = None

    def test_exposure_rasters_are_aligned_and_use_their_own_nodata(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cdi_path = tmp_path / "cdi.tif"
            boundary_path = tmp_path / "boundary.geojson"
            cultivated_path = tmp_path / "cultivated.tif"
            self._write_test_raster(cdi_path)
            self._write_boundary(boundary_path)
            # 255 is a typical byte-style nodata; it must not be read as a score.
            self._write_exposure_raster(cultivated_path, 3.0, nodata=255, masked_corner=True)

            outputs = build_agropastoral_risk_rasters(
                cdi_raster=cdi_path,
                boundary_geojson=boundary_path,
                output_dir=tmp_path / "out",
                cultivated_raster=cultivated_path,
                exposure_defaults=ExposureDefaults(cultivated=2, rangeland=2, water_points=1),
            )

            risk = self._read_band_array(gdal.Open(str(outputs["risk_score"])))
            # cell (0,3): cdi=3, exposure = .45*3 + .35*2 + .2*1 = 2.25 -> .6*3 + .4*2.25
            self.assertAlmostEqual(float(risk[0, 3]), 2.7, places=2)
            # cell (0,0) is fully masked in the exposure raster -> no data, not a score.
            self.assertEqual(float(risk[0, 0]), -9999.0)

    def test_stack_risk_class_band_uses_nodata_where_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cdi_path = tmp_path / "cdi.tif"
            boundary_path = tmp_path / "boundary.geojson"
            cultivated_path = tmp_path / "cultivated.tif"
            self._write_test_raster(cdi_path)
            self._write_boundary(boundary_path)
            self._write_exposure_raster(cultivated_path, 1.0, nodata=255, masked_corner=True)

            outputs = build_agropastoral_risk_rasters(
                cdi_raster=cdi_path,
                boundary_geojson=boundary_path,
                output_dir=tmp_path / "out",
                cultivated_raster=cultivated_path,
            )

            stack = gdal.Open(str(outputs["risk_stack"]))
            class_band = stack.GetRasterBand(4)
            self.assertEqual(class_band.GetDescription(), "risk_class")
            values = np.frombuffer(
                class_band.ReadRaster(0, 0, stack.RasterXSize, stack.RasterYSize, buf_type=gdal.GDT_Float32),
                dtype=np.float32,
            ).reshape(stack.RasterYSize, stack.RasterXSize)
            self.assertEqual(float(values[0, 0]), class_band.GetNoDataValue())

    def _write_coarse_hazard(self, path: Path):
        """2x2 raster of 2-degree cells over the same 4x4 extent as the CDI; 0 is nodata."""
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(str(path), 2, 2, 1, gdal.GDT_Byte)
        dataset.SetGeoTransform((0, 2, 0, 4, 0, -2))
        dataset.SetProjection("EPSG:4326")
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(0)
        self._write_band_array(band, np.array([[1, 9], [5, 0]]), dtype=gdal.GDT_Byte)
        dataset.FlushCache()

    def test_combined_hazard_classes_are_mapped(self):
        raw = np.array([[1, 2, 3, 4, 5, 6, 7, 8, 9, 0]], dtype="float32")
        scores = _normalize_cdi(raw, cdi_code_scheme="combined-hazard")
        self.assertEqual(scores.tolist()[0], [0, 0, 1, 1, 2, 2, 3, 3, 3, -9999])

    def test_coarse_hazard_is_resampled_onto_the_grid_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            hazard_path = tmp_path / "hazard.tif"
            template_path = tmp_path / "grid.tif"
            boundary_path = tmp_path / "boundary.geojson"
            self._write_coarse_hazard(hazard_path)
            self._write_test_raster(template_path)  # 4x4 at 1 degree
            self._write_boundary(boundary_path)

            outputs = build_agropastoral_risk_rasters(
                cdi_raster=hazard_path,
                boundary_geojson=boundary_path,
                output_dir=tmp_path / "out",
                exposure_defaults=ExposureDefaults(cultivated=2, rangeland=2, water_points=1),
                cdi_code_scheme="combined-hazard",
                grid_template=template_path,
                hazard_name="combined_hazard",
            )

            risk_dataset = gdal.Open(str(outputs["risk_score"]))
            self.assertEqual((risk_dataset.RasterXSize, risk_dataset.RasterYSize), (4, 4))
            risk = self._read_band_array(risk_dataset)
            # class 1 -> hazard 0 across the top-left 2x2 block: 0.6*0 + 0.4*1.8
            self.assertAlmostEqual(float(risk[0, 0]), 0.72, places=2)
            self.assertAlmostEqual(float(risk[1, 1]), 0.72, places=2)
            # class 9 -> hazard 3 across the top-right block
            self.assertAlmostEqual(float(risk[0, 3]), 2.52, places=2)
            # class 5 -> hazard 2 bottom-left
            self.assertAlmostEqual(float(risk[3, 0]), 1.92, places=2)
            # class 0 (nodata) bottom-right stays nodata
            self.assertEqual(float(risk[3, 3]), -9999.0)
            self.assertEqual(outputs["combined_hazard"].name, "combined_hazard_niger.tif")

    def _write_exposure_array(self, path: Path, array: np.ndarray):
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(str(path), 8, 8, 1, gdal.GDT_Float32)
        dataset.SetGeoTransform((0, 0.5, 0, 4, 0, -0.5))
        dataset.SetProjection("EPSG:4326")
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(-9999)
        self._write_band_array(band, array)
        dataset.FlushCache()

    def test_agropastoral_mask_drops_cells_with_no_cultivated_or_rangeland_exposure(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cdi_path, boundary_path = tmp_path / "cdi.tif", tmp_path / "boundary.geojson"
            cultivated_path, rangeland_path = tmp_path / "cultivated.tif", tmp_path / "rangeland.tif"
            self._write_test_raster(cdi_path)
            self._write_boundary(boundary_path)
            cultivated = np.zeros((8, 8), dtype="float32")
            cultivated[0:2, 6:8] = 3  # only 4x4 cell (0, 3) has cropland
            rangeland = np.zeros((8, 8), dtype="float32")
            rangeland[6:8, 0:2] = 1  # only cell (3, 0) has rangeland
            self._write_exposure_array(cultivated_path, cultivated)
            self._write_exposure_array(rangeland_path, rangeland)

            def run(name: str, masked: bool):
                outputs = build_agropastoral_risk_rasters(
                    cdi_raster=cdi_path,
                    boundary_geojson=boundary_path,
                    output_dir=tmp_path / name,
                    cultivated_raster=cultivated_path,
                    rangeland_raster=rangeland_path,
                    mask_to_agropastoral=masked,
                )
                risk = self._read_band_array(gdal.Open(str(outputs["risk_score"])))
                stack = gdal.Open(str(outputs["risk_stack"]))
                klass = np.frombuffer(
                    stack.GetRasterBand(4).ReadRaster(0, 0, 4, 4, buf_type=gdal.GDT_Float32), dtype=np.float32
                ).reshape(4, 4)
                return risk, klass

            risk, klass = run("masked", True)
            self.assertNotEqual(float(risk[0, 3]), -9999.0)  # cropland cell kept
            self.assertNotEqual(float(risk[3, 0]), -9999.0)  # rangeland cell kept
            self.assertEqual(float(risk[1, 1]), -9999.0)  # no cropland, no rangeland: not scored
            self.assertEqual(float(klass[1, 1]), -9999.0)
            self.assertEqual(int((risk != -9999.0).sum()), 2)

            risk_unmasked, _ = run("unmasked", False)
            self.assertNotEqual(float(risk_unmasked[1, 1]), -9999.0)


if __name__ == "__main__":
    unittest.main()
