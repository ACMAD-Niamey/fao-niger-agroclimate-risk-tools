"""Fetch Niger's administrative level 1 regions from ACMAD's storage.

The region summary needs polygons for Niger's eight regions. ACMAD's GeoServer
has no admin level 1 layer, and finding a suitable file is a hurdle for a new
user, so a copy of the official OCHA boundaries is published beside the
prepared exposure. It is small (about 180 KB) and publicly readable.

Like the exposure download, the file is checked before it is used (it must be
GeoJSON polygons with the expected name and code fields, in longitude and
latitude) and is moved into place atomically, so a failed download never
replaces a good file with a broken one.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests

from .cancellation import WorkflowCancelled

logger = logging.getLogger(__name__)

ACMAD_ADMIN1_URL = "https://minio.acmad.org/geodata/fao-niger-agroclimate/niger/boundaries/niger_admin1_ocha.geojson"
ADMIN1_FILENAME = "niger_admin1_ocha.geojson"
ADMIN1_SOURCE_FILE = "niger_admin1_source.json"
ADMIN1_NAME_FIELD = "adm1_name"
ADMIN1_CODE_FIELD = "adm1_pcode"
ADMIN1_ATTRIBUTION = "Administrative boundaries: OCHA Common Operational Dataset (CC BY-IGO)."
MAX_BYTES = 5 * 1024 * 1024  # the real file is about 180 KB

CancelCheck = Callable[[], bool]


class AdminBoundaryDownloadError(RuntimeError):
    """The regions could not be fetched or did not pass checks. Messages are plain language."""


def _points(geometry: Dict[str, Any]):
    """Every [x, y] in a Polygon or MultiPolygon."""

    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    for polygon in polygons:
        for ring in polygon:
            yield from ring


def validate_admin_geojson(data: bytes) -> int:
    """Check the bytes are polygon regions with name and code fields; return how many regions."""

    try:
        collection = json.loads(data.decode("utf-8"))
        features = collection["features"]
        assert collection["type"] == "FeatureCollection" and isinstance(features, list)
    except (ValueError, KeyError, AssertionError, UnicodeDecodeError, TypeError):
        raise AdminBoundaryDownloadError("The regions file from ACMAD is not valid GeoJSON, so it was not used.") from None
    if not features:
        raise AdminBoundaryDownloadError("The regions file from ACMAD has no regions in it, so it was not used.")

    for feature in features:
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in ("Polygon", "MultiPolygon"):
            raise AdminBoundaryDownloadError("The regions file from ACMAD does not contain polygons, so it was not used.")
        properties = feature.get("properties") or {}
        for field in (ADMIN1_NAME_FIELD, ADMIN1_CODE_FIELD):
            if not properties.get(field):
                raise AdminBoundaryDownloadError(
                    f"The regions file from ACMAD is missing the field {field}, so it was not used."
                )
        for x, y in _points(geometry):
            if not (-180 <= x <= 180 and -90 <= y <= 90):
                raise AdminBoundaryDownloadError(
                    "The regions file from ACMAD is not in longitude and latitude, so it was not used."
                )
    return len(features)


def fetch_admin1(
    output_dir: str | Path,
    *,
    url: str = ACMAD_ADMIN1_URL,
    session: Optional[requests.Session] = None,
    timeout_seconds: float = 60.0,
    is_cancelled: Optional[CancelCheck] = None,
) -> Path:
    """Download, check and install the admin level 1 regions; return the file's path."""

    if is_cancelled is not None and is_cancelled():
        raise WorkflowCancelled("Getting the regions was cancelled.")
    client = session or requests.Session()
    try:
        response = client.get(url, timeout=timeout_seconds)
    except requests.RequestException as exc:
        logger.warning("Fetching %s failed: %s", url, exc)  # the technical detail stays in the log
        raise AdminBoundaryDownloadError("Could not reach ACMAD's server to get the regions.") from exc
    if response.status_code == 404:
        raise AdminBoundaryDownloadError("ACMAD's server does not have the regions file.")
    if response.status_code != 200:
        raise AdminBoundaryDownloadError(f"ACMAD's server answered with HTTP {response.status_code} for the regions file.")
    data = response.content
    if len(data) > MAX_BYTES:
        raise AdminBoundaryDownloadError("The regions file from ACMAD is much larger than expected, so it was not used.")

    regions = validate_admin_geojson(data)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / ADMIN1_FILENAME
    partial = output_dir / (ADMIN1_FILENAME + ".part")
    partial.write_bytes(data)
    os.replace(partial, destination)  # atomic: never a half-written file under the real name
    (output_dir / ADMIN1_SOURCE_FILE).write_text(
        json.dumps(
            {
                "source": "ACMAD copy of the OCHA Common Operational Dataset, Niger administrative level 1",
                "url": url,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "features": regions,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "attribution": ADMIN1_ATTRIBUTION,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return destination


def read_admin1_source(directory: str | Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads((Path(directory) / ADMIN1_SOURCE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
