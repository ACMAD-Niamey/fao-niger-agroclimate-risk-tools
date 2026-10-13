from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np
from osgeo import gdal

from agroclimate_core.acmad_download import AcmadProductNotFound
from agroclimate_core.periods import PeriodUnavailableError
from agroclimate_core.workflow import (
    ConfigError,
    RunConfig,
    WorkflowCancelled,
    WorkflowServices,
    run_risk_workflow,
)
from helpers import write_boundary, write_raster

CDI_CODES = np.array([[0, 1, 4, 7], [0, 1, 4, 7], [0, 1, 4, 7], [0, 1, 4, 7]])
COMBINED_CLASSES = np.array([[1, 3], [5, 9]])  # 2x2 cells of 2 degrees over the 4x4 test extent

AVAILABILITY = {"cdi": {"latest_year": 2026, "latest_month": 9, "latest_dekad": 11, "start_year": 2015}}
CATALOG = {"datasets": [{"key": "combined_drought_hazard_era5", "available_periods": [{"year": 2026, "period": "SON"}]}]}


def fake_services(tmp: Path, *, boundary: Path) -> tuple[WorkflowServices, list[dict]]:
    calls: list[dict] = []

    def download_cdi(**kwargs):
        calls.append({"kind": "cdi", **{k: v for k, v in kwargs.items() if k != "output_path"}})
        return write_raster(Path(kwargs["output_path"]), CDI_CODES, nodata=-9999.0, dtype=gdal.GDT_Int32)

    def download_combined(**kwargs):
        calls.append({"kind": "combined", "forecast_period": kwargs["forecast_period"], "year": kwargs["year"]})
        if kwargs["forecast_period"] != "SON":
            raise AcmadProductNotFound("No asset found")
        return write_raster(Path(kwargs["output_path"]), COMBINED_CLASSES, cell=2.0, nodata=0, dtype=gdal.GDT_Byte)

    services = WorkflowServices(
        fetch_availability=lambda base_url: AVAILABILITY,
        fetch_catalog=lambda base_url: CATALOG,
        download_cdi=download_cdi,
        download_combined=download_combined,
        download_boundary=lambda path, geoserver_url: _copy(boundary, path),
    )
    return services, calls


