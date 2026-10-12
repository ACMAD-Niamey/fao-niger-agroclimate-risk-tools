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


if __name__ == "__main__":
    unittest.main()
