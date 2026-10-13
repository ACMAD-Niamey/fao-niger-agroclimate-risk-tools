"""Small synthetic-raster helpers shared by tests (no network, no QGIS)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import requests
from osgeo import gdal


def block_real_network() -> None:
    """Make any accidental real network call in a test fail loudly instead of quietly succeeding.

    Tests use fake services. Without this, a test that forgot to fake one (it happened once: a
    "remember my choice" test started a real land cover download) still passes, just slowly.
    """

    def refuse(self, method, url, *args, **kwargs):
        raise RuntimeError(f"A test tried to use the real network: {method} {url}")

    requests.sessions.Session.request = refuse
    # GDAL's /vsicurl/ reads (land cover tiles) do not go through requests: send them to a closed port.
    gdal.SetConfigOption("GDAL_HTTP_PROXY", "127.0.0.1:9")
    gdal.SetConfigOption("GDAL_HTTP_TIMEOUT", "2")
    gdal.SetConfigOption("GDAL_HTTP_MAX_RETRY", "0")


block_real_network()


def write_raster(
    path: Path,
    array: np.ndarray,
    *,
    origin: Sequence[float] = (0.0, 4.0),
    cell: float = 1.0,
    nodata: float | None = None,
    dtype: int = gdal.GDT_Float32,
) -> Path:
    """Write a single-band GeoTIFF in EPSG:4326 from a 2-D array."""

    rows, cols = array.shape
    dataset = gdal.GetDriverByName("GTiff").Create(str(path), cols, rows, 1, dtype)
    dataset.SetGeoTransform((origin[0], cell, 0, origin[1], 0, -cell))
    dataset.SetProjection("EPSG:4326")
    band = dataset.GetRasterBand(1)
    if nodata is not None:
        band.SetNoDataValue(nodata)
    numpy_type = {gdal.GDT_Byte: "uint8", gdal.GDT_Int32: "int32"}.get(dtype, "float32")
    data = array.astype(numpy_type)
    band.WriteRaster(0, 0, cols, rows, data.tobytes(), buf_type=dtype)
    dataset.FlushCache()
    return path


def write_boundary(path: Path, west: float = 0.0, south: float = 0.0, east: float = 4.0, north: float = 4.0) -> Path:
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    feature = {"type": "Feature", "properties": {"name": "test"}, "geometry": {"type": "Polygon", "coordinates": [ring]}}
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}), encoding="utf-8")
    return path
