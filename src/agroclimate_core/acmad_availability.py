"""What ACMAD has published, from its ``get_available_datasets`` endpoint."""

from __future__ import annotations

from typing import Any, Mapping

import requests

from .acmad_download import DEFAULT_ACMAD_API_BASE_URL
from .periods import DekadPeriod, SeasonPeriod

AVAILABLE_DATASETS_PATH = "/api/data_api/rs_data/get_available_datasets/"
DATASET_CATALOG_PATH = "/api/data_api/rs_data/get_dataset_catalog/"


def fetch_available_datasets(
    base_url: str = DEFAULT_ACMAD_API_BASE_URL,
    *,
    timeout_seconds: float = 60.0,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fetch the catalogue of published products and their latest periods."""

    client = session or requests.Session()
    response = client.get(base_url.rstrip("/") + AVAILABLE_DATASETS_PATH, timeout=timeout_seconds)
    response.raise_for_status()
    return response.json()


def _product(availability: Mapping[str, Any], product: str) -> Mapping[str, Any]:
    entry = availability.get(product)
    if not isinstance(entry, Mapping) or "latest_year" not in entry:
        known = sorted(name for name, value in availability.items() if isinstance(value, Mapping) and "latest_year" in value)
        raise KeyError(f"ACMAD does not list a product named {product!r}; available: {', '.join(known)}")
    return entry


def latest_dekad_range(availability: Mapping[str, Any], product: str) -> tuple[DekadPeriod, DekadPeriod]:
    """Earliest and latest dekad published for a dekadal product (for example ``cdi``)."""

    entry = _product(availability, product)
    if "latest_dekad" not in entry:
        raise KeyError(f"{product!r} is not a dekadal product")
    latest = DekadPeriod(int(entry["latest_year"]), int(entry["latest_month"]), int(entry["latest_dekad"]))
    # Only the start year is reported, so the archive is assumed to begin in January.
    earliest = DekadPeriod(int(entry["start_year"]), 1, 1)
    return earliest, latest


def published_seasons(availability: Mapping[str, Any], product: str = "longrange_forecast") -> list[SeasonPeriod]:
    """Seasons listed for a seasonal product, keyed by the year of their start month."""

    entry = _product(availability, product)
    seasons: list[SeasonPeriod] = []
    for key, value in entry.items():
        if key.isdigit() and isinstance(value, Mapping):
            seasons.extend(SeasonPeriod(int(key), label) for label in value.get("forecast_periods_str", []))
    return sorted(seasons)


def fetch_dataset_catalog(
    base_url: str = DEFAULT_ACMAD_API_BASE_URL,
    *,
    timeout_seconds: float = 60.0,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fetch the catalogue of combined seasonal products with their published periods.

    ``get_available_datasets`` does not list these products; this catalogue does,
    together with class legends and an ``available_periods`` list for each.
    """

    client = session or requests.Session()
    response = client.get(base_url.rstrip("/") + DATASET_CATALOG_PATH, timeout=timeout_seconds)
    response.raise_for_status()
    return response.json()


def combined_product_seasons(catalog: Mapping[str, Any], key: str) -> list[SeasonPeriod]:
    """Seasons ACMAD has published for one catalogue product, oldest first."""

    datasets = catalog.get("datasets", [])
    for dataset in datasets:
        if dataset.get("key") == key:
            return sorted(
                SeasonPeriod(int(item["year"]), str(item["period"])) for item in dataset.get("available_periods") or []
            )
    raise KeyError(f"ACMAD's catalogue has no product {key!r}; available: {', '.join(d.get('key', '?') for d in datasets)}")
