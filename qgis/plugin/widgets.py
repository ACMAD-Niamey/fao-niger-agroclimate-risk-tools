"""Small reusable widgets for the results panel."""

from __future__ import annotations

from typing import List, Tuple

from qgis.PyQt.QtCore import QRectF, Qt
from qgis.PyQt.QtGui import QColor, QFontMetrics, QPainter
from qgis.PyQt.QtWidgets import QSizePolicy, QWidget

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
