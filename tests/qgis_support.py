"""Run plugin tests inside a headless QGIS, against the plugin as it ships.

These tests only run with QGIS's own Python, from a directory that does not
contain this repository's ``qgis/`` folder (it would shadow QGIS's package):

    source <env with QT_QPA_PLATFORM=offscreen, PROJ_LIB, GDAL_DATA, PYTHONPATH=src:QGIS python>
    cd /tmp && /Applications/QGIS-LTR.app/Contents/MacOS/bin/python3 -m unittest discover -s <repo>/tests -t <repo>/tests

Anywhere else they skip, so the normal test run is unaffected.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PACKAGE = "fao_niger_agroclimate"

try:  # the repository's own qgis/ folder shadows QGIS when run from the repo root
    from qgis.core import QgsApplication  # noqa: F401

    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

_app = None
_plugin_dir: tempfile.TemporaryDirectory | None = None


def require_qgis() -> None:
    if not QGIS_AVAILABLE:
        raise unittest.SkipTest("QGIS Python is not available")


def init_qgis():
    """Start one headless QgsApplication for the whole test run."""

    global _app
    require_qgis()
    if _app is None:
        from qgis.core import QgsApplication

        _app = QgsApplication([], True)
        _app.initQgis()
    return _app


def load_plugin_package():
    """Build the real plugin zip layout, put it on sys.path and import it."""

    global _plugin_dir
    require_qgis()
    if PLUGIN_PACKAGE in sys.modules:
        return sys.modules[PLUGIN_PACKAGE]
    spec = importlib.util.spec_from_file_location("build_qgis_plugin", REPO_ROOT / "scripts" / "build_qgis_plugin.py")
    builder = importlib.util.module_from_spec(spec)
    sys.modules["build_qgis_plugin"] = builder
    spec.loader.exec_module(builder)
    _plugin_dir = tempfile.TemporaryDirectory(prefix="plugin_build_")
    builder.build_plugin(REPO_ROOT, Path(_plugin_dir.name))
    sys.path.insert(0, _plugin_dir.name)
    return importlib.import_module(PLUGIN_PACKAGE)
