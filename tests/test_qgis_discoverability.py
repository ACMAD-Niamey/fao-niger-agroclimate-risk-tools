"""The panel must be easy to find, and a failed load step must be visible, not silent."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import qgis_support
from test_qgis_panel import FakeIface, PanelTestCase, run_inline


class FakeBarItem:
    def __init__(self, title, text):
        from qgis.PyQt.QtWidgets import QHBoxLayout

        self.title, self.text, self._layout = title, text, QHBoxLayout()

    def layout(self):
        return self._layout

    def buttons(self):
        from qgis.PyQt.QtWidgets import QPushButton

        found = []
        for index in range(self._layout.count()):
            widget = self._layout.itemAt(index).widget()
            if isinstance(widget, QPushButton):
                found.append(widget)
        return found


class BarWithWidgets:
    """A message bar that also supports createMessage/pushWidget, as QGIS's does."""

    def __init__(self):
        self.messages, self.items = [], []

    def pushMessage(self, title, text, level=None, duration=None):
        self.messages.append((str(text), level))

    def createMessage(self, title, text):
        return FakeBarItem(title, text)

    def pushWidget(self, item, level=None, duration=None):
        self.items.append(item)


class FailingIface(FakeIface):
    def __init__(self, fail_on: str):
        super().__init__()
        self.bar = BarWithWidgets()
        self._fail_on = fail_on

    def addToolBarIcon(self, action):
        if self._fail_on == "toolbar":
            raise RuntimeError("toolbar is unavailable")
        super().addToolBarIcon(action)


class DiscoverabilityTests(PanelTestCase):
    def make_plugin(self, iface):
        import fao_niger_agroclimate.plugin as plugin_module

        original = plugin_module.RiskPanelController
        plugin_module.RiskPanelController = lambda ifc, plugin_dir: self.RiskPanelController(
            ifc, plugin_dir, services=self.services, settings=self.settings, submit_task=run_inline, prompter=self.prompter
        )
        self.addCleanup(setattr, plugin_module, "RiskPanelController", original)
        plugin = plugin_module.FaoNigerAgroclimatePlugin(iface, settings=self.store)
        self.addCleanup(plugin.unload)
        return plugin

    def test_a_toolbox_entry_opens_the_panel_and_comes_first(self):
        import qgis.utils
        from fao_niger_agroclimate.processing.provider import FaoNigerAgroclimateProvider
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        provider = FaoNigerAgroclimateProvider()
        provider.loadAlgorithms()
        names = sorted(alg.displayName() for alg in provider.algorithms())
        self.assertTrue(names[0].startswith("Agroclimate Risk panel"), names)  # the toolbox sorts A-Z, so it is listed first
        algorithm = provider.algorithm("open_risk_panel")
        self.assertIsNotNone(algorithm)

        opened = []

        class FakePlugin:
            def show_panel(self):
                opened.append(True)

        FakePlugin.__name__ = "FaoNigerAgroclimatePlugin"
        qgis.utils.plugins["fake_fao"] = FakePlugin()
        self.addCleanup(qgis.utils.plugins.pop, "fake_fao", None)
        result = algorithm.create().processAlgorithm({}, QgsProcessingContext(), QgsProcessingFeedback())
        self.assertEqual(opened, [True])
        self.assertEqual(result, {})

    def test_the_toolbox_entry_explains_when_the_plugin_is_not_loaded(self):
        from fao_niger_agroclimate.processing.provider import FaoNigerAgroclimateProvider
        from qgis.core import QgsProcessingContext, QgsProcessingException, QgsProcessingFeedback

        provider = FaoNigerAgroclimateProvider()
        provider.loadAlgorithms()
        with self.assertRaises(QgsProcessingException) as caught:
            provider.algorithm("open_risk_panel").create().processAlgorithm({}, QgsProcessingContext(), QgsProcessingFeedback())
        self.assertIn("not loaded", str(caught.exception))

    def test_the_old_vector_tool_says_it_is_not_the_map_tool(self):
        from fao_niger_agroclimate.processing.provider import FaoNigerAgroclimateProvider

        provider = FaoNigerAgroclimateProvider()
        provider.loadAlgorithms()
        help_text = provider.algorithm("agropastoral_drought_risk").shortHelpString()
        self.assertIn("Agroclimate Risk panel (open this to build the risk map)", help_text)

    def test_loading_announces_the_panel_once_per_version_with_a_button_that_opens_it(self):
        iface = FailingIface(fail_on="")
        plugin = self.make_plugin(iface)
        plugin.initGui()
        self.assertEqual(len(iface.bar.items), 1)
        buttons = iface.bar.items[0].buttons()
        self.assertEqual([b.text() for b in buttons], ["Open the risk panel"])
        buttons[0].click()
        self.assertIsNotNone(plugin.controller)  # the button opened the panel

        plugin.unload()
        second = self.make_plugin(FailingIface(fail_on=""))
        second.initGui()
        self.assertEqual(len(second.iface.bar.items), 0)  # already announced for this version

    def test_a_failing_load_step_is_reported_and_the_rest_still_load(self):
        iface = FailingIface(fail_on="toolbar")
        plugin = self.make_plugin(iface)
        plugin.initGui()
        self.assertTrue(any("could not load" in text.lower() for text, _ in iface.bar.messages), iface.bar.messages)
        self.assertGreaterEqual(len(plugin.actions), 4)  # the style actions were still added
        self.assertEqual(len(iface.menu), 5)  # panel entry + four style actions in the menu

    def test_the_plugin_version_is_read_from_the_package(self):
        import fao_niger_agroclimate.plugin as plugin_module

        version = plugin_module.plugin_version(Path(plugin_module.__file__).resolve().parent)
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
