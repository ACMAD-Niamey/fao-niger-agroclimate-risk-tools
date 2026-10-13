"""The end-to-end risk workflow, callable from the command line or from QGIS.

``run_risk_workflow`` is the one place that knows the order of the steps: pick
the period ACMAD has published, fetch the boundary and hazard, build the risk
rasters, write the metadata. The command-line script and the QGIS plugin are
thin shells around it, so they cannot drift apart.

Nothing here imports QGIS. Network access goes through ``WorkflowServices`` so
tests (and offline use) can substitute their own.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

from .acmad_availability import fetch_available_datasets, fetch_dataset_catalog
from .acmad_boundaries import build_wfs_getfeature_url, niger_boundary_request
from .acmad_download import DEFAULT_ACMAD_API_BASE_URL, download_acmad_raster, download_combined_product
from .cancellation import WorkflowCancelled
from .hazard_selection import ConfigError, HazardSelection, select_hazard
from .raster_pipeline import ExposureDefaults, build_agropastoral_risk_rasters
from .run_metadata import write_run_metadata

logger = logging.getLogger(__name__)

DEFAULT_GEOSERVER_URL = "https://ada.acmad.org/geoserver"
DEFAULT_COMBINED_PRODUCT = "combined_drought_hazard_era5"

ProgressCallback = Callable[[float, str], None]
CancelCheck = Callable[[], bool]

__all__ = [
    "ConfigError",
    "RunConfig",
    "RunResult",
    "WorkflowCancelled",
    "WorkflowServices",
    "default_services",
    "run_risk_workflow",
]


@dataclass(frozen=True)
class RunConfig:
    """Everything a run needs. Defaults match the command-line defaults."""

    output_dir: Optional[Path] = None  # default: <output_root>/niger-risk-<period used>
    output_root: Path = Path("outputs")

    # When to map. Either an analysis date, or an exact CDI period (year, month, dekad).
    analysis_date: Optional[date] = None
    year: Optional[int] = None
    month: Optional[int] = None
    dekad: Optional[int] = None

    # Which hazard.
    hazard: str = "cdi"  # "cdi" or "combined"
    cdi_product: str = "cdi"
    combined_product: str = DEFAULT_COMBINED_PRODUCT
    forecast_period: Optional[str] = None
    forecast_year: Optional[int] = None
    max_fallback_dekads: int = 3
    strict_dates: bool = False
    cdi_code_scheme: str = "acmad"

    # Local files that replace a download.
    cdi_raster: Optional[Path] = None
    combined_hazard_raster: Optional[Path] = None

    # Exposure.
    cultivated_raster: Optional[Path] = None
    rangeland_raster: Optional[Path] = None
    water_points_raster: Optional[Path] = None
    exposure_defaults: ExposureDefaults = field(default_factory=ExposureDefaults)
    mask_to_agropastoral: Optional[bool] = None  # None = on when exposure rasters are given
    grid_template: Optional[Path] = None

    acmad_api_base_url: str = DEFAULT_ACMAD_API_BASE_URL
    acmad_geoserver_url: str = DEFAULT_GEOSERVER_URL

    def validate(self) -> None:
        """Raise ConfigError with a plain message if the run cannot be understood."""

        if self.hazard not in ("cdi", "combined"):
            raise ConfigError(f"Unknown hazard {self.hazard!r}; expected 'cdi' or 'combined'.")
        if self.month is not None and not 1 <= self.month <= 12:
            raise ConfigError(f"Month must be 1 to 12; got {self.month}.")
        if self.dekad is not None and self.dekad not in (1, 11, 21):
            raise ConfigError(f"Dekad must be 1, 11 or 21; got {self.dekad}.")
        if self.max_fallback_dekads < 0:
            raise ConfigError("The fallback limit cannot be negative.")
        has_period = self.analysis_date is not None or (self.year is not None and self.month is not None)
        if self.hazard == "cdi" and not has_period:
            raise ConfigError("Give an analysis date, or both a year and a month.")
        if self.hazard == "combined" and self.analysis_date is None and self.forecast_period is None:
            raise ConfigError("The combined hazard needs an analysis date, or a forecast period and year.")
        if self.forecast_period is not None and self.forecast_year is None:
            raise ConfigError("A forecast period needs a forecast year.")


@dataclass
class WorkflowServices:
    """The network calls a run makes. Replace them in tests or for offline use."""

    fetch_availability: Callable[[str], Dict[str, Any]]
    fetch_catalog: Callable[[str], Dict[str, Any]]
    download_cdi: Callable[..., Path]
    download_combined: Callable[..., Path]
    download_boundary: Callable[[Path, str], Path]


def download_niger_boundary(output_path: Path, geoserver_url: str) -> Path:
    """Fetch the Niger admin level 0 boundary from ACMAD's GeoServer."""

    url = build_wfs_getfeature_url(niger_boundary_request(wfs_url=geoserver_url, admin_level=0))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("features"):
        raise RuntimeError(f"ACMAD boundary request returned no features: {url}")
    output_path.write_text(json.dumps(payload), encoding="utf-8")
    return output_path


