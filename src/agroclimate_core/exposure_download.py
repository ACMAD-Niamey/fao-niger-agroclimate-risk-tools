"""Fetch the exposure rasters ACMAD has already prepared, instead of building them.

Building exposure from ESA WorldCover downloads hundreds of megabytes and takes
minutes. The result is four small rasters (about 66 KB in all) that ACMAD
publishes on its public storage, so a user can have them in seconds, with no
credentials.

Nothing is trusted blindly. Each file must open as a raster, hold values in the
expected range, and sit on the same grid as the others. Files are checked in a
scratch folder first and only then moved into place, so a failed or partial
download never leaves a half-written exposure folder that a later run would
mistake for a good one.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import requests
from osgeo import gdal

from .cancellation import WorkflowCancelled

logger = logging.getLogger(__name__)

ACMAD_EXPOSURE_BASE_URL = "https://minio.acmad.org/geodata/fao-niger-agroclimate/niger/exposure"
EXPOSURE_FILES = (
    "cultivated_exposure.tif",
    "cultivated_fraction.tif",
    "rangeland_exposure.tif",
    "rangeland_fraction.tif",
)
SOURCE_FILE = "exposure_source.json"
MAX_FILE_BYTES = 20 * 1024 * 1024  # the real files are tens of KB; anything huge is not what we expect
NODATA = -9999.0
_TOLERANCE = 1e-3  # float rounding at the edges of the allowed range

ProgressCallback = Callable[[float, str], None]
CancelCheck = Callable[[], bool]


class ExposureDownloadError(RuntimeError):
    """The prepared exposure could not be fetched or did not pass checks. Messages are plain language."""


def _check_cancel(is_cancelled: Optional[CancelCheck]) -> None:
    if is_cancelled is not None and is_cancelled():
        raise WorkflowCancelled("Getting the exposure was cancelled.")


def _value_range(name: str) -> Tuple[float, float, str]:
    """The legal range of a file's values, from its name: scores are 0-3, fractions 0-1."""

    return (0.0, 3.0, "0 to 3") if name.endswith("_exposure.tif") else (0.0, 1.0, "0 to 1")


def _validate(paths: Dict[str, Path]) -> None:
    grids = {}
    for name, path in paths.items():
        dataset = gdal.Open(str(path))
        if dataset is None or dataset.RasterCount != 1:
            raise ExposureDownloadError(f"{name} from ACMAD is not a valid single-band raster.")
        raw = dataset.GetRasterBand(1).ReadRaster(0, 0, dataset.RasterXSize, dataset.RasterYSize, buf_type=gdal.GDT_Float32)
        values = np.frombuffer(raw, dtype=np.float32)
        nodata = dataset.GetRasterBand(1).GetNoDataValue()
        valid = np.isfinite(values) & ((values != nodata) if nodata is not None else True)
        if not valid.any():
            raise ExposureDownloadError(f"{name} from ACMAD has no valid cells.")
        low, high, text = _value_range(name)
        if values[valid].min() < low - _TOLERANCE or values[valid].max() > high + _TOLERANCE:
            raise ExposureDownloadError(f"{name} from ACMAD has values outside {text}, so it was not used.")
        grids[name] = (dataset.RasterXSize, dataset.RasterYSize, tuple(round(v, 9) for v in dataset.GetGeoTransform()))
    if len(set(grids.values())) != 1:
        raise ExposureDownloadError("The exposure rasters from ACMAD are not on the same grid, so they were not used.")


def _download(client: Any, url: str, name: str, target: Path, timeout_seconds: float) -> None:
    try:
        response = client.get(url, timeout=timeout_seconds)
    except requests.RequestException as exc:
        # The raw exception text can be long and technical; keep it in the log, not in front of the user.
        logger.warning("Fetching %s failed: %s", url, exc)
        raise ExposureDownloadError("Could not reach ACMAD's server to get the prepared exposure.") from exc
    if response.status_code == 404:
        raise ExposureDownloadError(f"ACMAD's server does not have {name}.")
    if response.status_code != 200:
        raise ExposureDownloadError(f"ACMAD's server answered with HTTP {response.status_code} for {name}.")
    if len(response.content) > MAX_FILE_BYTES:
        raise ExposureDownloadError(f"{name} from ACMAD is much larger than expected, so it was not used.")
    target.write_bytes(response.content)


def _install(staged: Dict[str, Path], output_dir: Path) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    installed: Dict[str, Path] = {}
    for name, path in staged.items():
        destination = output_dir / name
        partial = output_dir / (name + ".part")
        shutil.copyfile(path, partial)
        os.replace(partial, destination)  # replace is atomic on one filesystem: never a half-written file
        installed[name.rsplit(".", 1)[0]] = destination
    return installed


def fetch_prepared_exposure(
    output_dir: str | Path,
    *,
    base_url: str = ACMAD_EXPOSURE_BASE_URL,
    session: Optional[requests.Session] = None,
    timeout_seconds: float = 60.0,
    progress: Optional[ProgressCallback] = None,
    is_cancelled: Optional[CancelCheck] = None,
) -> Dict[str, Path]:
    """Download, check and install ACMAD's prepared exposure rasters; return their paths."""

    output_dir = Path(output_dir)
    client = session or requests.Session()
    base = base_url.rstrip("/")

    def report(percent: float, message: str) -> None:
        if progress is not None:
            progress(percent, message)

    with tempfile.TemporaryDirectory(prefix="agroclimate_exposure_") as scratch:
        staged: Dict[str, Path] = {}
        hashes: Dict[str, Dict[str, Any]] = {}
        for index, name in enumerate(EXPOSURE_FILES):
            _check_cancel(is_cancelled)
            report(100.0 * index / (len(EXPOSURE_FILES) + 1), f"Downloading {name} ({index + 1} of {len(EXPOSURE_FILES)})")
            target = Path(scratch) / name
            _download(client, f"{base}/{name}", name, target, timeout_seconds)
            staged[name] = target
            data = target.read_bytes()
            hashes[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

        _check_cancel(is_cancelled)
        report(100.0 * len(EXPOSURE_FILES) / (len(EXPOSURE_FILES) + 1), "Checking the files")
        _validate(staged)
        installed = _install(staged, output_dir)

    (output_dir / SOURCE_FILE).write_text(
        json.dumps(
            {
                "source": "ACMAD prepared exposure (from ESA WorldCover 2021)",
                "base_url": base,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "files": hashes,
                "note": "Scores use the provisional thresholds of 5%, 25% and 50% of a cell. They are under review.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report(100, "Exposure rasters are ready")
    return installed


def read_exposure_source(directory: str | Path) -> Optional[Dict[str, Any]]:
    """Where an exposure folder came from, if it was fetched with ``fetch_prepared_exposure``."""

    path = Path(directory) / SOURCE_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
