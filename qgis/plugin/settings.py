"""Remembered options, kept in the QGIS profile.

The language model key is the one sensitive value. By default it lives only
in memory for the QGIS session; it is written to the profile (unencrypted)
only if the user ticks "remember". Nothing here logs or prints the key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from qgis.core import QgsSettings

from .agroclimate_core.llm import LlmSettings

PREFIX = "FaoNigerAgroclimate"
DEFAULT_OUTPUT_ROOT = Path.home() / "fao_niger_agroclimate_outputs"


class PluginSettings:
    """Typed access to the plugin's remembered options."""

    def __init__(self, store: Optional[QgsSettings] = None) -> None:
        self._store = store or QgsSettings()
        self._session_key = ""  # kept in memory only unless the user chooses to remember it

    def _get(self, name: str, default: Any, value_type: type) -> Any:
        return self._store.value(f"{PREFIX}/{name}", default, type=value_type)

    def _set(self, name: str, value: Any) -> None:
        self._store.setValue(f"{PREFIX}/{name}", value)

    # --- run options -----------------------------------------------------------------------
    @property
    def output_root(self) -> Path:
        return Path(self._get("output_root", str(DEFAULT_OUTPUT_ROOT), str))

    @output_root.setter
    def output_root(self, value: Path) -> None:
        self._set("output_root", str(value))

    @property
    def exposure_dir(self) -> Path:
        return Path(self._get("exposure_dir", str(self.output_root / "exposure"), str))

    @exposure_dir.setter
    def exposure_dir(self, value: Path) -> None:
        self._set("exposure_dir", str(value))

    @property
    def strict_dates(self) -> bool:
        return self._get("strict_dates", False, bool)

    @strict_dates.setter
    def strict_dates(self, value: bool) -> None:
        self._set("strict_dates", bool(value))

    @property
    def max_fallback_dekads(self) -> int:
        return self._get("max_fallback_dekads", 3, int)

    @max_fallback_dekads.setter
    def max_fallback_dekads(self, value: int) -> None:
        self._set("max_fallback_dekads", int(value))

    @property
    def use_acmad_exposure(self) -> bool:
        """Fetch ACMAD's prepared exposure (seconds) rather than build it from land cover (minutes)."""

        return self._get("use_acmad_exposure", True, bool)

    @use_acmad_exposure.setter
    def use_acmad_exposure(self, value: bool) -> None:
        self._set("use_acmad_exposure", bool(value))

    @property
    def use_acmad_regions(self) -> bool:
        """Summarise by ACMAD's admin level 1 regions rather than a layer the user picks."""

        return self._get("use_acmad_regions", True, bool)

    @use_acmad_regions.setter
    def use_acmad_regions(self, value: bool) -> None:
        self._set("use_acmad_regions", bool(value))

    # --- language model --------------------------------------------------------------------
    def load_llm(self) -> LlmSettings:
        stored_key = self._get("llm/api_key", "", str)
        return LlmSettings(
            base_url=self._get("llm/base_url", "", str),
            api_key=stored_key or self._session_key,
            model=self._get("llm/model", "", str),
            language=self._get("llm/language", "en", str),
            extra_fields=self._get("llm/extra_fields", "", str),
        )

    @property
    def llm_key_is_remembered(self) -> bool:
        return bool(self._get("llm/api_key", "", str))

    def save_llm(self, settings: LlmSettings, *, remember_key: bool) -> None:
        self._set("llm/base_url", settings.base_url.strip())
        self._set("llm/model", settings.model.strip())
        self._set("llm/language", settings.language)
        self._set("llm/extra_fields", settings.extra_fields.strip())
        self._session_key = settings.api_key.strip()
        # Writing an empty value clears a key that was remembered earlier.
        self._set("llm/api_key", self._session_key if remember_key else "")
