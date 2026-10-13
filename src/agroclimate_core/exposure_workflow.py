"""Prepare cropland and rangeland exposure for Niger from land cover.

Exposure is static, so this runs once (a few minutes, mostly downloading) and
its output is reused by every risk run. Like the risk workflow it has no QGIS
dependency and reports progress through a callback.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Sequence

from .cancellation import WorkflowCancelled
from .hazard_selection import ConfigError
from .exposure import ExposureThresholds, prepare_exposure_rasters
from .grid import make_grid_template
from .workflow import DEFAULT_GEOSERVER_URL, CancelCheck, ProgressCallback, WorkflowServices, default_services

logger = logging.getLogger(__name__)

CULTIVATED_SCORE_FILE = "cultivated_exposure.tif"
RANGELAND_SCORE_FILE = "rangeland_exposure.tif"


@dataclass(frozen=True)
class ExposureConfig:
    output_dir: Path = Path("outputs/exposure")
    # Where downloaded land cover windows are kept for next time. None streams without saving.
    cache_dir: Optional[Path] = Path("outputs/cache/worldcover")
    workers: int = 4
    cultivated_thresholds: ExposureThresholds = field(default_factory=ExposureThresholds)
    rangeland_thresholds: ExposureThresholds = field(default_factory=ExposureThresholds)
    boundary_geojson: Optional[Path] = None  # downloaded from ACMAD when not given
    geoserver_url: str = DEFAULT_GEOSERVER_URL
    landcover: Optional[Sequence[Path]] = None  # local land cover rasters instead of WorldCover
    # "worldcover" builds the rasters from ESA WorldCover (minutes, hundreds of MB);
    # "acmad" downloads the four small rasters ACMAD has already prepared (seconds).
    source: str = "worldcover"


def exposure_files_exist(directory: str | Path) -> bool:
    """True when both exposure score rasters a risk run needs are present."""

    directory = Path(directory)
    return (directory / CULTIVATED_SCORE_FILE).is_file() and (directory / RANGELAND_SCORE_FILE).is_file()


def run_exposure_preparation(
    config: ExposureConfig,
    *,
    services: Optional[WorkflowServices] = None,
    progress: Optional[ProgressCallback] = None,
    is_cancelled: Optional[CancelCheck] = None,
) -> Dict[str, Path]:
    """Get the exposure rasters, built from land cover or fetched from ACMAD, and return their paths."""

    if config.source not in ("worldcover", "acmad"):
        raise ConfigError(f"Unknown exposure source {config.source!r}; expected 'worldcover' or 'acmad'.")
    services = services or default_services()

    if config.source == "acmad":
        # No boundary, grid or land cover is needed: the prepared rasters are already on the right grid.
        logger.info("Getting ACMAD's prepared exposure into %s", config.output_dir)
        return services.download_exposure(config.output_dir, progress=progress, is_cancelled=is_cancelled)

    def report(percent: float, message: str) -> None:
        logger.info("%3.0f%% %s", percent, message)
        if progress is not None:
            progress(percent, message)

    def checkpoint() -> None:
        if is_cancelled is not None and is_cancelled():
            raise WorkflowCancelled("The exposure preparation was cancelled.")

    report(0, "Preparing the Niger grid")
    checkpoint()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    boundary = config.boundary_geojson
    if boundary is None:
        boundary = services.download_boundary(config.output_dir / "niger_boundary_admin0.geojson", config.geoserver_url)
    checkpoint()
    # A scratch template: the grid is cheap to rebuild and only the exposure rasters are kept.
    with tempfile.TemporaryDirectory(prefix="agroclimate_grid_") as scratch:
        template = make_grid_template(boundary, Path(scratch) / "grid.tif")

        def scaled(percent: float, message: str) -> None:
            report(5 + 0.95 * percent, message)

        outputs = prepare_exposure_rasters(
            template_path=template,
            output_dir=config.output_dir,
            source_paths=list(config.landcover) if config.landcover else None,
            thresholds={"cultivated": config.cultivated_thresholds, "rangeland": config.rangeland_thresholds},
            boundary_geojson=boundary,
            cache_dir=config.cache_dir,
            workers=config.workers,
            progress=scaled,
            is_cancelled=is_cancelled,
        )
    report(100, "Exposure rasters are ready")
    return outputs