def default_services() -> WorkflowServices:
    return WorkflowServices(
        fetch_availability=fetch_available_datasets,
        fetch_catalog=fetch_dataset_catalog,
        download_cdi=download_acmad_raster,
        download_combined=download_combined_product,
        download_boundary=download_niger_boundary,
    )


@dataclass
class RunResult:
    """What a finished run produced, for a caller to display."""

    output_dir: Path
    outputs: Dict[str, Path]
    metadata_path: Path
    hazard_name: str
    hazard_label: str
    hazard_path: Path
    fallback: bool
    mask_applied: bool
    boundary_path: Path
    warnings: List[str] = field(default_factory=list)


def _resolve_grid_template(config: RunConfig, warnings: List[str]) -> Optional[Path]:
    if config.grid_template is not None:
        return config.grid_template
    if config.hazard == "combined":
        for candidate in (config.cultivated_raster, config.rangeland_raster, config.water_points_raster):
            if candidate is not None:
                return candidate
        message = "No exposure raster was given, so the 1 degree combined hazard stays on its native coarse grid."
        logger.warning(message)
        warnings.append(message)
    return None


def run_risk_workflow(
    config: RunConfig,
    *,
    services: Optional[WorkflowServices] = None,
    progress: Optional[ProgressCallback] = None,
    is_cancelled: Optional[CancelCheck] = None,
) -> RunResult:
    """Run the whole workflow and return what it wrote.

    ``progress(percent, message)`` is called as steps start so a UI can show
    them; ``is_cancelled()`` is checked between steps so a long run can be
    stopped without leaving half-written results.
    """

    config.validate()
    services = services or default_services()
    warnings: List[str] = []

    def report(percent: float, message: str) -> None:
        logger.info("%3.0f%% %s", percent, message)
        if progress is not None:
            progress(percent, message)

    def checkpoint() -> None:
        if is_cancelled is not None and is_cancelled():
            raise WorkflowCancelled("The run was cancelled.")

    report(0, "Checking which ACMAD period is available")
    checkpoint()
    hazard: HazardSelection = select_hazard(config, services)
    if hazard.fallback:
        warnings.append(
            f"The requested period is not published yet; the map shows {hazard.label}, the latest available."
        )

    output_dir = config.output_dir or config.output_root / f"niger-risk-{hazard.label}"
    output_dir.mkdir(parents=True, exist_ok=True)

    report(10, "Fetching the Niger boundary")
    checkpoint()
    boundary_path = services.download_boundary(output_dir / "niger_boundary_admin0.geojson", config.acmad_geoserver_url)

    report(20, f"Fetching the hazard data ({hazard.label})")
    checkpoint()
    hazard_path = hazard.fetch(output_dir)

    report(40, "Building the risk rasters")
    checkpoint()
    has_exposure_rasters = any((config.cultivated_raster, config.rangeland_raster))
    # Masking needs real land cover: with the constant default scores every cell would pass anyway.
    mask_applied = has_exposure_rasters if config.mask_to_agropastoral is None else (
        config.mask_to_agropastoral and has_exposure_rasters
    )
    grid_template = _resolve_grid_template(config, warnings)
    outputs = build_agropastoral_risk_rasters(
        cdi_raster=hazard_path,
        boundary_geojson=boundary_path,
        output_dir=output_dir,
        cultivated_raster=config.cultivated_raster,
        rangeland_raster=config.rangeland_raster,
        water_points_raster=config.water_points_raster,
        exposure_defaults=config.exposure_defaults,
        cdi_code_scheme=hazard.code_scheme,
        grid_template=grid_template,
        hazard_name=hazard.name,
        mask_to_agropastoral=mask_applied,
    )

    report(90, "Writing run metadata")
    defaults = config.exposure_defaults
    metadata_path = write_run_metadata(
        output_dir,
        {
            "boundary": {
                # The risk run clips to Niger's country outline from ACMAD. Admin regions (for example OCHA
                # admin level 1) are only used later, for the optional region summary.
                "source": "ACMAD GeoServer, admin level 0 (Niger, country_code 181)",
                "geoserver_url": config.acmad_geoserver_url,
                "file": boundary_path,
            },
            "hazard": {"input": config.hazard, "file": hazard_path, "grid_template": grid_template, **hazard.metadata},
            "exposure": {
                "agropastoral_mask": mask_applied,
                "cultivated": config.cultivated_raster or f"default score {defaults.cultivated}",
                "rangeland": config.rangeland_raster or f"default score {defaults.rangeland}",
                "water_points": config.water_points_raster or f"default score {defaults.water_points}",
            },
            "outputs": outputs,
        },
    )
    report(100, "Done")
    return RunResult(
        output_dir=output_dir,
        outputs=outputs,
        metadata_path=metadata_path,
        hazard_name=hazard.name,
        hazard_label=hazard.label,
        hazard_path=hazard_path,
        fallback=hazard.fallback,
        mask_applied=mask_applied,
        boundary_path=boundary_path,
        warnings=warnings,
    )
