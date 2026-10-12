"""Time periods used by ACMAD products and how a requested date maps onto them.

ACMAD publishes dekadal monitoring products (CDI, anomalies) and seasonal
products (long-range forecast, combined hazard). Publication lags behind the
calendar, so a run for "today" usually has no data yet. The functions here
decide, from a requested date and what is published, which period to use, and
return enough information for the caller to say so on the map and in metadata.

Pure date logic only: no network, no GDAL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

DEKAD_STARTS = (1, 11, 21)

# Season label -> start month. Labels name the three months covered; the year of
# a SeasonPeriod is the year of the start month (DJF 2025 = Dec 2025 - Feb 2026).
SEASON_START_MONTH = {
    "JFM": 1, "FMA": 2, "MAM": 3, "AMJ": 4, "MJJ": 5, "JJA": 6,
    "JAS": 7, "ASO": 8, "SON": 9, "OND": 10, "NDJ": 11, "DJF": 12,
}


class PeriodUnavailableError(RuntimeError):
    """Raised when no acceptable published period exists for a requested date."""


@dataclass(frozen=True, order=True)
class DekadPeriod:
    year: int
    month: int
    dekad: int  # 1, 11 or 21: the first day of the dekad, as in ACMAD file names

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"month must be 1-12; got {self.month}")
        if self.dekad not in DEKAD_STARTS:
            raise ValueError(f"dekad must be one of {DEKAD_STARTS}; got {self.dekad}")

    @classmethod
    def from_date(cls, value: date) -> "DekadPeriod":
        dekad = 1 if value.day <= 10 else 11 if value.day <= 20 else 21
        return cls(value.year, value.month, dekad)

    @property
    def label(self) -> str:
        return f"{self.year}-{self.month:02d}-{self.dekad:02d}"

    @property
    def ordinal(self) -> int:
        """Consecutive dekad number, so the gap between two periods is a subtraction."""

        return self.year * 36 + (self.month - 1) * 3 + DEKAD_STARTS.index(self.dekad)

    def previous(self) -> "DekadPeriod":
        index = DEKAD_STARTS.index(self.dekad)
        if index > 0:
            return DekadPeriod(self.year, self.month, DEKAD_STARTS[index - 1])
        if self.month > 1:
            return DekadPeriod(self.year, self.month - 1, 21)
        return DekadPeriod(self.year - 1, 12, 21)


@dataclass(frozen=True, order=True)
class SeasonPeriod:
    year: int  # year of the start month
    label: str

    def __post_init__(self) -> None:
        if self.label not in SEASON_START_MONTH:
            raise ValueError(f"Unknown season label {self.label!r}; expected one of {sorted(SEASON_START_MONTH)}")

    @property
    def start(self) -> date:
        return date(self.year, SEASON_START_MONTH[self.label], 1)

    @property
    def end(self) -> date:
        """First day after the season."""

        month_index = self.start.month - 1 + 3
        return date(self.start.year + month_index // 12, month_index % 12 + 1, 1)

    def contains(self, value: date) -> bool:
        return self.start <= value < self.end

    @property
    def text(self) -> str:
        return f"{self.label} {self.year}"


@dataclass(frozen=True)
class ResolvedDekad:
    period: DekadPeriod
    requested: DekadPeriod
    fallback: bool
    lag_dekads: int


@dataclass(frozen=True)
class ResolvedSeason:
    period: SeasonPeriod
    requested: date
    fallback: bool


def resolve_dekad(
    requested: date,
    latest: DekadPeriod,
    earliest: DekadPeriod,
    *,
    max_fallback_dekads: int = 3,
    strict: bool = False,
) -> ResolvedDekad:
    """Pick the dekad to use for ``requested``.

    Everything between ``earliest`` and ``latest`` is treated as published; ACMAD
    reports those two markers, and the per-year month lists it also returns are a
    coarse cross product that wrongly omits the 21st-dekad files.
    """

    wanted = DekadPeriod.from_date(requested)
    if wanted < earliest:
        raise PeriodUnavailableError(f"{wanted.label} is before the start of the archive ({earliest.label})")
    if wanted <= latest:
        return ResolvedDekad(period=wanted, requested=wanted, fallback=False, lag_dekads=0)

    lag = wanted.ordinal - latest.ordinal
    if strict:
        raise PeriodUnavailableError(f"{wanted.label} is not published yet; the latest available is {latest.label}")
    if lag > max_fallback_dekads:
        raise PeriodUnavailableError(
            f"{wanted.label} is {lag} dekads after the latest available ({latest.label}); "
            f"the limit is {max_fallback_dekads}. Pass an earlier --analysis-date or raise the limit."
        )
    return ResolvedDekad(period=latest, requested=wanted, fallback=True, lag_dekads=lag)


def resolve_season(requested: date, published: Sequence[SeasonPeriod], *, strict: bool = False) -> ResolvedSeason:
    """Pick the published season covering ``requested``, preferring the latest-starting one."""

    if not published:
        raise PeriodUnavailableError("No seasonal products are published")

    containing = [season for season in published if season.contains(requested)]
    if containing:
        return ResolvedSeason(period=max(containing, key=lambda s: s.start), requested=requested, fallback=False)

    started = [season for season in published if season.start <= requested]
    if strict or not started:
        raise PeriodUnavailableError(f"No published season covers {requested.isoformat()}")
    return ResolvedSeason(period=max(started, key=lambda s: s.start), requested=requested, fallback=True)
