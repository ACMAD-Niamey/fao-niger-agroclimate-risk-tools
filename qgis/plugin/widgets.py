"""Small reusable widgets for the results panel."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from qgis.PyQt.QtCore import QRectF, Qt
from qgis.PyQt.QtGui import QColor, QFontMetrics, QPainter
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# (label, share in percent, colour as #rrggbb)
Bar = Tuple[str, float, str]
BAR_HEIGHT = 22
BAR_GAP = 6


class ClassBarChart(QWidget):
    """Horizontal bars, one per risk class, coloured as on the map."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bars: List[Bar] = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._update_height()

    def set_bars(self, bars: List[Bar]) -> None:
        self._bars = list(bars)
        self._update_height()
        self.update()

    def bars(self) -> List[Bar]:
        return list(self._bars)

    def _update_height(self) -> None:
        self.setMinimumHeight(max(1, len(self._bars)) * (BAR_HEIGHT + BAR_GAP) + BAR_GAP)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        metrics = QFontMetrics(self.font())
        label_width = max([metrics.horizontalAdvance(label) for label, _, _ in self._bars] + [40]) + 8
        value_width = metrics.horizontalAdvance("100.0%") + 8
        track = max(10, self.width() - label_width - value_width - 4)
        for index, (label, share, colour) in enumerate(self._bars):
            top = BAR_GAP + index * (BAR_HEIGHT + BAR_GAP)
            painter.setPen(self.palette().text().color())
            painter.drawText(QRectF(0, top, label_width, BAR_HEIGHT), Qt.AlignVCenter | Qt.AlignLeft, label)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#e6e6e6"))  # the empty track makes small shares readable
            painter.drawRoundedRect(QRectF(label_width, top, track, BAR_HEIGHT), 3, 3)
            painter.setBrush(QColor(colour))
            painter.drawRoundedRect(QRectF(label_width, top, track * max(0.0, min(100.0, share)) / 100.0, BAR_HEIGHT), 3, 3)
            painter.setPen(self.palette().text().color())
            painter.drawText(
                QRectF(label_width + track + 4, top, value_width, BAR_HEIGHT),
                Qt.AlignVCenter | Qt.AlignRight,
                f"{share:.1f}%",
            )


# (key in a summary row, column title), in reading order. Keys a run does not have (for example the hectare
# columns when no land cover fractions were available) are simply left out.
REGION_FIELDS = (
    ("admin_name", "Region"),
    ("admin_code", "Code"),
    ("cells_total", "Cells"),
    ("cells_scored", "Cells scored"),
    ("zone_area_km2", "Region area (km²)"),
    ("scored_area_km2", "Scored area (km²)"),
    ("mean_risk_score", "Mean score"),
    ("max_risk_class", "Worst class"),
    ("pct_low", "Low (%)"),
    ("pct_moderate", "Moderate (%)"),
    ("pct_high", "High (%)"),
    ("pct_very_high", "Very high (%)"),
    ("high_risk_area_km2", "High-risk area (km²)"),
    ("cultivated_ha_total", "Cropland (ha)"),
    ("cultivated_ha_high_risk", "Cropland in high risk (ha)"),
    ("rangeland_ha_total", "Rangeland (ha)"),
    ("rangeland_ha_high_risk", "Rangeland in high risk (ha)"),
)


class RegionTableDialog(QDialog):
    """Every figure of the region summary in a window of its own, with room to scroll and a Copy button.

    The panel's table is a compact view of a wide table; this is the whole thing, sortable and
    copyable as tab-separated text that pastes straight into a spreadsheet.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Risk by region")
        self.resize(1100, 460)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 0)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        self.copy_button = QPushButton("Copy table")
        self.copy_button.setToolTip("Copies the whole table as tab-separated text. Paste it into a spreadsheet.")
        self.close_button = QPushButton("Close")
        buttons.addStretch(1)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.copy_button.clicked.connect(self._copy)
        self.close_button.clicked.connect(self.close)
        self._columns: List[Tuple[str, str]] = []
        self._rows: List[Dict[str, Any]] = []

    def set_rows(self, rows: Sequence[Dict[str, Any]]) -> None:
        self._rows = list(rows)
        present = {key for row in self._rows for key in row}
        self._columns = [(key, title) for key, title in REGION_FIELDS if key in present]
        self.table.setSortingEnabled(False)
        self.table.setColumnCount(len(self._columns))
        self.table.setHorizontalHeaderLabels([title for _key, title in self._columns])
        self.table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            for c, (key, _title) in enumerate(self._columns):
                value = row.get(key)
                item = QTableWidgetItem()
                if value is None:
                    item.setText("n/a")
                elif isinstance(value, (int, float)):
                    item.setData(Qt.DisplayRole, value)  # numbers sort as numbers, not as text
                else:
                    item.setText(str(value))
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

    def as_text(self) -> str:
        """The whole table, tab separated, with a header line."""

        def cell(value: Any) -> str:
            if value is None:
                return "n/a"
            return f"{value:.2f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)

        lines = ["\t".join(title for _key, title in self._columns)]
        lines += ["\t".join(cell(row.get(key)) for key, _title in self._columns) for row in self._rows]
        return "\n".join(lines)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.as_text())
