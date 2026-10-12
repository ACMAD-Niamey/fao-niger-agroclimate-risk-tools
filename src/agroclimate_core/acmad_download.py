"""ACMAD API download helpers for raster products."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests


DEFAULT_ACMAD_API_BASE_URL = "https://ada.acmad.org"
DOWNLOAD_DATA_PATH = "/api/data_api/download_data/"


class AcmadDownloadError(RuntimeError):
    """Raised when an ACMAD raster download cannot be completed."""


def _absolute_url(base_url: str, url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return urljoin(base_url.rstrip("/") + "/", url.lstrip("/"))


def _is_json_response(response: requests.Response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        return True
    return response.content[:1] in (b"{", b"[")


def _write_response_content(response: requests.Response, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as fp:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                fp.write(chunk)
    if output_path.stat().st_size == 0:
        raise AcmadDownloadError(f"Downloaded file is empty: {output_path}")
    return output_path


def _poll_download_job(
    session: requests.Session,
    base_url: str,
    status_url: str,
    *,
    poll_seconds: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    url = _absolute_url(base_url, status_url)

    while time.monotonic() < deadline:
        response = session.get(url, timeout=60)
        response.raise_for_status()
        payload = response.json()
        status = str(payload.get("status", "")).lower()
        if status in {"finished", "complete", "completed", "success", "done"}:
            return payload
        if status in {"failed", "error", "download_failed"}:
            raise AcmadDownloadError(f"ACMAD download job failed: {json.dumps(payload, sort_keys=True)}")
        time.sleep(poll_seconds)

    raise AcmadDownloadError(f"Timed out waiting for ACMAD download job: {url}")


def download_acmad_raster(
    *,
    data_name: str,
    year: int,
    month: int,
    output_path: str | Path,
    dekad: int | None = None,
    accumulation: int | None = None,
    mask_nodata: bool = True,
    base_url: str = DEFAULT_ACMAD_API_BASE_URL,
    poll_seconds: float = 5.0,
    timeout_seconds: float = 600.0,
) -> Path:
    """Download one ACMAD raster product to a local file.

    ACMAD's ``download_data`` endpoint streams an existing GeoTIFF immediately
    when available, or returns a background-job payload that must be polled.
    This helper supports both response modes.
    """

    output_path = Path(output_path)
    params: dict[str, Any] = {
        "data_name": data_name,
        "year": int(year),
        "month": int(month),
        "mask_nodata": str(bool(mask_nodata)).lower(),
    }
    if dekad is not None:
        params["dekad"] = int(dekad)
    if accumulation is not None:
        params["accumulation"] = int(accumulation)

    session = requests.Session()
    url = _absolute_url(base_url, DOWNLOAD_DATA_PATH)
    response = session.get(url, params=params, stream=True, timeout=120)
    response.raise_for_status()

    if response.status_code == 200 and not _is_json_response(response):
        return _write_response_content(response, output_path)

    payload = response.json()
    download_url = payload.get("download_url") or payload.get("file_url") or payload.get("url")
    if download_url:
        file_response = session.get(_absolute_url(base_url, str(download_url)), stream=True, timeout=120)
        file_response.raise_for_status()
        return _write_response_content(file_response, output_path)

    status_url = payload.get("status_url") or payload.get("poll_url")
    job_id = payload.get("job_id") or payload.get("id")
    if not status_url and job_id:
        status_url = f"/api/data_api/download/status/{job_id}/"
    if not status_url:
        raise AcmadDownloadError(f"ACMAD response did not include a download or status URL: {payload}")

    final_payload = _poll_download_job(
        session,
        base_url,
        str(status_url),
        poll_seconds=poll_seconds,
        timeout_seconds=timeout_seconds,
    )
    download_url = final_payload.get("download_url") or final_payload.get("file_url") or final_payload.get("url")
    if not download_url and job_id:
        download_url = f"/api/data_api/download/file/{job_id}/"
    if not download_url:
        raise AcmadDownloadError(f"Completed ACMAD job did not include a file URL: {final_payload}")

    file_response = session.get(_absolute_url(base_url, str(download_url)), stream=True, timeout=120)
    file_response.raise_for_status()
    return _write_response_content(file_response, output_path)
