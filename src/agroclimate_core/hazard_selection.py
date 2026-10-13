"""Decide which hazard data a run uses, before anything is downloaded.

The decision is separate from the download so a caller (the command line, the
QGIS plugin) can show the user which period will be used, and so tests can run
without a network.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

from .acmad_availability import combined_product_seasons, latest_dekad_range
from .periods import SeasonPeriod, resolve_dekad, resolve_season

if TYPE_CHECKING:  # imported for type checking only, to avoid a circular import
    from .workflow import RunConfig, WorkflowServices

logger = logging.getLogger(__name__)


class ConfigError(ValueError):
    """The requested run cannot be understood (missing date, unknown hazard, ...)."""


@dataclass
class HazardSelection:
    """Which hazard data a run uses, decided before anything is downloaded."""

    name: str  # key of the clipped hazard in the outputs: "cdi" or "combined_hazard"
    label: str  # period actually used; goes into the default output folder name
    code_scheme: str
    metadata: Dict[str, Any]
    fallback: bool
    fetch: Callable[[Path], Path]  # downloads into the output folder, returns the raster path


def dekad_from_day(day: int) -> int:
    if day <= 10:
        return 1
    if day <= 20:
        return 11
    return 21


def resolve_requested_period(config: "RunConfig") -> Tuple[int, int, int, str, date]:
    """Year, month, dekad, label and requested date for a CDI run."""

    if config.analysis_date is not None:
        requested = config.analysis_date
        return requested.year, requested.month, dekad_from_day(requested.day), requested.isoformat(), requested
    if config.year is None or config.month is None:
        raise ConfigError("Give an analysis date, or both a year and a month.")
    dekad = config.dekad or 1
    try:
        requested = date(config.year, config.month, dekad)
    except ValueError as exc:
        raise ConfigError(f"Not a valid period: {config.year}-{config.month}-{dekad} ({exc})") from exc
    return config.year, config.month, dekad, f"{config.year}-{config.month:02d}-{dekad:02d}", requested


def select_cdi_hazard(config: "RunConfig", services: "WorkflowServices") -> HazardSelection:
    """Choose the CDI dekad from what ACMAD has actually published.

    Publication lags behind the calendar, so "today" usually has no CDI yet. An
    explicit year and month is an exact request and is never silently replaced.
    """

    year, month, dekad, label, requested = resolve_requested_period(config)
    code_scheme = config.cdi_code_scheme

    if config.cdi_raster is not None:
        local = config.cdi_raster
        return HazardSelection(
            name="cdi",
            label=label,
            code_scheme=code_scheme,
            metadata={"source": "local file", "requested_date": requested, "code_scheme": code_scheme},
            fallback=False,
            fetch=lambda _output_dir: local,
        )

    availability = services.fetch_availability(config.acmad_api_base_url)
    earliest, latest = latest_dekad_range(availability, config.cdi_product)
    resolved = resolve_dekad(
        requested,
        latest,
        earliest,
        max_fallback_dekads=config.max_fallback_dekads,
        strict=config.strict_dates or config.analysis_date is None,
    )
    if resolved.fallback:
        logger.warning(
            "CDI for %s is not published yet; using %s (%d dekads older).",
            resolved.requested.label,
            resolved.period.label,
            resolved.lag_dekads,
        )
    period = resolved.period

    def fetch(output_dir: Path) -> Path:
        return services.download_cdi(
            data_name=config.cdi_product,
            year=period.year,
            month=period.month,
            dekad=period.dekad,
            output_path=output_dir / f"acmad_{config.cdi_product}_{period.year}_{period.month:02d}_{period.dekad:02d}.tif",
            base_url=config.acmad_api_base_url,
            # With mask_nodata=true ACMAD turns CDI code 0 ("no drought") into nodata, which would
            # drop every unaffected area from the risk map instead of scoring it low.
            mask_nodata=False,
        )

    return HazardSelection(
        name="cdi",
        label=period.label,
        code_scheme=code_scheme,
        fallback=resolved.fallback,
        metadata={
            "source": f"ACMAD {config.cdi_product}",
            "requested_date": requested,
            "period_used": period,
            "period_requested": resolved.requested,
            "fallback": resolved.fallback,
            "lag_dekads": resolved.lag_dekads,
            "mask_nodata": False,
            "code_scheme": code_scheme,
        },
        fetch=fetch,
    )


def select_combined_hazard(config: "RunConfig", services: "WorkflowServices") -> HazardSelection:
    """Choose the seasonal combined hazard from the periods ACMAD lists for it.

    An explicit forecast period skips the catalogue, and the download itself
    then confirms whether ACMAD has it.
    """

    fallback = False
    season: SeasonPeriod
    requested: Optional[date]
    if config.forecast_period is not None:
        if config.forecast_year is None:
            raise ConfigError("A forecast period needs a forecast year.")
        try:
            season = SeasonPeriod(config.forecast_year, config.forecast_period.upper())
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        requested = season.start
    else:
        if config.analysis_date is None:
            raise ConfigError("The combined hazard needs an analysis date, or a forecast period and year.")
        requested = config.analysis_date
        catalog = services.fetch_catalog(config.acmad_api_base_url)
        try:
            published = combined_product_seasons(catalog, config.combined_product)
        except KeyError as exc:
            raise ConfigError(str(exc.args[0])) from exc
        resolved = resolve_season(requested, published, strict=config.strict_dates)
        season, fallback = resolved.period, resolved.fallback
        if fallback:
            logger.warning("No published season covers %s; using %s.", requested.isoformat(), season.text)

    local = config.combined_hazard_raster

    def fetch(output_dir: Path) -> Path:
        if local is not None:
            return local
        return services.download_combined(
            data_name=config.combined_product,
            forecast_period=season.label,
            year=season.year,
            output_path=output_dir / f"acmad_{config.combined_product}_{season.year}_{season.label}.tif",
            base_url=config.acmad_api_base_url,
        )

    return HazardSelection(
        name="combined_hazard",
        label=f"combined-{season.year}-{season.label}",
        code_scheme="combined-hazard",
        fallback=fallback,
        metadata={
            "source": "local file" if local else f"ACMAD {config.combined_product}",
            "requested_date": requested,
            "season_used": season.text,
            "fallback": fallback,
            "resolution_note": "1 degree grid; each cell is repeated on the exposure grid, not interpolated",
            "code_scheme": "combined-hazard",
        },
        fetch=fetch,
    )


def select_hazard(config: "RunConfig", services: "WorkflowServices") -> HazardSelection:
    if config.hazard == "cdi":
        return select_cdi_hazard(config, services)
    if config.hazard == "combined":
        return select_combined_hazard(config, services)
    raise ConfigError(f"Unknown hazard {config.hazard!r}; expected 'cdi' or 'combined'.")
