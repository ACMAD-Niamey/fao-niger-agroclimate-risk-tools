"""Style file lookup and colours, shared by the map layers and the results panel.

The results chart reads its colours from the same .qml files that style the
map, so a class can never be one colour on the map and another in the panel.
This module has no QGIS imports so it can be tested anywhere.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple

RISK_CLASS_STYLE = "risk_class.qml"
RISK_SCORE_STYLE = "risk_score.qml"
CDI_HAZARD_STYLE = "cdi_hazard.qml"
COMBINED_HAZARD_STYLE = "combined_hazard.qml"


def style_file(styles_dir: Path, name: str) -> Path:
    path = Path(styles_dir) / name
    if not path.is_file():
        raise FileNotFoundError(f"Style file not found: {path}")
    return path


def class_colors(qml_path: Path) -> Dict[int, Tuple[str, str]]:
    """``{class value: (label, colour)}`` from a paletted or discrete style."""

    root = ET.parse(qml_path).getroot()
    items = root.findall(".//paletteEntry") or root.findall(".//item")
    return {int(float(item.get("value"))): (item.get("label", ""), item.get("color", "#999999")) for item in items}
