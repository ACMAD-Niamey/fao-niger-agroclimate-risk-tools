"""Helpers for deriving ACMAD WFS boundary requests from country metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlencode


DEFAULT_WFS_VERSION = "1.0.0"
DEFAULT_OUTPUT_FORMAT = "application/json"
DEFAULT_ACMAD_GEOSERVER_URL = "https://ada.acmad.org/geoserver"
DEFAULT_ACMAD_ADMIN_LAYERS = {
    0: "data_api_adminlevelzero",
    1: "data_api_adminlevelone",
}
DEFAULT_NIGER_COUNTRY_INFO = {
    "country_name": "Niger",
    "country_code": 181,
    "region_name": "Western Africa",
    "region_code": 6,
    "admin0_typename": DEFAULT_ACMAD_ADMIN_LAYERS[0],
    "admin1_typename": DEFAULT_ACMAD_ADMIN_LAYERS[1],
    "country_field": "country_code",
}


@dataclass(frozen=True)
class BoundaryRequest:
    """Information required to request a boundary layer from WFS."""

    wfs_url: str
    type_name: str
    country_code: str | int
    admin_level: int = 0
    country_field: str = "country_code"
    workspace: str | None = None
    output_format: str = DEFAULT_OUTPUT_FORMAT
    version: str = DEFAULT_WFS_VERSION


def normalize_country_code(country_code: str | int) -> str | int:
    """Normalize country codes used in API and WFS filters."""

    if isinstance(country_code, int):
        return country_code

    code = str(country_code).strip().upper()
    if not code:
        raise ValueError("country_code is required")
    if code.isdigit():
        return int(code)
    return code


def extract_country_code(country_info: Mapping[str, Any]) -> str | int:
    """Extract a country code from common country-info API field names."""

    for key in ("country_code", "code", "iso3", "iso_a3", "adm0_a3"):
        value = country_info.get(key)
        if value is not None and value != "":
            return normalize_country_code(value)
    raise ValueError("Country information did not include a recognizable country code")


def extract_wfs_url(country_info: Mapping[str, Any]) -> str | None:
    """Extract a WFS URL from country metadata if one is present."""

    for key in ("wfs_url", "geoserver_wfs_url", "boundary_wfs_url"):
        value = country_info.get(key)
        if value:
            return normalize_wfs_url(str(value))

    geoserver_url = country_info.get("geoserver_url")
    if geoserver_url:
        return normalize_wfs_url(str(geoserver_url))

    return None


def normalize_wfs_url(url: str) -> str:
    """Normalize GeoServer base URLs to a WFS endpoint."""

    normalized = url.strip().rstrip("/")
    if not normalized:
        raise ValueError("WFS URL is required")
    if "?" in normalized:
        return normalized
    if normalized.endswith("/ows") or normalized.endswith("/wfs"):
        return normalized
    if normalized.endswith("/geoserver"):
        return normalized + "/wfs"
    return normalized


def qualify_type_name(type_name: str, workspace: str | None = None) -> str:
    """Apply an optional GeoServer workspace to a layer/type name."""

    clean_type_name = type_name.strip()
    clean_workspace = (workspace or "").strip()
    if not clean_type_name:
        raise ValueError("WFS typeName is required")
    if ":" in clean_type_name or not clean_workspace:
        return clean_type_name
    return f"{clean_workspace}:{clean_type_name}"


def boundary_type_name(country_info: Mapping[str, Any], admin_level: int) -> str:
    """Resolve a WFS typeName for a country/admin boundary layer.

    The function supports explicit metadata fields first, then a configurable
    template. This lets the QGIS plugin work with the actual ACMAD country-info
    response once its exact field names are confirmed.
    """

    admin_level = int(admin_level)
    level_key = f"admin{admin_level}_layer"
    typename_key = f"admin{admin_level}_typename"

    for key in (typename_key, level_key, "typename", "type_name", "boundary_layer"):
        value = country_info.get(key)
        if value:
            return str(value)

    layers = country_info.get("boundary_layers") or country_info.get("admin_layers")
    if isinstance(layers, Mapping):
        for key in (str(admin_level), admin_level, f"admin{admin_level}", f"adm{admin_level}"):
            value = layers.get(key)
            if value:
                return str(value)

    template = country_info.get("boundary_layer_template")
    if template:
        return str(template).format(
            country_code=str(extract_country_code(country_info)).lower(),
            country_code_upper=extract_country_code(country_info),
            admin_level=admin_level,
        )

    if admin_level in DEFAULT_ACMAD_ADMIN_LAYERS:
        return DEFAULT_ACMAD_ADMIN_LAYERS[admin_level]

    raise ValueError(f"Country information did not include a boundary layer for admin level {admin_level}")


def build_cql_filter(country_code: str | int, country_field: str = "country_code") -> str:
    """Build a simple CQL filter for a country code."""

    safe_field = country_field.strip()
    if not safe_field.replace("_", "").isalnum():
        raise ValueError(f"Invalid country field name: {country_field!r}")
    normalized_code = normalize_country_code(country_code)
    return f"{safe_field}='{normalized_code}'"


def build_wfs_getfeature_url(request: BoundaryRequest) -> str:
    """Build a WFS GetFeature URL that returns GeoJSON."""

    wfs_url = normalize_wfs_url(request.wfs_url)
    separator = "&" if "?" in wfs_url else "?"
    query = urlencode(
        {
            "service": "WFS",
            "version": request.version,
            "request": "GetFeature",
            "typeName": qualify_type_name(request.type_name, request.workspace),
            "outputFormat": request.output_format,
            "CQL_FILTER": build_cql_filter(request.country_code, request.country_field),
        }
    )
    return f"{wfs_url}{separator}{query}"


def boundary_request_from_country_info(
    country_info: Mapping[str, Any],
    *,
    admin_level: int = 0,
    country_code: str | int | None = None,
    wfs_url: str | None = None,
    country_field: str | None = None,
    workspace: str | None = None,
) -> BoundaryRequest:
    """Create a WFS boundary request from ACMAD country-info metadata."""

    resolved_country_code = normalize_country_code(country_code) if country_code else extract_country_code(country_info)
    resolved_wfs_url = normalize_wfs_url(wfs_url) if wfs_url else extract_wfs_url(country_info)
    if not resolved_wfs_url:
        raise ValueError("A WFS URL is required in country metadata or as an override")

    return BoundaryRequest(
        wfs_url=resolved_wfs_url,
        type_name=boundary_type_name(country_info, admin_level),
        country_code=resolved_country_code,
        admin_level=int(admin_level),
        country_field=country_field or str(country_info.get("country_field", "country_code")),
        workspace=workspace or country_info.get("workspace") or country_info.get("geoserver_workspace"),
    )


def niger_boundary_request(
    *,
    wfs_url: str,
    admin_level: int = 0,
    type_name: str | None = None,
    workspace: str | None = None,
) -> BoundaryRequest:
    """Build a Niger WFS boundary request using ACMAD's numeric country code."""

    country_info = dict(DEFAULT_NIGER_COUNTRY_INFO)
    if type_name:
        country_info[f"admin{int(admin_level)}_typename"] = type_name
    return boundary_request_from_country_info(
        country_info,
        admin_level=admin_level,
        wfs_url=wfs_url,
        workspace=workspace,
    )
