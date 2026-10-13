"""Add a finished run to the QGIS project and style it.

Only this module and ``controller`` touch the project. It never runs the
workflow; it receives a ``RunResult`` and puts its rasters on the map.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from qgis.core import QgsCoordinateTransform, QgsProject, QgsRasterLayer

from .agroclimate_core.workflow import RunResult
from .styles import (
    CDI_HAZARD_STYLE,
    COMBINED_HAZARD_STYLE,
    RISK_CLASS_STYLE,
    RISK_SCORE_STYLE,
    style_file,
)

logger = logging.getLogger(__name__)


@dataclass
class AddedLayers:
    group_name: str
    layers: Dict[str, QgsRasterLayer] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def group_name_for(result: RunResult) -> str:
    return f"Agropastoral risk - {result.hazard_label}"


def _layer_specs(result: RunResult) -> List[dict]:
    """Which rasters go on the map, in drawing order (top first)."""

    specs = [
        {"key": "risk_class", "path": result.outputs["risk_class"], "style": RISK_CLASS_STYLE,
         "name": f"Risk class ({result.hazard_label})", "visible": True},
        {"key": "risk_score", "path": result.outputs["risk_score"], "style": RISK_SCORE_STYLE,
         "name": f"Risk score ({result.hazard_label})", "visible": False},
    ]
    if result.hazard_name == "combined_hazard":
        specs.append({"key": "hazard", "path": result.outputs["combined_hazard"], "style": COMBINED_HAZARD_STYLE,
                      "name": f"Combined hazard ({result.hazard_label})", "visible": False})
    else:
        # The clipped CDI file holds ACMAD's raw 0-14 codes. Band 1 of the stack is the 0-3
        # hazard score the CDI style is written for, so that is what goes on the map.
        specs.append({"key": "hazard", "path": result.outputs["risk_stack"], "style": CDI_HAZARD_STYLE,
                      "name": f"CDI hazard score ({result.hazard_label})", "visible": False})
    return specs


def _remove_existing_group(project: QgsProject, name: str) -> None:
    root = project.layerTreeRoot()
    existing = root.findGroup(name)
    if existing is None:
        return
    layer_ids = [node.layerId() for node in existing.findLayers()]
    project.removeMapLayers(layer_ids)
    root.removeChildNode(existing)


def add_run_to_project(
    result: RunResult,
    project: QgsProject,
    styles_dir: Path,
    *,
    canvas=None,
) -> AddedLayers:
    """Add the run's rasters as a group, styled, and zoom to the risk map.

    Running the same period twice replaces its group instead of piling up
    duplicates.
    """

    added = AddedLayers(group_name=group_name_for(result))
    _remove_existing_group(project, added.group_name)
    group = project.layerTreeRoot().insertGroup(0, added.group_name)

    for spec in _layer_specs(result):
        layer = QgsRasterLayer(str(spec["path"]), spec["name"])
        if not layer.isValid():
            added.warnings.append(f"Could not open {spec['path']}")
            continue
        message, loaded = layer.loadNamedStyle(str(style_file(styles_dir, spec["style"])))
        if not loaded:
            added.warnings.append(f"Could not apply {spec['style']}: {message}")
        project.addMapLayer(layer, False)
        node = group.addLayer(layer)
        node.setItemVisibilityChecked(spec["visible"])
        added.layers[spec["key"]] = layer

    risk_layer: Optional[QgsRasterLayer] = added.layers.get("risk_class")
    if canvas is not None and risk_layer is not None:
        transform = QgsCoordinateTransform(risk_layer.crs(), canvas.mapSettings().destinationCrs(), project)
        canvas.setExtent(transform.transformBoundingBox(risk_layer.extent()))
        canvas.refresh()
    return added
