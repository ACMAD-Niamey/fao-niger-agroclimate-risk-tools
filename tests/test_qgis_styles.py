import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

STYLE_DIR = Path(__file__).resolve().parents[1] / "qgis" / "styles"


def _entries(name: str) -> list[tuple[float, str, str]]:
    root = ET.parse(STYLE_DIR / name).getroot()
    items = root.findall(".//paletteEntry") or root.findall(".//item")
    return [(float(item.get("value")), item.get("label"), item.get("color").lower()) for item in items]


def _luminance(hex_color: str) -> float:
    """Relative luminance (WCAG): lower means darker."""

    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


class StyleTests(unittest.TestCase):
    ORDERED = ("risk_class.qml", "risk_score.qml", "cdi_hazard.qml", "combined_hazard.qml")

    def test_every_style_is_well_formed_xml(self):
        for path in STYLE_DIR.glob("*.qml"):
            ET.parse(path)

    def test_ordered_classes_get_monotonically_darker(self):
        """Ordinal data needs lightness to rise with severity, which stays readable in greyscale print."""

        for name in self.ORDERED:
            lum = [_luminance(color) for _, _, color in sorted(_entries(name))]
            self.assertEqual(lum, sorted(lum, reverse=True), f"{name} is not light-to-dark")

    def test_risk_class_labels_state_the_score_breaks_used_by_the_code(self):
        labels = [label for _, label, _ in sorted(_entries("risk_class.qml"))]
        self.assertEqual(
            labels,
            ["Low (< 1.0)", "Moderate (1.0 to < 1.7)", "High (1.7 to < 2.4)", "Very high (>= 2.4)"],
        )

    def test_no_red_green_pairs_in_class_colours(self):
        """Red and green are not separable for common colour-vision deficiencies."""

        for name in self.ORDERED:
            for _, _, color in _entries(name):
                red, green = int(color[1:3], 16), int(color[3:5], 16)
                self.assertFalse(green > red + 40, f"{name}: {color} reads as green")

    def test_combined_hazard_style_has_the_nine_acmad_classes(self):
        entries = sorted(_entries("combined_hazard.qml"))
        self.assertEqual([int(v) for v, _, _ in entries], list(range(1, 10)))
        self.assertEqual(entries[0][1], "No drought hazard")
        self.assertEqual(entries[2][1], "Low (Watch)")
        self.assertEqual(entries[8][1], "Extreme")


if __name__ == "__main__":
    unittest.main()
