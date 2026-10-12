"""MinIO (S3-compatible) storage helpers for sharing prepared layers between runs.

Credentials come only from environment variables (normally a git-ignored
``.env``), never from code. Nothing here knows about rasters or QGIS, so the
scripts and the future plugin can both call it.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, MutableMapping

logger = logging.getLogger(__name__)

_MISSING_OBJECT_CODES = {"NoSuchKey", "NoSuchObject", "NotFound"}


@dataclass(frozen=True)
class MinioSettings:
    endpoint: str
    bucket: str
    # repr=False keeps secrets out of logs and tracebacks that print the settings.
    access_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    secure: bool = True

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "MinioSettings":
        env = os.environ if environ is None else environ
        missing = [name for name in ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET") if not env.get(name)]
        if missing:
            raise ValueError(f"Missing MinIO settings in the environment: {', '.join(missing)}")

        endpoint = env["MINIO_ENDPOINT"].strip()
        # The minio client wants host[:port] with the scheme given separately, but .env
        # files often hold a full URL, so accept both.
        secure = env.get("MINIO_SECURE", "").lower() not in {"0", "false", "no"}
        if endpoint.startswith("http://"):
            endpoint, secure = endpoint[len("http://"):], False
        elif endpoint.startswith("https://"):
            endpoint, secure = endpoint[len("https://"):], True
        return cls(
            endpoint=endpoint.rstrip("/"),
            bucket=env["MINIO_BUCKET"].strip(),
            access_key=env["MINIO_ACCESS_KEY"].strip(),
            secret_key=env["MINIO_SECRET_KEY"].strip(),
            secure=secure,
        )


def load_env_file(path: str | Path, environ: MutableMapping[str, str] | None = None) -> None:
    """Load KEY=VALUE lines into the environment without overriding existing variables."""

    target = os.environ if environ is None else environ
    env_path = Path(path)
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        target.setdefault(key.strip(), value.strip().strip("'\""))


def build_client(settings: MinioSettings) -> Any:
    from minio import Minio  # imported lazily so the core package works without the optional dependency

    return Minio(settings.endpoint, access_key=settings.access_key, secret_key=settings.secret_key, secure=settings.secure)


def _already_uploaded(client: Any, bucket: str, object_name: str, size: int) -> bool:
    from minio.error import S3Error

    try:
        stat = client.stat_object(bucket, object_name)
    except S3Error as exc:
        if exc.code in _MISSING_OBJECT_CODES:
            return False
        raise
    # Same name and size is treated as the same file: the tiles and rasters here
    # are written once and never edited in place.
    return stat.size == size


def upload_files(
    client: Any,
    bucket: str,
    files: Mapping[Path, str],
    *,
    skip_existing: bool = True,
    dry_run: bool = False,
) -> list[str]:
    """Upload ``{local_path: object_name}`` and return the object names written."""

    if not dry_run and not client.bucket_exists(bucket):
        raise RuntimeError(f"Bucket does not exist or is not accessible: {bucket}")

    uploaded: list[str] = []
    for local_path, object_name in files.items():
        size = local_path.stat().st_size
        if skip_existing and not dry_run and _already_uploaded(client, bucket, object_name, size):
            logger.info("Skipping %s (already in bucket, %d bytes)", object_name, size)
            continue
        logger.info("%s %s (%d bytes)", "Would upload" if dry_run else "Uploading", object_name, size)
        if not dry_run:
            client.fput_object(bucket, object_name, str(local_path))
        uploaded.append(object_name)
    return uploaded
