"""QGIS plugin wrapper for FAO Niger agroclimate risk tools."""

from __future__ import annotations

from pathlib import Path

from qgis.PyQt.QtWidgets import QAction
from qgis.core import Qgis, QgsApplication

from .processing.provider import FaoNigerAgroclimateProvider


class FaoNigerAgroclimatePlugin:
    """Minimal plugin shell that registers the Processing provider."""

    MENU_NAME = "FAO Niger Agroclimate"
    STYLE_ACTIONS = (
        ("Apply Risk Class Style", "risk_class.qml"),
        ("Apply Risk Score Style", "risk_score.qml"),
        ("Apply CDI Hazard Style", "cdi_hazard.qml"),
    )

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.actions = []

    def initGui(self):
        existing_provider = QgsApplication.processingRegistry().providerById("fao_niger_agroclimate")
        if existing_provider is not None:
            QgsApplication.processingRegistry().removeProvider(existing_provider)

        self.provider = FaoNigerAgroclimateProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)
        self._add_style_actions()

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.MENU_NAME, action)
        self.actions = []

        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None

    def _add_style_actions(self):
        for label, style_name in self.STYLE_ACTIONS:
            action = QAction(label, self.iface.mainWindow())
            action.triggered.connect(lambda _checked=False, name=style_name: self._apply_style_to_active_layer(name))
            self.iface.addPluginToMenu(self.MENU_NAME, action)
            self.actions.append(action)

    def _apply_style_to_active_layer(self, style_name):
        layer = self.iface.activeLayer()
        if layer is None:
            self._push_message("Select a raster layer first.", Qgis.Warning)
            return

        if not hasattr(layer, "loadNamedStyle"):
            self._push_message("The selected layer does not support QGIS named styles.", Qgis.Warning)
            return

        style_path = Path(__file__).resolve().parent / "styles" / style_name
        if not style_path.exists():
            self._push_message(f"Style file not found: {style_path}", Qgis.Critical)
            return

        result = layer.loadNamedStyle(str(style_path))
        message = result[0] if isinstance(result, tuple) and result else ""
        ok = result[1] if isinstance(result, tuple) and len(result) > 1 else True
        if not ok:
            self._push_message(message or f"Could not apply {style_name}.", Qgis.Warning)
            return
        layer.triggerRepaint()
        self.iface.layerTreeView().refreshLayerSymbology(layer.id())
        self._push_message(f"Applied {style_name} to {layer.name()}.", Qgis.Success)

    def _push_message(self, message, level):
        self.iface.messageBar().pushMessage(self.MENU_NAME, message, level=level, duration=5)
