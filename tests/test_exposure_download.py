from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import requests

from agroclimate_core.cancellation import WorkflowCancelled
from agroclimate_core.exposure_download import (
    EXPOSURE_FILES,
    SOURCE_FILE,
    ExposureDownloadError,
    fetch_prepared_exposure,
    read_exposure_source,
)
from agroclimate_core.exposure_workflow import ExposureConfig, exposure_files_exist, run_exposure_preparation
from agroclimate_core.hazard_selection import ConfigError
from agroclimate_core.workflow import WorkflowServices
from helpers import write_raster

BASE = "https://minio.example.org/geodata/niger/exposure"


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b""):
        self.status_code, self.content = status_code, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, files: dict[str, bytes], status: dict[str, int] | None = None, error: Exception | None = None):
        self.files, self.status, self.error, self.urls = files, status or {}, error, []

    def get(self, url, timeout=None, **_kwargs):
        self.urls.append(url)
        if self.error:
            raise self.error
        name = url.rsplit("/", 1)[-1]
        code = self.status.get(name, 200)
        return FakeResponse(code, self.files.get(name, b"") if code == 200 else b"not found")


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.files = self._good_files()

    def tearDown(self):
        self.tmp.cleanup()

    def _good_files(self, **overrides) -> dict[str, bytes]:
        """Four small rasters on one grid: scores 0-3, fractions 0-1, nodata -9999."""

        source = self.root / "source"
        source.mkdir(exist_ok=True)
        arrays = {
            "cultivated_exposure.tif": np.array([[0, 1, 2], [3, 1, -9999]], dtype="float32"),
            "rangeland_exposure.tif": np.array([[3, 2, 1], [0, 1, -9999]], dtype="float32"),
            "cultivated_fraction.tif": np.array([[0, 0.1, 0.3], [0.9, 0.2, -9999]], dtype="float32"),
            "rangeland_fraction.tif": np.array([[0.9, 0.5, 0.1], [0, 0.2, -9999]], dtype="float32"),
        }
        arrays.update(overrides)
        out = {}
        for name, array in arrays.items():
            path = write_raster(source / name, array, origin=(0.0, 2.0), cell=1.0, nodata=-9999.0)
            out[name] = path.read_bytes()
        return out

    def fetch(self, session=None, output=None, **kwargs):
        return fetch_prepared_exposure(output or self.root / "exposure", base_url=BASE, session=session or FakeSession(self.files), **kwargs)

    def test_downloads_the_four_rasters_and_records_where_they_came_from(self):
        session = FakeSession(self.files)
        outputs = self.fetch(session)
        self.assertEqual(set(outputs), {name.rsplit(".", 1)[0] for name in EXPOSURE_FILES})
        self.assertTrue(exposure_files_exist(self.root / "exposure"))
        self.assertEqual(sorted(u.rsplit("/", 1)[-1] for u in session.urls), sorted(EXPOSURE_FILES))
        source = read_exposure_source(self.root / "exposure")
        self.assertEqual(source["base_url"], BASE)
        self.assertEqual(
            source["files"]["cultivated_exposure.tif"]["sha256"], hashlib.sha256(self.files["cultivated_exposure.tif"]).hexdigest()
        )
        self.assertIn("provisional", source["note"])

    def test_a_missing_file_fails_clearly_and_leaves_nothing_behind(self):
        session = FakeSession(self.files, status={"rangeland_fraction.tif": 404})
        with self.assertRaises(ExposureDownloadError) as caught:
            self.fetch(session)
        self.assertIn("rangeland_fraction.tif", str(caught.exception))
        self.assertFalse(exposure_files_exist(self.root / "exposure"))  # not even the files that did download
        leftovers = list((self.root / "exposure").glob("*")) if (self.root / "exposure").exists() else []
        self.assertEqual(leftovers, [])

    def test_a_web_page_instead_of_a_raster_is_rejected(self):
        files = dict(self.files, **{"cultivated_exposure.tif": b"<html>Login required</html>"})
        with self.assertRaises(ExposureDownloadError) as caught:
            self.fetch(FakeSession(files))
        self.assertIn("cultivated_exposure.tif", str(caught.exception))
        self.assertFalse(exposure_files_exist(self.root / "exposure"))

    def test_scores_outside_zero_to_three_are_rejected(self):
        bad = self._good_files(**{"cultivated_exposure.tif": np.array([[0, 1, 2], [7, 1, -9999]], dtype="float32")})
        with self.assertRaises(ExposureDownloadError) as caught:
            self.fetch(FakeSession(bad))
        self.assertIn("0 to 3", str(caught.exception))

    def test_fractions_outside_zero_to_one_are_rejected(self):
        bad = self._good_files(**{"rangeland_fraction.tif": np.array([[0, 5, 0], [0, 0, -9999]], dtype="float32")})
        with self.assertRaises(ExposureDownloadError) as caught:
            self.fetch(FakeSession(bad))
        self.assertIn("0 to 1", str(caught.exception))

    def test_rasters_on_different_grids_are_rejected(self):
        source = self.root / "other"
        source.mkdir()
        other = write_raster(source / "x.tif", np.zeros((4, 4), dtype="float32"), origin=(0.0, 4.0), cell=1.0, nodata=-9999.0)
        files = dict(self.files, **{"rangeland_exposure.tif": other.read_bytes()})
        with self.assertRaises(ExposureDownloadError) as caught:
            self.fetch(FakeSession(files))
        self.assertIn("same grid", str(caught.exception))

    def test_an_unreachable_server_gives_a_plain_message_without_raw_exception_text(self):
        with self.assertRaises(ExposureDownloadError) as caught:
            self.fetch(FakeSession(self.files, error=requests.ConnectionError("HTTPSConnectionPool(host='x'): Max retries")))
        self.assertIn("Could not reach", str(caught.exception))
        self.assertNotIn("HTTPSConnectionPool", str(caught.exception))

    def test_a_failed_refresh_keeps_the_exposure_already_in_place(self):
        self.fetch()
        before = (self.root / "exposure" / "cultivated_exposure.tif").read_bytes()
        with self.assertRaises(ExposureDownloadError):
            self.fetch(FakeSession(self.files, status={"rangeland_exposure.tif": 500}))
        self.assertTrue(exposure_files_exist(self.root / "exposure"))
        self.assertEqual((self.root / "exposure" / "cultivated_exposure.tif").read_bytes(), before)

    def test_cancelling_stops_the_download_and_writes_nothing(self):
        with self.assertRaises(WorkflowCancelled):
            self.fetch(is_cancelled=lambda: True)
        self.assertFalse(exposure_files_exist(self.root / "exposure"))

    def test_progress_is_ordered_and_ends_at_one_hundred(self):
        seen: list[float] = []
        self.fetch(progress=lambda percent, _message: seen.append(percent))
        self.assertEqual(seen, sorted(seen))
        self.assertEqual(seen[-1], 100)


class WorkflowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.downloads = []

        def download_exposure(output_dir, **kwargs):
            self.downloads.append(Path(output_dir))
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            for name in EXPOSURE_FILES:
                write_raster(Path(output_dir) / name, np.ones((2, 2), dtype="float32"), nodata=-9999.0)
            return {name.rsplit(".", 1)[0]: Path(output_dir) / name for name in EXPOSURE_FILES}

        def no_boundary(*_a, **_k):
            raise AssertionError("fetching ACMAD's prepared exposure must not download the boundary or any land cover")

        unused = lambda *a, **k: None  # noqa: E731
        self.services = WorkflowServices(unused, unused, unused, unused, no_boundary, download_exposure)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_acmad_source_downloads_the_prepared_files_only(self):
        config = ExposureConfig(output_dir=self.root / "exposure", source="acmad")
        outputs = run_exposure_preparation(config, services=self.services)
        self.assertEqual(self.downloads, [self.root / "exposure"])
        self.assertIn("cultivated_exposure", outputs)

    def test_an_unknown_source_is_a_configuration_error(self):
        with self.assertRaises(ConfigError):
            run_exposure_preparation(ExposureConfig(output_dir=self.root, source="elsewhere"), services=self.services)

    def test_worldcover_remains_the_default_source_for_the_command_line(self):
        self.assertEqual(ExposureConfig().source, "worldcover")


if __name__ == "__main__":
    unittest.main()
