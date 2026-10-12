#!/usr/bin/env python3
"""Build a distributable QGIS plugin zip.

The development layout keeps plugin code, Processing algorithms, and shared
Python package code in separate repository folders. QGIS users need one plugin
folder or zip. This script assembles that installable package.
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


PLUGIN_NAME = "fao_niger_agroclimate"


def copytree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def build_plugin(repo_root: Path, output_dir: Path) -> Path:
    build_root = output_dir / PLUGIN_NAME
    zip_path = output_dir / f"{PLUGIN_NAME}.zip"

    if build_root.exists():
        shutil.rmtree(build_root)
    if zip_path.exists():
        zip_path.unlink()

    build_root.mkdir(parents=True)

    plugin_source = repo_root / "qgis" / "plugin"
    processing_source = repo_root / "qgis" / "processing"
    package_source = repo_root / "src" / "agroclimate_core"

    for file_name in ("__init__.py", "metadata.txt", "plugin.py", "icon.svg"):
        shutil.copy2(plugin_source / file_name, build_root / file_name)

    copytree(processing_source, build_root / "processing")
    copytree(package_source, build_root / "agroclimate_core")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(build_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output_dir))

    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the QGIS plugin zip.")
    parser.add_argument(
        "--output-dir",
        default="dist/qgis",
        help="Directory where the plugin folder and zip should be written.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = build_plugin(repo_root, output_dir)
    print(zip_path)


if __name__ == "__main__":
    main()
