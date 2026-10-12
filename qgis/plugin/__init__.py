"""QGIS plugin entry point."""


def classFactory(iface):
    from .plugin import FaoNigerAgroclimatePlugin

    return FaoNigerAgroclimatePlugin(iface)
