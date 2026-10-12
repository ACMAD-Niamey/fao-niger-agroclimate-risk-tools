"""Write the per-run metadata file that records which data a map was built from."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

METADATA_FILENAME = "run_metadata.json"


def _json_default(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialise {type(value).__name__} to run metadata")


def write_run_metadata(output_dir: str | Path, payload: Mapping[str, Any]) -> Path:
    """Write ``run_metadata.json`` with a UTC timestamp added to ``payload``.

    The requested date and the date each input actually used sit side by side,
    so a reader can see at a glance when a map is built from older data than
    the date it was asked for.
    """

    path = Path(output_dir) / METADATA_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload}
    path.write_text(json.dumps(document, indent=2, default=_json_default, sort_keys=False), encoding="utf-8")
    return path
