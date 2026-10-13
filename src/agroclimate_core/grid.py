"""The common output grid for Niger, defined from the boundary alone.

Hazard products are on a 0.1 degree lattice (the CDI) or a coarser one that
nests inside it. Snapping the boundary's extent outward to that lattice gives a
grid every product lines up with, without needing to download any hazard first.
"""

from __future__ import annotations

import math
from pathlib import Path

from osgeo import gdal, ogr

GRID_CELL_DEGREES = 0.1
_EPSILON = 1e-9  # keeps a boundary exactly on a grid line from adding an empty row or column


def make_grid_template(boundary_geojson: str | Path, output_path: str | Path, *, cell: float = GRID_CELL_DEGREES) -> Path:
    """Write an empty float raster covering the boundary on the ``cell``-degree lattice."""

    vector = ogr.Open(str(boundary_geojson))
    if vector is None:
        raise RuntimeError(f"Could not open boundary: {boundary_geojson}")
    min_x, max_x, min_y, max_y = vector.GetLayer(0).GetExtent()

    first_col = math.floor(min_x / cell + _EPSILON)
    last_col = math.ceil(max_x / cell - _EPSILON)
    first_row = math.floor(min_y / cell + _EPSILON)
    last_row = math.ceil(max_y / cell - _EPSILON)
    columns, rows = last_col - first_col, last_row - first_row
    if columns <= 0 or rows <= 0:
        raise ValueError("The boundary is empty or has no area.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset = gdal.GetDriverByName("GTiff").Create(str(output_path), columns, rows, 1, gdal.GDT_Float32)
    if dataset is None:
        raise RuntimeError(f"Could not create grid template: {output_path}")
    dataset.SetGeoTransform((first_col * cell, cell, 0, last_row * cell, 0, -cell))
    dataset.SetProjection("EPSG:4326")
    dataset.FlushCache()
    return output_path
