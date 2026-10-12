"""Exposure preparation: turn land cover into 0-3 exposure scores on the hazard grid.

Hazard products (CDI, combined hazard) are coarse (0.1 to 1 degree) while land
cover is ~10 m. Resampling land cover to the hazard grid with nearest-neighbour
or bilinear would be wrong for a categorical map, so this module counts, per
hazard cell, the share of source pixels that belong to a class group (for
example cropland) and then bins that share into the shared 0-3 score scale.

The module only needs GDAL and NumPy and knows nothing about QGIS.
"""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np
from osgeo import gdal, ogr

logger = logging.getLogger(__name__)

WORLDCOVER_BASE_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
WORLDCOVER_TILE_DEGREES = 3

# ESA WorldCover legend values we use. 0 is nodata in the product.
WORLDCOVER_SHRUBLAND = 20
WORLDCOVER_GRASSLAND = 30
WORLDCOVER_CROPLAND = 40

DEFAULT_CLASS_GROUPS: dict[str, tuple[int, ...]] = {
    "cultivated": (WORLDCOVER_CROPLAND,),
    # Pastoral use of shrub and grass is the working definition of rangeland for
    # the MVP; sparse vegetation (60) is excluded and should be reviewed with FAO.
    "rangeland": (WORLDCOVER_SHRUBLAND, WORLDCOVER_GRASSLAND),
}

_SNAP_TOLERANCE = 1e-6


@dataclass(frozen=True)
class ExposureThresholds:
    """Fraction-of-cell cut-offs for scores 1, 2 and 3 (below ``low`` scores 0).

    The defaults are placeholders so the pipeline runs; the real values are a
    product decision to be reviewed with FAO Niger.
    """

    low: float = 0.05
    moderate: float = 0.25
    high: float = 0.50

    def __post_init__(self) -> None:
        if not 0.0 <= self.low < self.moderate < self.high <= 1.0:
            raise ValueError(
                "Thresholds must satisfy 0 <= low < moderate < high <= 1; "
                f"got {self.low}, {self.moderate}, {self.high}"
            )


@dataclass(frozen=True)
class WorldCoverTile:
    name: str
    url: str
    bounds: tuple[float, float, float, float]  # xmin, ymin, xmax, ymax


def worldcover_tiles(bounds: tuple[float, float, float, float]) -> list[WorldCoverTile]:
    """Return the WorldCover tiles covering (xmin, ymin, xmax, ymax)."""

    xmin, ymin, xmax, ymax = bounds
    size = WORLDCOVER_TILE_DEGREES
    # The epsilon stops a bound sitting exactly on a tile edge from pulling in an
    # extra, empty neighbouring tile.
    lon_starts = range(math.floor(xmin / size) * size, math.floor((xmax - 1e-9) / size) * size + 1, size)
    lat_starts = range(math.floor(ymin / size) * size, math.floor((ymax - 1e-9) / size) * size + 1, size)

    tiles: list[WorldCoverTile] = []
    for lat in lat_starts:
        for lon in lon_starts:
            name = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"
            url = f"/vsicurl/{WORLDCOVER_BASE_URL}/ESA_WorldCover_10m_2021_v200_{name}_Map.tif"
            tiles.append(WorldCoverTile(name, url, (lon, lat, lon + size, lat + size)))
    return tiles


def worldcover_tile_urls(bounds: tuple[float, float, float, float]) -> list[str]:
    """Return /vsicurl/ URLs of the WorldCover tiles covering (xmin, ymin, xmax, ymax)."""

    return [tile.url for tile in worldcover_tiles(bounds)]


def fraction_to_score(fractions: np.ndarray, thresholds: ExposureThresholds, *, nodata: float) -> np.ndarray:
    """Bin class fractions (0-1, NaN = no data) into 0-3 exposure scores."""

    scores = np.zeros(fractions.shape, dtype="float32")
    scores[fractions >= thresholds.low] = 1
    scores[fractions >= thresholds.moderate] = 2
    scores[fractions >= thresholds.high] = 3
    scores[~np.isfinite(fractions)] = nodata
    return scores


def _snap(value: float, name: str) -> int:
    """Return ``value`` as an int, refusing values that are not whole numbers.

    A source grid that is not an exact multiple of the template grid would put
    source pixels in two cells at once, and silently approximating that would
    bias the fractions.
    """

    rounded = round(value)
    if abs(value - rounded) > _SNAP_TOLERANCE * max(1.0, abs(value)):
        raise ValueError(f"Source raster is not aligned to the template grid ({name} = {value})")
    return int(rounded)


