"""QGIS plugin wrapper for FAO Niger agroclimate risk tools."""

from __future__ import annotations

from qgis.core import QgsApplication

from .processing.provider import FaoNigerAgroclimateProvider


class FaoNigerAgroclimatePlugin:
    """Minimal plugin shell that registers the Processing provider."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initGui(self):
        existing_provider = QgsApplication.processingRegistry().providerById("fao_niger_agroclimate")
        if existing_provider is not None:
            QgsApplication.processingRegistry().removeProvider(existing_provider)

        self.provider = FaoNigerAgroclimateProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
