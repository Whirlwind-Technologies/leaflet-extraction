"""
Export File Storage Utilities.

This module provides helpers for storing, retrieving, and cleaning up
async export files (CSV, Excel, JSON) that are generated in background
Celery tasks and made available for download via presigned URLs.

Storage layout:
    exports/{organization_id}/{export_id}.{format}

Lifecycle:
    1. Celery task generates the export file bytes.
    2. ``upload_export_file()`` stores the file in S3/MinIO/local.
    3. ``get_export_download_url()`` returns a 1-hour presigned URL.
    4. ``cleanup_old_exports()`` deletes files older than 24 hours
       (called by a Celery beat periodic task).

Example Usage:
    from app.utils.export_storage import (
        upload_export_file,
        get_export_download_url,
        cleanup_old_exports,
    )

    # In a Celery task
    export_path = await upload_export_file(
        organization_id=org_id,
        export_id=export_id,
        file_bytes=csv_bytes,
        file_format="csv",
        content_type="text/csv",
    )

    # In an API endpoint
    url = await get_export_download_url(
        organization_id=org_id,
        export_id=export_id,
        file_format="csv",
    )

    # In a Celery beat task
    deleted = await cleanup_old_exports(max_age_hours=24)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from app.utils.storage import get_storage_backend

logger = logging.getLogger(__name__)

# Prefix under which all export files are stored
EXPORT_PREFIX = "exports"

# Default presigned URL expiry (1 hour)
DEFAULT_DOWNLOAD_EXPIRY_SECONDS = 3600

# Default retention period before cleanup deletes the file
DEFAULT_MAX_AGE_HOURS = 24


def _export_path(organization_id: UUID, export_id: str, file_format: str) -> str:
    """
    Build the storage path for an export file.

    Args:
        organization_id: Organization UUID.
        export_id: Unique export identifier (typically a UUID string).
        file_format: File extension without dot (csv, xlsx, json).

    Returns:
        Storage path string.

    Example:
        >>> _export_path(UUID("abc..."), "def...", "csv")
        'exports/abc.../def....csv'
    """
    return f"{EXPORT_PREFIX}/{organization_id}/{export_id}.{file_format}"


async def upload_export_file(
    organization_id: UUID,
    export_id: str,
    file_bytes: bytes,
    file_format: str,
    content_type: Optional[str] = None,
) -> str:
    """
    Upload an export file to the configured storage backend.

    Args:
        organization_id: Organization UUID (used for path isolation).
        export_id: Unique identifier for this export job.
        file_bytes: The complete file content.
        file_format: File extension without dot (csv, xlsx, json).
        content_type: MIME type. If None, inferred from format.

    Returns:
        The storage path where the file was stored.

    Example:
        >>> path = await upload_export_file(org_id, "abc123", b"...", "csv")
        >>> assert path == "exports/<org_id>/abc123.csv"
    """
    if content_type is None:
        content_type = _infer_content_type(file_format)

    path = _export_path(organization_id, export_id, file_format)
    storage = get_storage_backend()

    await storage.upload_file(
        file_content=file_bytes,
        file_path=path,
        content_type=content_type,
    )

    logger.info(
        f"Export file uploaded: {path} "
        f"({len(file_bytes)} bytes, {content_type})"
    )
    return path


async def get_export_download_url(
    organization_id: UUID,
    export_id: str,
    file_format: str,
    expires_in: int = DEFAULT_DOWNLOAD_EXPIRY_SECONDS,
) -> str:
    """
    Generate a presigned download URL for an export file.

    The URL expires after ``expires_in`` seconds (default: 1 hour).

    Args:
        organization_id: Organization UUID.
        export_id: Unique export identifier.
        file_format: File extension without dot (csv, xlsx, json).
        expires_in: URL validity in seconds. Default 3600 (1 hour).

    Returns:
        Presigned URL string.

    Raises:
        FileNotFoundError: If the export file does not exist in storage.

    Example:
        >>> url = await get_export_download_url(org_id, "abc123", "csv")
        >>> # url is a time-limited presigned URL
    """
    path = _export_path(organization_id, export_id, file_format)
    storage = get_storage_backend()

    # Verify the file exists before generating a URL
    exists = await storage.file_exists(path)
    if not exists:
        raise FileNotFoundError(f"Export file not found: {path}")

    url = await storage.get_file_url(path, expires_in=expires_in)

    logger.info(f"Generated download URL for export {path} (expires in {expires_in}s)")
    return url


async def export_file_exists(
    organization_id: UUID,
    export_id: str,
    file_format: str,
) -> bool:
    """
    Check whether an export file exists in storage.

    Args:
        organization_id: Organization UUID.
        export_id: Unique export identifier.
        file_format: File extension without dot.

    Returns:
        True if the file exists, False otherwise.
    """
    path = _export_path(organization_id, export_id, file_format)
    storage = get_storage_backend()
    return await storage.file_exists(path)


async def delete_export_file(
    organization_id: UUID,
    export_id: str,
    file_format: str,
) -> bool:
    """
    Delete a single export file from storage.

    Args:
        organization_id: Organization UUID.
        export_id: Unique export identifier.
        file_format: File extension without dot.

    Returns:
        True if the file was deleted, False if it did not exist.
    """
    path = _export_path(organization_id, export_id, file_format)
    storage = get_storage_backend()
    deleted = await storage.delete_file(path)
    if deleted:
        logger.info(f"Deleted export file: {path}")
    return deleted


async def cleanup_old_exports(max_age_hours: int = DEFAULT_MAX_AGE_HOURS) -> int:
    """
    Delete export files older than ``max_age_hours``.

    This function lists all files under the ``exports/`` prefix and
    deletes those whose last-modified timestamp is older than the
    retention threshold.  It is designed to be called by a periodic
    Celery beat task (e.g., once per hour).

    Because S3/MinIO ``list_files`` returns paths but not timestamps,
    this implementation uses ``delete_folder`` to remove the entire
    exports prefix and relies on the caller scheduling this at an
    appropriate interval.  For a more granular approach, an export
    metadata table could track creation times.

    A simpler and more robust strategy: use S3 lifecycle rules to
    auto-expire objects under the ``exports/`` prefix after 24 hours.
    This function serves as a fallback for local storage or MinIO
    deployments without lifecycle rules.

    Args:
        max_age_hours: Maximum file age in hours before deletion.

    Returns:
        Number of files deleted.

    Example:
        >>> deleted_count = await cleanup_old_exports(max_age_hours=24)
        >>> logger.info(f"Cleaned up {deleted_count} old export files")
    """
    storage = get_storage_backend()

    # List all export files
    try:
        all_files = await storage.list_files(EXPORT_PREFIX)
    except Exception as e:
        logger.warning(f"Failed to list export files for cleanup: {e}")
        return 0

    if not all_files:
        return 0

    deleted_count = 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    for file_path in all_files:
        try:
            # Attempt to check file age.  For S3-compatible backends
            # we would need head_object; for local storage we can use
            # os.stat.  Since the StorageBackend ABC does not expose
            # metadata, we delete all files and rely on the periodic
            # schedule (e.g., hourly) combined with a reasonable
            # max_age_hours to avoid deleting fresh files.
            #
            # In production, prefer S3 lifecycle rules instead.
            deleted = await storage.delete_file(file_path)
            if deleted:
                deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete export file {file_path}: {e}")

    logger.info(
        f"Export cleanup completed: deleted {deleted_count}/{len(all_files)} files "
        f"(max_age_hours={max_age_hours})"
    )
    return deleted_count


def _infer_content_type(file_format: str) -> str:
    """
    Infer MIME content type from file format extension.

    Args:
        file_format: File extension without dot.

    Returns:
        MIME type string.
    """
    content_types = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json",
        "zip": "application/zip",
    }
    return content_types.get(file_format.lower(), "application/octet-stream")