def aggregate_class_fractions(
    source_paths: Sequence[str | Path],
    template_path: str | Path,
    class_groups: Mapping[str, Sequence[int]],
    cell_mask: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Share of valid source pixels in each class group, per template cell.

    ``cell_mask`` (True = needed) lets callers skip cells outside the area of
    interest, which for a country is roughly 40% of its bounding box. Skipped
    cells come back as NaN.

    Source pixels equal to the source nodata value are excluded from the
    denominator. Cells no source raster covers (or covers only with nodata) are
    NaN. Sources may be tiles; each template cell must lie entirely in one tile.
    """

    template = gdal.Open(str(template_path))
    if template is None:
        raise RuntimeError(f"Could not open template raster: {template_path}")
    t_gt = template.GetGeoTransform()
    t_cols, t_rows = template.RasterXSize, template.RasterYSize
    cell_x, cell_y = t_gt[1], -t_gt[5]
    if cell_mask is not None and cell_mask.shape != (t_rows, t_cols):
        raise ValueError(f"cell_mask shape {cell_mask.shape} does not match the template {(t_rows, t_cols)}")

    group_counts = {name: np.zeros((t_rows, t_cols), dtype="float64") for name in class_groups}
    valid_counts = np.zeros((t_rows, t_cols), dtype="float64")

    for source_path in source_paths:
        source = gdal.Open(str(source_path))
        if source is None:
            raise RuntimeError(f"Could not open source raster: {source_path}")
        s_gt = source.GetGeoTransform()
        pixel_x, pixel_y = s_gt[1], -s_gt[5]
        per_cell_x = _snap(cell_x / pixel_x, "pixels per cell (x)")
        per_cell_y = _snap(cell_y / pixel_y, "pixels per cell (y)")
        # Whole-cell offset between grids; also proves the origins line up.
        _snap((s_gt[0] - t_gt[0]) / cell_x, "x origin offset in cells")
        _snap((t_gt[3] - s_gt[3]) / cell_y, "y origin offset in cells")

        s_xmax = s_gt[0] + pixel_x * source.RasterXSize
        s_ymin = s_gt[3] - pixel_y * source.RasterYSize
        first_col = max(0, math.ceil((s_gt[0] - t_gt[0]) / cell_x - _SNAP_TOLERANCE))
        last_col = min(t_cols, math.floor((s_xmax - t_gt[0]) / cell_x + _SNAP_TOLERANCE))
        first_row = max(0, math.ceil((t_gt[3] - s_gt[3]) / cell_y - _SNAP_TOLERANCE))
        last_row = min(t_rows, math.floor((t_gt[3] - s_ymin) / cell_y + _SNAP_TOLERANCE))
        if first_col >= last_col or first_row >= last_row:
            logger.info("Source %s does not overlap the template grid; skipping", source_path)
            continue

        band = source.GetRasterBand(1)
        if band.DataType != gdal.GDT_Byte:
            raise ValueError(f"Class raster must be 8-bit (like ESA WorldCover); {source_path} is not")
        nodata = band.GetNoDataValue()
        logger.info(
            "Aggregating %s into %d x %d template cells", source_path, last_row - first_row, last_col - first_col
        )

        for row in range(first_row, last_row):
            row_first, row_last = first_col, last_col
            if cell_mask is not None:
                needed = np.flatnonzero(cell_mask[row, first_col:last_col])
                if needed.size == 0:
                    continue
                # Read only the span of needed cells in this row; the gap cells between
                # them are cheap and are blanked at the end.
                row_first, row_last = first_col + int(needed[0]), first_col + int(needed[-1]) + 1
            n_cols = row_last - row_first
            x_off = _snap((t_gt[0] + row_first * cell_x - s_gt[0]) / pixel_x, "x window offset")
            y_off = _snap((s_gt[3] - (t_gt[3] - row * cell_y)) / pixel_y, "y window offset")
            width = n_cols * per_cell_x
            # ReadRaster + frombuffer rather than ReadAsArray: it works in GDAL builds
            # without the gdal_array bindings, as the raster pipeline already does.
            raw = band.ReadRaster(x_off, y_off, width, per_cell_y, buf_type=gdal.GDT_Byte)
            if raw is None:
                raise RuntimeError(f"Could not read {source_path} rows {y_off}..{y_off + per_cell_y}")
            block = np.frombuffer(raw, dtype=np.uint8).reshape(per_cell_y, width)
            valid = np.ones(block.shape, dtype=bool) if nodata is None else block != nodata
            columns = slice(row_first, row_last)
            valid_counts[row, columns] += valid.reshape(per_cell_y, n_cols, per_cell_x).sum(axis=(0, 2))
            for name, codes in class_groups.items():
                member = np.isin(block, codes) & valid
                group_counts[name][row, columns] += member.reshape(per_cell_y, n_cols, per_cell_x).sum(axis=(0, 2))

    has_data = valid_counts > 0
    if cell_mask is not None:
        has_data &= cell_mask
    with np.errstate(invalid="ignore", divide="ignore"):
        return {
            name: np.where(has_data, counts / valid_counts, np.nan).astype("float32")
            for name, counts in group_counts.items()
        }


def cells_touching_boundary(boundary_path: str | Path, template_path: str | Path) -> np.ndarray:
    """Boolean grid (template shape) of cells the boundary polygon touches.

    ``ALL_TOUCHED`` keeps cells that only clip the border: a border cell with
    10% inside the country still needs exposure scores.
    """

    template = gdal.Open(str(template_path))
    if template is None:
        raise RuntimeError(f"Could not open template raster: {template_path}")
    vector = ogr.Open(str(boundary_path))
    if vector is None:
        raise RuntimeError(f"Could not open boundary: {boundary_path}")

    mask_ds = gdal.GetDriverByName("MEM").Create("", template.RasterXSize, template.RasterYSize, 1, gdal.GDT_Byte)
    mask_ds.SetGeoTransform(template.GetGeoTransform())
    mask_ds.SetProjection(template.GetProjection())
    gdal.RasterizeLayer(mask_ds, [1], vector.GetLayer(0), burn_values=[1], options=["ALL_TOUCHED=TRUE"])
    raw = mask_ds.GetRasterBand(1).ReadRaster(0, 0, template.RasterXSize, template.RasterYSize, buf_type=gdal.GDT_Byte)
    return np.frombuffer(raw, dtype=np.uint8).reshape(template.RasterYSize, template.RasterXSize).astype(bool)


def cache_raster_window(
    source: str | Path, destination: str | Path, bounds: tuple[float, float, float, float]
) -> Path:
    """Copy the (xmin, ymin, xmax, ymax) window of ``source`` to a local GeoTIFF, once.

    Writing to a ``.part`` file and renaming means an interrupted download never
    leaves a truncated file that a later run would mistake for a finished cache.
    """

    destination = Path(destination)
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    xmin, ymin, xmax, ymax = bounds
    result = gdal.Translate(
        str(partial),
        str(source),
        format="GTiff",
        projWin=[xmin, ymax, xmax, ymin],
        creationOptions=["COMPRESS=DEFLATE", "TILED=YES"],
    )
    if result is None:
        raise RuntimeError(f"Could not fetch window {bounds} from {source}")
    result.FlushCache()
    result = None
    partial.replace(destination)
    return destination


def fetch_worldcover_tiles(
    *,
    template_path: str | Path,
    cache_dir: str | Path,
    cell_mask: np.ndarray | None = None,
    workers: int = 4,
    fetch: Callable[[str, Path, tuple[float, float, float, float]], Path] = cache_raster_window,
) -> list[Path]:
    """Download (in parallel) only the WorldCover windows the masked cells need.

    Tiles with no needed cell are skipped, and each remaining tile is cut to the
    bounding box of its needed cells. Windows already in ``cache_dir`` are reused.
    """

    template = gdal.Open(str(template_path))
    if template is None:
        raise RuntimeError(f"Could not open template raster: {template_path}")
    gt = template.GetGeoTransform()
    cols, rows = template.RasterXSize, template.RasterYSize
    cell_x, cell_y = gt[1], -gt[5]
    bounds = (gt[0], gt[3] - cell_y * rows, gt[0] + cell_x * cols, gt[3])
    if cell_mask is None:
        cell_mask = np.ones((rows, cols), dtype=bool)

    jobs: list[tuple[str, Path, tuple[float, float, float, float]]] = []
    for tile in worldcover_tiles(bounds):
        # Template cell range inside this tile (tile edges lie on whole degrees, which
        # the 0.1 degree grid shares, so no cell straddles two tiles).
        col0 = max(0, math.ceil((tile.bounds[0] - gt[0]) / cell_x - _SNAP_TOLERANCE))
        col1 = min(cols, math.floor((tile.bounds[2] - gt[0]) / cell_x + _SNAP_TOLERANCE))
        row0 = max(0, math.ceil((gt[3] - tile.bounds[3]) / cell_y - _SNAP_TOLERANCE))
        row1 = min(rows, math.floor((gt[3] - tile.bounds[1]) / cell_y + _SNAP_TOLERANCE))
        if col0 >= col1 or row0 >= row1:
            continue
        needed_rows, needed_cols = np.nonzero(cell_mask[row0:row1, col0:col1])
        if needed_rows.size == 0:
            logger.info("Tile %s has no needed cells; skipping", tile.name)
            continue
        c_min, c_max = col0 + int(needed_cols.min()), col0 + int(needed_cols.max()) + 1
        r_min, r_max = row0 + int(needed_rows.min()), row0 + int(needed_rows.max()) + 1
        window = (
            gt[0] + c_min * cell_x,
            gt[3] - r_max * cell_y,
            gt[0] + c_max * cell_x,
            gt[3] - r_min * cell_y,
        )
        stamp = "_".join(f"{value:.3f}" for value in window)
        jobs.append((tile.url, Path(cache_dir) / f"worldcover_2021_{tile.name}_{stamp}.tif", window))

    logger.info("Fetching %d WorldCover windows with %d workers", len(jobs), workers)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        # list() so an exception in any worker is raised here rather than lost.
        return list(pool.map(lambda job: fetch(job[0], job[1], job[2]), jobs))


def _write_float_raster(path: Path, template: gdal.Dataset, array: np.ndarray, *, description: str, nodata: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path),
        template.RasterXSize,
        template.RasterYSize,
        1,
        gdal.GDT_Float32,
        options=["COMPRESS=LZW", "TILED=YES"],
    )
    if dataset is None:
        raise RuntimeError(f"Could not create raster: {path}")
    dataset.SetGeoTransform(template.GetGeoTransform())
    dataset.SetProjection(template.GetProjection())
    band = dataset.GetRasterBand(1)
    band.SetDescription(description)
    band.SetNoDataValue(nodata)
    data = np.where(np.isfinite(array), array, nodata).astype("float32")
    band.WriteRaster(0, 0, data.shape[1], data.shape[0], data.tobytes(), buf_type=gdal.GDT_Float32)
    dataset.FlushCache()


def prepare_exposure_rasters(
    *,
    template_path: str | Path,
    output_dir: str | Path,
    source_paths: Sequence[str | Path] | None = None,
    class_groups: Mapping[str, Sequence[int]] = DEFAULT_CLASS_GROUPS,
    thresholds: Mapping[str, ExposureThresholds] | None = None,
    boundary_geojson: str | Path | None = None,
    cache_dir: str | Path | None = None,
    workers: int = 4,
    nodata: float = -9999.0,
) -> dict[str, Path]:
    """Write ``<group>_fraction.tif`` and ``<group>_exposure.tif`` for each class group.

    The fraction rasters are kept next to the scores so reviewers can see the
    raw share that produced each score and re-bin it with other thresholds
    without re-reading the land cover. ``source_paths`` defaults to the
    WorldCover tiles covering the template.

    With ``boundary_geojson`` only cells touching the boundary are computed and
    downloaded. With ``cache_dir`` the needed land cover windows are saved there
    (in parallel) and re-used by later runs; without it they are streamed.
    """

    template = gdal.Open(str(template_path))
    if template is None:
        raise RuntimeError(f"Could not open template raster: {template_path}")

    cell_mask = cells_touching_boundary(boundary_geojson, template_path) if boundary_geojson else None

    if source_paths is None:
        if cache_dir is not None:
            source_paths = fetch_worldcover_tiles(
                template_path=template_path, cache_dir=cache_dir, cell_mask=cell_mask, workers=workers
            )
        else:
            gt = template.GetGeoTransform()
            bounds = (
                gt[0],
                gt[3] + gt[5] * template.RasterYSize,
                gt[0] + gt[1] * template.RasterXSize,
                gt[3],
            )
            source_paths = worldcover_tile_urls(bounds)

    fractions = aggregate_class_fractions(source_paths, template_path, class_groups, cell_mask=cell_mask)
    output_dir = Path(output_dir)
    outputs: dict[str, Path] = {}
    for name, fraction in fractions.items():
        group_thresholds = (thresholds or {}).get(name, ExposureThresholds())
        fraction_path = output_dir / f"{name}_fraction.tif"
        score_path = output_dir / f"{name}_exposure.tif"
        _write_float_raster(fraction_path, template, fraction, description=f"{name}_fraction", nodata=nodata)
        scores = fraction_to_score(fraction, group_thresholds, nodata=nodata)
        _write_float_raster(score_path, template, scores, description=f"{name}_exposure_score", nodata=nodata)
        outputs[f"{name}_fraction"] = fraction_path
        outputs[f"{name}_exposure"] = score_path
    return outputs
