"""A Processing Toolbox entry that opens the Agroclimate Risk panel.

Users look for tools in the Processing Toolbox first. Without this entry the
only FAO Niger tools listed there were the older vector tools, and the real
map tool (the dock panel) was easy to miss.
"""

from qgis.core import QgsProcessingAlgorithm, QgsProcessingException

PLUGIN_CLASS_NAME = "FaoNigerAgroclimatePlugin"


def find_plugin():
    """The loaded plugin instance, found by its class so the folder name does not matter."""

    import qgis.utils

    for plugin in qgis.utils.plugins.values():
        if type(plugin).__name__ == PLUGIN_CLASS_NAME and hasattr(plugin, "show_panel"):
            return plugin
    return None


class OpenRiskPanelAlgorithm(QgsProcessingAlgorithm):
    def createInstance(self):
        return OpenRiskPanelAlgorithm()

    def name(self):
        return "open_risk_panel"

    def displayName(self):
        return "Agroclimate Risk panel (open this to build the risk map)"

    def group(self):
        return "FAO Niger Agroclimate"

    def groupId(self):
        return "fao_niger_agroclimate"

    def shortHelpString(self):
        return (
            "Opens the Agroclimate Risk panel. This is the main tool: pick a period ACMAD has published, press "
            "Run, and it builds the risk map, adds the styled layers to QGIS and shows statistics and a region "
            "summary. You can also open it from the toolbar icon or from Plugins > FAO Niger Agroclimate."
        )

    def flags(self):
        # Opening a window must happen on the main thread, and a model cannot use it.
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading | QgsProcessingAlgorithm.FlagHideFromModeler

    def initAlgorithm(self, config=None):
        pass

    def processAlgorithm(self, parameters, context, feedback):
        plugin = find_plugin()
        if plugin is None:
            raise QgsProcessingException(
                "The FAO Niger Agroclimate plugin is not loaded. Enable it in Plugins > Manage and Install Plugins, "
                "restart QGIS if you just reinstalled it, and try again."
            )
        plugin.show_panel()
        feedback.pushInfo("The Agroclimate Risk panel is open. You can close this dialog.")
        return {}
