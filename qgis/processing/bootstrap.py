"""Import bootstrap for QGIS Processing scripts.

QGIS may run Processing scripts without installing this repository as a Python
package. This helper adds the repository's ``src`` directory to ``sys.path`` so
Processing algorithms and future plugin code can import the shared core logic.
"""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_src_path() -> None:
    """Add the repository ``src`` directory to ``sys.path`` if it exists."""

    src_path = Path(__file__).resolve().parents[2] / "src"
    if src_path.exists():
        src_text = str(src_path)
        if src_text not in sys.path:
            sys.path.insert(0, src_text)
