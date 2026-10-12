"""QGIS plugin wrapper for FAO Niger agroclimate risk tools."""

from __future__ import annotations

import sys
from pathlib import Path

from qgis.core import QgsApplication


def _ensure_repo_paths() -> None:
    plugin_dir = Path(__file__).resolve().parent
    repo_root = plugin_dir.parents[1]
    src_path = repo_root / "src"
    processing_path = repo_root / "qgis" / "processing"
    for path in (processing_path, src_path):
        path_text = str(path)
        if path.exists() and path_text not in sys.path:
            sys.path.insert(0, path_text)


_ensure_repo_paths()

from provider import FaoNigerAgroclimateProvider


class FaoNigerAgroclimatePlugin:
    """Minimal plugin shell that registers the Processing provider."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initGui(self):
        self.provider = FaoNigerAgroclimateProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
