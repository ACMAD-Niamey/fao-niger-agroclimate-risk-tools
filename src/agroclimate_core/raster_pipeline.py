"""Raster pipeline for the first agropastoral drought risk product."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from osgeo import gdal

from .risk import classify_risk


RASTER_NODATA = -9999.0
CLASS_NODATA = 255


@dataclass(frozen=True)
class ExposureDefaults:
    cultivated: float = 2.0
    rangeland: float = 2.0
    water_points: float = 1.0


def _open_dataset(path: str | Path) -> gdal.Dataset:
    dataset = gdal.Open(str(path))
    if dataset is None:
        raise RuntimeError(f"Could not open raster: {path}")
    return dataset


def _band_array(dataset: gdal.Dataset) -> tuple[np.ndarray, float | None]:
    band = dataset.GetRasterBand(1)
    raw = band.ReadRaster(
        0,
        0,
        dataset.RasterXSize,
        dataset.RasterYSize,
        buf_xsize=dataset.RasterXSize,
        buf_ysize=dataset.RasterYSize,
        buf_type=gdal.GDT_Float32,
    )
    if raw is None:
        raise RuntimeError("Could not read raster band")
    array = np.frombuffer(raw, dtype=np.float32).reshape(dataset.RasterYSize, dataset.RasterXSize).copy()
    nodata = band.GetNoDataValue()
    return array, nodata


def _write_array(band: gdal.Band, array: np.ndarray, *, dtype: int = gdal.GDT_Float32) -> None:
    if dtype == gdal.GDT_Byte:
        output = array.astype("uint8")
    else:
        output = array.astype("float32")
    band.WriteRaster(
        0,
        0,
        output.shape[1],
        output.shape[0],
        output.tobytes(),
        buf_xsize=output.shape[1],
        buf_ysize=output.shape[0],
        buf_type=dtype,
    )


def _valid_mask(array: np.ndarray, nodata: float | None) -> np.ndarray:
    mask = np.isfinite(array)
    if nodata is not None:
        mask &= array != nodata
    return mask


def _driver_create_like(
    path: str | Path,
    template: gdal.Dataset,
    *,
    bands: int,
    dtype: int = gdal.GDT_Float32,
) -> gdal.Dataset:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(
        str(path),
        template.RasterXSize,
        template.RasterYSize,
        bands,
        dtype,
        options=["COMPRESS=LZW", "TILED=YES"],
    )
    if dataset is None:
        raise RuntimeError(f"Could not create raster: {path}")
    dataset.SetGeoTransform(template.GetGeoTransform())
    dataset.SetProjection(template.GetProjection())
    return dataset


def clip_raster_to_cutline(
    input_path: str | Path,
    cutline_path: str | Path,
    output_path: str | Path,
    *,
    nodata: float = RASTER_NODATA,
) -> Path:
    """Clip a raster to a vector cutline and return the clipped GeoTIFF path."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = gdal.Warp(
        str(output_path),
        str(input_path),
        cutlineDSName=str(cutline_path),
        cropToCutline=True,
        dstNodata=nodata,
        multithread=True,
        format="GTiff",
        creationOptions=["COMPRESS=LZW", "TILED=YES"],
    )
    if result is None:
        raise RuntimeError(f"Could not clip raster {input_path} to {cutline_path}")
    result.FlushCache()
    result = None
    return output_path


def align_raster_to_template(
    input_path: str | Path,
    template_path: str | Path,
    output_path: str | Path,
    *,
    nodata: float = RASTER_NODATA,
) -> Path:
    """Resample an input raster to the grid of a template raster."""

    template = _open_dataset(template_path)
    transform = template.GetGeoTransform()
    xmin = transform[0]
    ymax = transform[3]
    xmax = xmin + transform[1] * template.RasterXSize
    ymin = ymax + transform[5] * template.RasterYSize
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = gdal.Warp(
        str(output_path),
        str(input_path),
        format="GTiff",
        outputBounds=(xmin, ymin, xmax, ymax),
        width=template.RasterXSize,
        height=template.RasterYSize,
        dstSRS=template.GetProjection(),
        srcNodata=nodata,
        dstNodata=nodata,
        resampleAlg="near",
        creationOptions=["COMPRESS=LZW", "TILED=YES"],
    )
    if result is None:
        raise RuntimeError(f"Could not align raster {input_path} to {template_path}")
    result.FlushCache()
    result = None
    return output_path


def _read_score_raster(
    path: str | Path | None,
    template: gdal.Dataset,
    *,
    default_score: float,
    temp_dir: Path,
    name: str,
) -> tuple[np.ndarray, np.ndarray]:
    if path is None:
        array = np.full((template.RasterYSize, template.RasterXSize), default_score, dtype="float32")
        return array, np.ones_like(array, dtype=bool)

    aligned_path = temp_dir / f"{name}_aligned.tif"
    align_raster_to_template(path, temp_dir / "cdi_clipped.tif", aligned_path)
    dataset = _open_dataset(aligned_path)
    array, nodata = _band_array(dataset)
    return array, _valid_mask(array, nodata)


def _normalize_cdi(array: np.ndarray, *, cdi_code_scheme: str) -> np.ndarray:
    if cdi_code_scheme == "score":
        return array.copy()
    if cdi_code_scheme == "one-based":
        return array - 1
    if cdi_code_scheme == "acmad":
        scores = np.full(array.shape, RASTER_NODATA, dtype="float32")
        scores[array == 0] = 0
        scores[(array >= 1) & (array <= 3)] = 1
        scores[(array >= 4) & (array <= 6)] = 2
        scores[(array >= 7) & (array <= 10)] = 3
        scores[(array >= 11) & (array <= 12)] = 1
        scores[(array >= 13) & (array <= 14)] = 0
        return scores
    raise ValueError(f"Unsupported CDI code scheme: {cdi_code_scheme}")


