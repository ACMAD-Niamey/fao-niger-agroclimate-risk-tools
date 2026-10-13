from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import requests

from agroclimate_core.admin1_download import (
    ADMIN1_ATTRIBUTION,
    ADMIN1_FILENAME,
    AdminBoundaryDownloadError,
    fetch_admin1,
    read_admin1_source,
)
from agroclimate_core.cancellation import WorkflowCancelled
import helpers  # noqa: F401  (installs the network guard)

URL = "https://minio.example.org/geodata/niger/boundaries/niger_admin1_ocha.geojson"


def polygon(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def collection(features=None, **override) -> bytes:
    features = features if features is not None else [
        {"type": "Feature", "properties": {"adm1_name": "Zinder", "adm1_pcode": "NE007"}, "geometry": polygon(8, 12, 12, 16)},
        {"type": "Feature", "properties": {"adm1_name": "Maradi", "adm1_pcode": "NE004"}, "geometry": polygon(6, 12, 8, 14)},
    ]
    return json.dumps({"type": "FeatureCollection", "features": features, **override}).encode()


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b""):
        self.status_code, self.content = status_code, content


class FakeSession:
    def __init__(self, response=None, error: Exception | None = None):
        self.response, self.error, self.urls = response, error, []

    def get(self, url, timeout=None, **_kwargs):
        self.urls.append(url)
        if self.error:
            raise self.error
        return self.response


class Admin1DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "boundaries"

    def tearDown(self):
        self.tmp.cleanup()

    def fetch(self, response, **kwargs):
        return fetch_admin1(self.out, url=URL, session=FakeSession(response), **kwargs)

    def test_downloads_validates_installs_and_records_the_origin(self):
        body = collection()
        path = self.fetch(FakeResponse(200, body))
        self.assertEqual(path, self.out / ADMIN1_FILENAME)
        self.assertEqual(path.read_bytes(), body)
        source = read_admin1_source(self.out)
        self.assertEqual(source["url"], URL)
        self.assertEqual(source["sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(source["features"], 2)
        self.assertEqual(source["attribution"], ADMIN1_ATTRIBUTION)
        self.assertIn("CC BY-IGO", ADMIN1_ATTRIBUTION)

    def test_a_missing_file_is_a_plain_error_and_leaves_nothing(self):
        with self.assertRaises(AdminBoundaryDownloadError) as caught:
            self.fetch(FakeResponse(404, b"nope"))
        self.assertIn("does not have", str(caught.exception))
        self.assertFalse((self.out / ADMIN1_FILENAME).exists())

    def test_other_http_errors_name_the_status(self):
        with self.assertRaises(AdminBoundaryDownloadError) as caught:
            self.fetch(FakeResponse(503, b""))
        self.assertIn("503", str(caught.exception))

    def test_an_unreachable_server_gives_a_plain_message_without_raw_exception_text(self):
        with self.assertRaises(AdminBoundaryDownloadError) as caught:
            fetch_admin1(self.out, url=URL, session=FakeSession(error=requests.ConnectionError("HTTPSConnectionPool(host='x')")))
        self.assertIn("Could not reach", str(caught.exception))
        self.assertNotIn("HTTPSConnectionPool", str(caught.exception))

    def test_a_web_page_instead_of_geojson_is_rejected(self):
        with self.assertRaises(AdminBoundaryDownloadError) as caught:
            self.fetch(FakeResponse(200, b"<html>Sign in</html>"))
        self.assertIn("not valid", str(caught.exception))
        self.assertFalse((self.out / ADMIN1_FILENAME).exists())

    def test_geojson_without_the_expected_fields_is_rejected(self):
        body = collection([{"type": "Feature", "properties": {"name": "Zinder"}, "geometry": polygon(0, 0, 1, 1)}])
        with self.assertRaises(AdminBoundaryDownloadError) as caught:
            self.fetch(FakeResponse(200, body))
        self.assertIn("adm1_name", str(caught.exception))

    def test_points_are_not_regions(self):
        body = collection([{"type": "Feature", "properties": {"adm1_name": "A", "adm1_pcode": "N1"}, "geometry": {"type": "Point", "coordinates": [1, 1]}}])
        with self.assertRaises(AdminBoundaryDownloadError) as caught:
            self.fetch(FakeResponse(200, body))
        self.assertIn("polygon", str(caught.exception).lower())

    def test_an_empty_collection_is_rejected(self):
        with self.assertRaises(AdminBoundaryDownloadError):
            self.fetch(FakeResponse(200, collection([])))

    def test_coordinates_that_are_not_longitude_and_latitude_are_rejected(self):
        body = collection([{"type": "Feature", "properties": {"adm1_name": "A", "adm1_pcode": "N1"}, "geometry": polygon(500000, 1000000, 600000, 1100000)}])
        with self.assertRaises(AdminBoundaryDownloadError) as caught:
            self.fetch(FakeResponse(200, body))
        self.assertIn("longitude", str(caught.exception))

    def test_a_failed_refresh_keeps_the_boundaries_already_in_place(self):
        self.fetch(FakeResponse(200, collection()))
        before = (self.out / ADMIN1_FILENAME).read_bytes()
        with self.assertRaises(AdminBoundaryDownloadError):
            self.fetch(FakeResponse(200, b"garbage"))
        self.assertEqual((self.out / ADMIN1_FILENAME).read_bytes(), before)
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.endswith(".part")], [])

    def test_cancelling_before_the_download_writes_nothing(self):
        with self.assertRaises(WorkflowCancelled):
            self.fetch(FakeResponse(200, collection()), is_cancelled=lambda: True)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
