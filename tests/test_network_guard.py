from __future__ import annotations

import time
import unittest

import requests
from osgeo import gdal

import helpers  # noqa: F401  (importing it installs the guard)


class NetworkGuardTests(unittest.TestCase):
    def test_requests_to_the_real_network_are_refused(self):
        with self.assertRaises(RuntimeError) as caught:
            requests.get("https://example.org/")
        self.assertIn("real network", str(caught.exception))

    def test_a_session_object_is_refused_too(self):
        with self.assertRaises(RuntimeError):
            requests.Session().post("https://example.org/", json={})

    def test_remote_raster_reads_fail_fast_instead_of_downloading(self):
        started = time.monotonic()
        self.assertIsNone(gdal.Open("/vsicurl/https://example.org/none.tif"))
        self.assertLess(time.monotonic() - started, 10)


if __name__ == "__main__":
    unittest.main()
