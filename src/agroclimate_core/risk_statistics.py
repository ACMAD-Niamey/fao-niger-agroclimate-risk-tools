"""Whole-map statistics for the results panel: area and share of each risk class."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from osgeo import gdal

from .admin_summary import CLASS_NAMES, CLASS_NODATA, _area_grid, _read_band


@dataclass(frozen=True)
class ClassStatistic:
    value: int
    name: str
    cells: int
    area_km2: float
    share_pct: float  # share of the scored area, not of the whole raster


@dataclass(frozen=True)
class RiskStatistics:
    classes: List[ClassStatistic]
    scored_cells: int
    total_cells: int  # cells in the raster extent, scored or not
    scored_area_km2: float
    mean_risk_score: Optional[float]  # area-weighted over scored cells; None if nothing is scored
    worst_class: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scored_cells": self.scored_cells,
            "total_cells": self.total_cells,
            "scored_area_km2": self.scored_area_km2,
            "mean_risk_score": self.mean_risk_score,
            "worst_class": self.worst_class,
            "classes": [
                {"value": c.value, "name": c.name, "cells": c.cells, "area_km2": c.area_km2, "share_pct": c.share_pct}
                for c in self.classes
            ],
        }


def summarize_risk_map(risk_class_path: str | Path, risk_score_path: str | Path) -> RiskStatistics:
    """Area per risk class over scored cells.

    Only scored cells count, so empty desert (which the map leaves blank) does
    not make the shares look safer than the agropastoral land really is.
    """

    classes, class_ds = _read_band(risk_class_path, gdal.GDT_Byte, np.uint8)
    scores, _ = _read_band(risk_score_path, gdal.GDT_Float32, np.float32)
    areas = _area_grid(class_ds)

    scored = classes != CLASS_NODATA
    scored_area = float(areas[scored].sum())
    stats: List[ClassStatistic] = []
    for value, name in CLASS_NAMES.items():
        in_class = scored & (classes == value)
        area = float(areas[in_class].sum())
        stats.append(
            ClassStatistic(
                value=value,
                name=name,
                cells=int(in_class.sum()),
                area_km2=round(area, 1),
                share_pct=round(area / scored_area * 100, 2) if scored_area > 0 else 0.0,
            )
        )
    mean = float((scores[scored] * areas[scored]).sum() / scored_area) if scored_area > 0 else None
    worst = CLASS_NAMES[int(classes[scored].max())] if scored.any() else "n/a"
    return RiskStatistics(
        classes=stats,
        scored_cells=int(scored.sum()),
        total_cells=int(classes.size),
        scored_area_km2=round(scored_area, 1),
        mean_risk_score=round(mean, 3) if mean is not None else None,
        worst_class=worst,
    )
