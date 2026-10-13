#!/usr/bin/env python3
"""Upload prepared exposure rasters, the admin level 1 boundaries and cached land cover to MinIO.

Credentials are read from the environment or a git-ignored .env file
(MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET). Objects
that already exist with the same size are skipped, so re-running is cheap.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agroclimate_core.admin1_download import ADMIN1_FILENAME, validate_admin_geojson
from agroclimate_core.storage import MinioSettings, build_client, load_env_file, upload_files

logger = logging.getLogger("upload_exposure_to_minio")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exposure-dir", type=Path, default=Path("outputs/exposure"), help="Folder with the exposure rasters.")
    parser.add_argument("--landcover-dir", type=Path, default=Path("outputs/cache/worldcover"), help="Folder with cached land cover windows.")
    parser.add_argument("--prefix", default="fao-niger-agroclimate/niger", help="Folder (key prefix) inside the bucket.")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env", help="Environment file with the MINIO_* settings.")
    parser.add_argument(
        "--admin1-file",
        type=Path,
        default=Path("outputs/admin/niger_adm1_ocha.geojson"),
        help="Niger admin level 1 regions (OCHA) to publish for the plugin's region summary. Skipped if the file is missing.",
    )
    parser.add_argument("--skip-landcover", action="store_true", help="Upload only the small files, not the cached land cover.")
    parser.add_argument("--dry-run", action="store_true", help="List what would be uploaded without contacting MinIO.")
    return parser.parse_args()


def collect_files(args: argparse.Namespace) -> dict[Path, str]:
    prefix = args.prefix.strip("/")
    files = {path: f"{prefix}/exposure/{path.name}" for path in sorted(args.exposure_dir.glob("*.tif"))}
    if args.admin1_file.is_file():
        # Refuse to publish a file the plugin would reject: validate with the plugin's own checks first.
        regions = validate_admin_geojson(args.admin1_file.read_bytes())
        logger.info("Admin level 1 file passes the plugin's checks (%d regions)", regions)
        files[args.admin1_file] = f"{prefix}/boundaries/{ADMIN1_FILENAME}"
    if not args.skip_landcover:
        files.update({path: f"{prefix}/landcover/worldcover_2021/{path.name}" for path in sorted(args.landcover_dir.glob("*.tif"))})
    return files


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()
    files = collect_files(args)
    if not files:
        logger.error("No .tif files found in %s or %s", args.exposure_dir, args.landcover_dir)
        return 1

    load_env_file(args.env_file)
    settings = MinioSettings.from_env()
    client = None if args.dry_run else build_client(settings)
    uploaded = upload_files(client, settings.bucket, files, dry_run=args.dry_run)
    logger.info("%s %d of %d files into %s/%s/", "Would upload" if args.dry_run else "Uploaded", len(uploaded), len(files), settings.bucket, args.prefix.strip("/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
