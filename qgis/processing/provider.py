"""Processing provider for FAO Niger agroclimate risk algorithms."""

from __future__ import annotations

from pathlib import Path

from qgis.core import QgsProcessingProvider

try:
    from qgis.PyQt.QtGui import QIcon
except ImportError:
    QIcon = None

from .agropastoral_drought_risk import AgropastoralDroughtRiskAlgorithm
from .fetch_acmad_boundary import FetchAcmadBoundaryAlgorithm


class FaoNigerAgroclimateProvider(QgsProcessingProvider):
    """Registers FAO Niger agroclimate algorithms in QGIS Processing."""

    def id(self):
        return "fao_niger_agroclimate"

    def name(self):
        return "FAO Niger Agroclimate"

    def longName(self):
        return self.name()

    def icon(self):
        if QIcon is None:
            return super().icon()

        plugin_icon = Path(__file__).resolve().parents[1] / "plugin" / "icon.svg"
        packaged_icon = Path(__file__).resolve().parents[1] / "icon.svg"
        for icon_path in (plugin_icon, packaged_icon):
            if icon_path.exists():
                return QIcon(str(icon_path))

        return QIcon()

    def loadAlgorithms(self):
        self.addAlgorithm(FetchAcmadBoundaryAlgorithm())
        self.addAlgorithm(AgropastoralDroughtRiskAlgorithm())
