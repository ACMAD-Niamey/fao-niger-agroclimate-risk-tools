"""Small synthetic-raster helpers shared by tests (no network, no QGIS)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
from osgeo import gdal


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
