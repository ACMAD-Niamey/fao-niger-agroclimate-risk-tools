import json
import tempfile
import unittest
from pathlib import Path

from agroclimate_core.acmad_download import (
    AcmadDownloadError,
    AcmadProductNotFound,
    download_combined_product,
)


class FakeResponse:
    def __init__(self, status_code: int, content: bytes, content_type: str):
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}

    def iter_content(self, chunk_size: int = 1024):
        yield self.content

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, **kwargs):
        self.calls.append((url, dict(params or {})))
        return self.response


class CombinedDownloadTests(unittest.TestCase):
    def test_downloads_tiff_with_expected_query(self):
        session = FakeSession(FakeResponse(200, b"II*\x00data", "image/tiff"))
        with tempfile.TemporaryDirectory() as tmp:
            path = download_combined_product(
                data_name="combined_drought_hazard_era5",
                forecast_period="SON",
                year=2026,
                output_path=Path(tmp) / "h.tif",
                session=session,
            )
            self.assertEqual(path.read_bytes(), b"II*\x00data")
        url, params = session.calls[0]
        self.assertTrue(url.endswith("/api/data_api/download_combined_product/"))
        self.assertEqual(params, {"data_name": "combined_drought_hazard_era5", "forecast_period": "SON", "year": 2026})

    def test_missing_asset_raises_not_found_with_acmad_message(self):
        body = json.dumps({"error": "No combined_drought_hazard_era5 asset found for year=2026, period=JJA"}).encode()
        session = FakeSession(FakeResponse(404, body, "application/json"))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(AcmadProductNotFound) as caught:
            download_combined_product(
                data_name="combined_drought_hazard_era5", forecast_period="JJA", year=2026,
                output_path=Path(tmp) / "h.tif", session=session,
            )
        self.assertIn("period=JJA", str(caught.exception))
        self.assertIsInstance(caught.exception, AcmadDownloadError)

    def test_unexpected_json_is_an_error_not_a_tiff(self):
        session = FakeSession(FakeResponse(200, b'{"detail": "queued"}', "application/json"))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(AcmadDownloadError):
            download_combined_product(
                data_name="x", forecast_period="SON", year=2026, output_path=Path(tmp) / "h.tif", session=session
            )


if __name__ == "__main__":
    unittest.main()