def _copy(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.boundary = write_boundary(self.root / "boundary_src.geojson")
        self.services, self.calls = fake_services(self.root, boundary=self.boundary)

    def tearDown(self):
        self.tmp.cleanup()

    def _config(self, **overrides) -> RunConfig:
        values = dict(output_dir=self.root / "run", analysis_date=date(2026, 10, 12))
        values.update(overrides)
        return RunConfig(**values)

    def test_cdi_run_falls_back_to_latest_published_dekad_and_records_it(self):
        result = run_risk_workflow(self._config(), services=self.services)
        self.assertEqual(result.hazard_label, "2026-09-11")
        self.assertTrue(result.fallback)
        self.assertEqual(self.calls[0]["dekad"], 11)
        self.assertFalse(self.calls[0]["mask_nodata"])  # 'no drought' must stay a value
        for key in ("risk_score", "risk_class", "risk_stack", "cdi"):
            self.assertTrue(result.outputs[key].exists(), key)
        metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
        self.assertTrue(metadata["hazard"]["fallback"])
        self.assertEqual(metadata["hazard"]["lag_dekads"], 3)
        self.assertIn("ACMAD", metadata["boundary"]["source"])  # which outline clipped the map is recorded
        self.assertTrue(metadata["boundary"]["file"].endswith("niger_boundary_admin0.geojson"))

    def test_strict_dates_refuse_instead_of_falling_back(self):
        with self.assertRaises(PeriodUnavailableError):
            run_risk_workflow(self._config(strict_dates=True), services=self.services)
        self.assertEqual(self.calls, [])  # nothing was downloaded

    def test_explicit_period_is_exact_and_never_replaced(self):
        result = run_risk_workflow(
            self._config(analysis_date=None, year=2026, month=9, dekad=1), services=self.services
        )
        self.assertEqual(result.hazard_label, "2026-09-01")
        self.assertFalse(result.fallback)
        with self.assertRaises(PeriodUnavailableError):
            run_risk_workflow(
                self._config(analysis_date=None, year=2026, month=10, dekad=1), services=self.services
            )

    def test_combined_hazard_run_uses_the_exposure_grid(self):
        cultivated = write_raster(self.root / "cultivated.tif", np.full((8, 8), 2.0), cell=0.5, nodata=-9999.0)
        result = run_risk_workflow(
            self._config(hazard="combined", cultivated_raster=cultivated), services=self.services
        )
        self.assertEqual(result.hazard_label, "combined-2026-SON")
        self.assertIn("combined_hazard", result.outputs)
        grid = gdal.Open(str(result.outputs["risk_score"]))
        self.assertEqual((grid.RasterXSize, grid.RasterYSize), (8, 8))  # exposure grid, not the 2x2 hazard grid
        self.assertEqual(self.calls[0]["forecast_period"], "SON")

    def test_missing_season_is_reported_as_a_product_error(self):
        with self.assertRaises(AcmadProductNotFound):
            run_risk_workflow(
                self._config(hazard="combined", analysis_date=None, forecast_period="JJA", forecast_year=2026),
                services=self.services,
            )

    def test_progress_runs_from_zero_to_one_hundred_in_order(self):
        seen: list[tuple[float, str]] = []
        run_risk_workflow(self._config(), services=self.services, progress=lambda pct, msg: seen.append((pct, msg)))
        percentages = [pct for pct, _ in seen]
        self.assertEqual(percentages, sorted(percentages))
        self.assertEqual(percentages[-1], 100)
        self.assertTrue(all(message for _, message in seen))

    def test_cancellation_stops_before_the_next_step(self):
        steps = {"count": 0}

        def cancelled() -> bool:
            steps["count"] += 1
            return steps["count"] > 2

        with self.assertRaises(WorkflowCancelled):
            run_risk_workflow(self._config(), services=self.services, is_cancelled=cancelled)

    def test_mask_is_automatic_when_exposure_rasters_are_given(self):
        cultivated = np.zeros((8, 8))
        cultivated[0:2, 0:2] = 3  # only one 1-degree cell has cropland
        path = write_raster(self.root / "cultivated.tif", cultivated, cell=0.5, nodata=-9999.0)
        masked = run_risk_workflow(self._config(cultivated_raster=path), services=self.services)
        self.assertTrue(masked.mask_applied)
        unmasked = run_risk_workflow(
            self._config(cultivated_raster=path, output_dir=self.root / "run2", mask_to_agropastoral=False),
            services=self.services,
        )
        self.assertFalse(unmasked.mask_applied)

    def test_run_metadata_records_where_fetched_exposure_came_from(self):
        folder = self.root / "exposure"
        folder.mkdir()
        cultivated = write_raster(folder / "cultivated_exposure.tif", np.full((8, 8), 2.0), cell=0.5, nodata=-9999.0)
        (folder / "exposure_source.json").write_text(json.dumps({"source": "ACMAD prepared exposure", "base_url": "https://x"}), encoding="utf-8")
        result = run_risk_workflow(self._config(cultivated_raster=cultivated), services=self.services)
        metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["exposure"]["prepared_from"]["source"], "ACMAD prepared exposure")

        plain = write_raster(self.root / "plain.tif", np.full((8, 8), 2.0), cell=0.5, nodata=-9999.0)
        result = run_risk_workflow(self._config(cultivated_raster=plain, output_dir=self.root / "run2"), services=self.services)
        self.assertIsNone(json.loads(result.metadata_path.read_text(encoding="utf-8"))["exposure"]["prepared_from"])

    def test_invalid_configurations_are_rejected_with_plain_messages(self):
        with self.assertRaises(ConfigError):
            RunConfig(output_dir=self.root).validate()  # no date and no period
        with self.assertRaises(ConfigError):
            RunConfig(output_dir=self.root, hazard="combined").validate()  # combined needs a date or a season
        with self.assertRaises(ConfigError):
            RunConfig(output_dir=self.root, hazard="nope", analysis_date=date(2026, 1, 1)).validate()
        with self.assertRaises(ConfigError):
            RunConfig(output_dir=self.root, year=2026, month=13).validate()


if __name__ == "__main__":
    unittest.main()