def _classify_risk_array(risk_score: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    risk_class = np.full(risk_score.shape, CLASS_NODATA, dtype="uint8")
    risk_class[valid_mask & (risk_score < 1.0)] = 1
    risk_class[valid_mask & (risk_score >= 1.0) & (risk_score < 1.7)] = 2
    risk_class[valid_mask & (risk_score >= 1.7) & (risk_score < 2.4)] = 3
    risk_class[valid_mask & (risk_score >= 2.4)] = 4
    return risk_class


def validate_score_range(name: str, array: np.ndarray, valid_mask: np.ndarray) -> None:
    if not np.any(valid_mask):
        raise RuntimeError(f"{name} has no valid pixels")
    values = array[valid_mask]
    minimum = float(np.nanmin(values))
    maximum = float(np.nanmax(values))
    if minimum < 0 or maximum > 3:
        raise RuntimeError(f"{name} must be on a 0-3 score scale; found range {minimum} to {maximum}")


def build_agropastoral_risk_rasters(
    *,
    cdi_raster: str | Path,
    boundary_geojson: str | Path,
    output_dir: str | Path,
    cultivated_raster: str | Path | None = None,
    rangeland_raster: str | Path | None = None,
    water_points_raster: str | Path | None = None,
    exposure_defaults: ExposureDefaults = ExposureDefaults(),
    cdi_code_scheme: str = "score",
) -> dict[str, Path]:
    """Create clipped CDI, exposure, risk score, risk class, and stack rasters."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clipped_cdi_path = output_dir / "cdi_niger.tif"
    clip_raster_to_cutline(cdi_raster, boundary_geojson, clipped_cdi_path)

    cdi_dataset = _open_dataset(clipped_cdi_path)
    cdi_raw, cdi_nodata = _band_array(cdi_dataset)
    cdi = _normalize_cdi(cdi_raw, cdi_code_scheme=cdi_code_scheme)
    valid = _valid_mask(cdi_raw, cdi_nodata)
    valid &= cdi != RASTER_NODATA
    validate_score_range("CDI", cdi, valid)

    cultivated, cultivated_valid = _read_score_raster(
        cultivated_raster,
        cdi_dataset,
        default_score=exposure_defaults.cultivated,
        temp_dir=output_dir,
        name="cultivated_exposure",
    )
    rangeland, rangeland_valid = _read_score_raster(
        rangeland_raster,
        cdi_dataset,
        default_score=exposure_defaults.rangeland,
        temp_dir=output_dir,
        name="rangeland_exposure",
    )
    water_points, water_valid = _read_score_raster(
        water_points_raster,
        cdi_dataset,
        default_score=exposure_defaults.water_points,
        temp_dir=output_dir,
        name="water_point_exposure",
    )

    valid &= cultivated_valid & rangeland_valid & water_valid
    validate_score_range("cultivated exposure", cultivated, valid)
    validate_score_range("rangeland exposure", rangeland, valid)
    validate_score_range("water-point exposure", water_points, valid)

    exposure = (0.45 * cultivated) + (0.35 * rangeland) + (0.20 * water_points)
    risk_score = (0.60 * cdi) + (0.40 * exposure)
    risk_class = _classify_risk_array(risk_score, valid)

    for array in (cdi, cultivated, rangeland, water_points, exposure, risk_score):
        array[~valid] = RASTER_NODATA

    risk_score_path = output_dir / "agropastoral_risk_score.tif"
    risk_score_ds = _driver_create_like(risk_score_path, cdi_dataset, bands=1)
    risk_score_ds.GetRasterBand(1).SetDescription("risk_score")
    risk_score_ds.GetRasterBand(1).SetNoDataValue(RASTER_NODATA)
    _write_array(risk_score_ds.GetRasterBand(1), risk_score, dtype=gdal.GDT_Float32)
    risk_score_ds.FlushCache()
    risk_score_ds = None

    risk_class_path = output_dir / "agropastoral_risk_class.tif"
    risk_class_ds = _driver_create_like(risk_class_path, cdi_dataset, bands=1, dtype=gdal.GDT_Byte)
    band = risk_class_ds.GetRasterBand(1)
    band.SetDescription("risk_class")
    band.SetNoDataValue(CLASS_NODATA)
    _write_array(band, risk_class, dtype=gdal.GDT_Byte)
    risk_class_ds.FlushCache()
    risk_class_ds = None

    stack_path = output_dir / "agropastoral_risk_stack.tif"
    stack_ds = _driver_create_like(stack_path, cdi_dataset, bands=4)
    stack_arrays: Iterable[tuple[str, np.ndarray]] = (
        ("hazard_score", cdi),
        ("exposure_score", exposure),
        ("risk_score", risk_score),
        ("risk_class", risk_class.astype("float32")),
    )
    for index, (name, array) in enumerate(stack_arrays, start=1):
        band = stack_ds.GetRasterBand(index)
        band.SetDescription(name)
        band.SetNoDataValue(RASTER_NODATA)
        _write_array(band, array, dtype=gdal.GDT_Float32)
    stack_ds.FlushCache()
    stack_ds = None

    return {
        "cdi": clipped_cdi_path,
        "risk_score": risk_score_path,
        "risk_class": risk_class_path,
        "risk_stack": stack_path,
    }


def risk_class_labels() -> dict[int, str]:
    return {
        1: classify_risk(0.5),
        2: classify_risk(1.2),
        3: classify_risk(2.0),
        4: classify_risk(2.6),
    }
