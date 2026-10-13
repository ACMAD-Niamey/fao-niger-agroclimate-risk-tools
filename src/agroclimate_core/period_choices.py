"""The periods a user can pick from: what ACMAD has actually published.

A drop-down of published periods (latest first) replaces guessing a date and
being told afterwards that it was not available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .acmad_availability import combined_product_seasons, latest_dekad_range
from .periods import DekadPeriod, SeasonPeriod
from .workflow import DEFAULT_COMBINED_PRODUCT, WorkflowServices, default_services

logger = logging.getLogger(__name__)

DEFAULT_MAX_DEKADS = 36  # about a year of ten-day periods


@dataclass(frozen=True)
class PeriodChoices:
    dekads: Tuple[DekadPeriod, ...] = ()  # newest first
    seasons: Tuple[SeasonPeriod, ...] = ()  # newest first
    problems: Tuple[str, ...] = field(default_factory=tuple)  # plain-language, for the user

    @property
    def latest_dekad(self) -> Optional[DekadPeriod]:
        return self.dekads[0] if self.dekads else None

    @property
    def latest_season(self) -> Optional[SeasonPeriod]:
        return self.seasons[0] if self.seasons else None


def load_period_choices(
    services: Optional[WorkflowServices] = None,
    *,
    api_base_url: str,
    cdi_product: str = "cdi",
    combined_product: str = DEFAULT_COMBINED_PRODUCT,
    max_dekads: int = DEFAULT_MAX_DEKADS,
) -> PeriodChoices:
    """Ask ACMAD what is published. Never raises: failures become ``problems``.

    A caller can then still offer a free date box, so being offline does not
    block the user.
    """

    services = services or default_services()
    problems: List[str] = []

    dekads: List[DekadPeriod] = []
    try:
        earliest, latest = latest_dekad_range(services.fetch_availability(api_base_url), cdi_product)
        period = latest
        while period >= earliest and len(dekads) < max_dekads:
            dekads.append(period)
            period = period.previous()
    except Exception as exc:  # network, format or missing product: all end the same way for the user
        logger.warning("Could not list CDI periods: %s", exc)
        problems.append("Could not read the available CDI periods from ACMAD.")

    seasons: List[SeasonPeriod] = []
    try:
        published = combined_product_seasons(services.fetch_catalog(api_base_url), combined_product)
        seasons = sorted(published, key=lambda season: season.start, reverse=True)
        if not seasons:
            problems.append("ACMAD lists no published seasonal outlook right now.")
    except Exception as exc:
        logger.warning("Could not list seasonal periods: %s", exc)
        problems.append("Could not read the available seasonal outlooks from ACMAD.")

    return PeriodChoices(dekads=tuple(dekads), seasons=tuple(seasons), problems=tuple(problems))
