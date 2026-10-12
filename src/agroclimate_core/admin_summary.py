"""Summarise the risk map by administrative unit.

Each admin unit gets the share of its scored area in every risk class, its
area-weighted mean score, its worst class and, when land cover fractions are
given, how much cropland and rangeland sits in high or very high risk cells.

Only scored cells count. Cells outside cropland and rangeland are "not
applicable" in the map, so they are left out here too instead of diluting a
region's average with desert.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from osgeo import gdal, ogr

EARTH_RADIUS_KM = 6371.0088  # mean radius; the sphere is accurate to ~0.3% for areas at this scale
CLASS_NAMES = {1: "low", 2: "moderate", 3: "high", 4: "very high"}
CLASS_NODATA = 255
HIGH_RISK_MIN_CLASS = 3
HA_PER_KM2 = 100.0


def cell_area_km2(lat_top: float, lat_bottom: float, delta_lon_degrees: float) -> float:
    """Area of a lon/lat cell on a sphere, so cells shrink correctly away from the equator."""

    band = math.sin(math.radians(lat_top)) - math.sin(math.radians(lat_bottom))
    return EARTH_RADIUS_KM**2 * math.radians(delta_lon_degrees) * abs(band)


def _read_band(path: str | Path, gdal_type: int, dtype: Any) -> tuple[np.ndarray, gdal.Dataset]:
    dataset = gdal.Open(str(path))
    if dataset is None:
        raise RuntimeError(f"Could not open raster: {path}")
    raw = dataset.GetRasterBand(1).ReadRaster(
        0, 0, dataset.RasterXSize, dataset.RasterYSize, buf_type=gdal_type
    )
    return np.frombuffer(raw, dtype=dtype).reshape(dataset.RasterYSize, dataset.RasterXSize), dataset


def _zone_grid(admin_geojson: str | Path, template: gdal.Dataset, name_field: str, code_field: str | None):
    """Rasterise admin polygons onto the raster grid; a cell belongs to the unit holding its centre."""

    source = ogr.Open(str(admin_geojson))
    if source is None:
        raise RuntimeError(f"Could not open admin boundaries: {admin_geojson}")
    layer = source.GetLayer(0)
    fields = [layer.GetLayerDefn().GetFieldDefn(i).GetName() for i in range(layer.GetLayerDefn().GetFieldCount())]
    for wanted in filter(None, (name_field, code_field)):
        if wanted not in fields:
            raise KeyError(f"Admin layer has no field {wanted!r}; available fields: {', '.join(fields)}")

    memory = ogr.GetDriverByName("Memory").CreateDataSource("zones")
    zones = memory.CreateLayer("zones", srs=layer.GetSpatialRef(), geom_type=ogr.wkbUnknown)
    zones.CreateField(ogr.FieldDefn("_zone", ogr.OFTInteger))
    units: list[dict[str, Any]] = []
    for index, feature in enumerate(layer, start=1):
        clone = ogr.Feature(zones.GetLayerDefn())
        clone.SetGeometry(feature.GetGeometryRef().Clone())
        clone.SetField("_zone", index)
        zones.CreateFeature(clone)
        units.append({"name": feature.GetField(name_field), "code": feature.GetField(code_field) if code_field else None})

    mask = gdal.GetDriverByName("MEM").Create("", template.RasterXSize, template.RasterYSize, 1, gdal.GDT_Int32)
    mask.SetGeoTransform(template.GetGeoTransform())
    mask.SetProjection(template.GetProjection())
    gdal.RasterizeLayer(mask, [1], zones, options=["ATTRIBUTE=_zone"])
    raw = mask.GetRasterBand(1).ReadRaster(0, 0, template.RasterXSize, template.RasterYSize, buf_type=gdal.GDT_Int32)
    grid = np.frombuffer(raw, dtype=np.int32).reshape(template.RasterYSize, template.RasterXSize)
    return grid, units


def _area_grid(template: gdal.Dataset) -> np.ndarray:
    gt = template.GetGeoTransform()
    dlon = abs(gt[1])
    rows = np.arange(template.RasterYSize)
    tops = gt[3] + rows * gt[5]
    bottoms = tops + gt[5]
    per_row = np.array([cell_area_km2(top, bottom, dlon) for top, bottom in zip(tops, bottoms)])
    return np.repeat(per_row[:, None], template.RasterXSize, axis=1)


def _fraction_grid(path: str | Path | None, shape: tuple[int, int]) -> np.ndarray | None:
    if path is None:
        return None
    array, dataset = _read_band(path, gdal.GDT_Float32, np.float32)
    if array.shape != shape:
        raise ValueError(f"{path} is on a different grid than the risk raster ({array.shape} vs {shape})")
    nodata = dataset.GetRasterBand(1).GetNoDataValue()
    return np.where(array == nodata, 0.0, array) if nodata is not None else array


def summarize_by_admin(
    risk_class_path: str | Path,
    risk_score_path: str | Path,
    admin_geojson: str | Path,
    *,
    name_field: str,
    code_field: str | None = None,
    cultivated_fraction_path: str | Path | None = None,
    rangeland_fraction_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """One row per admin unit, in the order the units appear in the file."""

    classes, class_ds = _read_band(risk_class_path, gdal.GDT_Byte, np.uint8)
    scores, _ = _read_band(risk_score_path, gdal.GDT_Float32, np.float32)
    zone_grid, units = _zone_grid(admin_geojson, class_ds, name_field, code_field)
    areas = _area_grid(class_ds)
    fractions = {
        "cultivated": _fraction_grid(cultivated_fraction_path, classes.shape),
        "rangeland": _fraction_grid(rangeland_fraction_path, classes.shape),
    }

    rows: list[dict[str, Any]] = []
    for index, unit in enumerate(units, start=1):
        in_zone = zone_grid == index
        scored = in_zone & (classes != CLASS_NODATA)
        scored_area = float(areas[scored].sum())
        row: dict[str, Any] = {
            "admin_name": unit["name"],
            "admin_code": unit["code"],
            "cells_total": int(in_zone.sum()),
            "cells_scored": int(scored.sum()),
            "zone_area_km2": round(float(areas[in_zone].sum()), 1),
            "scored_area_km2": round(scored_area, 1),
        }
        if scored_area > 0:
            row["mean_risk_score"] = round(float((scores[scored] * areas[scored]).sum() / scored_area), 3)
            row["max_risk_class"] = CLASS_NAMES[int(classes[scored].max())]
            for value, name in CLASS_NAMES.items():
                share = areas[scored & (classes == value)].sum() / scored_area
                row[f"pct_{name.replace(' ', '_')}"] = round(float(share) * 100, 2)
        else:
            row["mean_risk_score"] = None
            row["max_risk_class"] = "n/a"
            for name in CLASS_NAMES.values():
                row[f"pct_{name.replace(' ', '_')}"] = None
        high_risk = scored & (classes >= HIGH_RISK_MIN_CLASS)
        row["high_risk_area_km2"] = round(float(areas[high_risk].sum()), 1)
        for label, fraction in fractions.items():
            if fraction is not None:
                # Fraction x cell area = hectares of that land cover in the cell.
                row[f"{label}_ha_total"] = round(float((areas[in_zone] * fraction[in_zone]).sum() * HA_PER_KM2), 1)
                row[f"{label}_ha_high_risk"] = round(float((areas[high_risk] * fraction[high_risk]).sum() * HA_PER_KM2), 1)
        rows.append(row)
    return rows


def write_summary_csv(rows: Sequence[Mapping[str, Any]], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_summary_geojson(
    admin_geojson: str | Path,
    rows: Sequence[Mapping[str, Any]],
    path: str | Path,
    *,
    key_field: str,
) -> Path:
    """Copy the admin boundaries with the summary columns added, ready to map in QGIS."""

    collection = json.loads(Path(admin_geojson).read_text(encoding="utf-8"))
    by_key = {row["admin_name"]: row for row in rows}
    for feature in collection["features"]:
        summary = by_key.get(feature["properties"].get(key_field))
        if summary is not None:
            feature["properties"].update({k: v for k, v in summary.items() if k not in feature["properties"]})
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection), encoding="utf-8")
    return path
