"""
Export Job Model.

This module defines the ExportJob model for tracking asynchronous product
export jobs that are dispatched to Celery when the result set exceeds 1000
products.

Lifecycle:
    1. API endpoint creates an ExportJob record with status=PENDING.
    2. Celery task picks it up, sets status=PROCESSING.
    3. On success: status=COMPLETED, file_path and file_size_bytes populated.
    4. On failure: status=FAILED, error_message populated.
    5. Completed files expire after 24 hours (expires_at).

Example Usage:
    from app.models.export_job import ExportJob, ExportJobStatus

    job = ExportJob(
        organization_id=org.id,
        user_id=user.id,
        format="csv",
        mode="filtered",
        request_params={"filters": {"review_status": ["approved"]}},
        product_count=2500,
    )
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import BaseModel, TimestampMixin


# Default file expiry: 24 hours after job creation
DEFAULT_EXPORT_EXPIRY_HOURS = 24


class ExportJob(BaseModel, TimestampMixin):
    """
    Tracks asynchronous product export jobs.

    When an export request matches more than 1000 products, the API
    creates an ExportJob record and dispatches a Celery task. The client
    polls ``GET /products/export/{id}/status`` until the job completes,
    then downloads via ``GET /products/export/{id}/download``.

    Attributes:
        id: UUID primary key.
        organization_id: Owning organization (data isolation).
        user_id: User who initiated the export.
        status: Current job status (pending/processing/completed/failed).
        format: Requested export format (csv/excel/json).
        mode: Export mode (all/filtered/selected/review_queue).
        request_params: Full serialized ProductExportRequest for replay.
        product_count: Number of products at the time the job was created.
        file_path: Storage path of the completed export file.
        file_size_bytes: Size of the completed export file.
        error_message: Human-readable error description (when failed).
        completed_at: Timestamp when the job finished (success or failure).
        expires_at: Timestamp after which the export file may be deleted.

    Example:
        >>> job = ExportJob(
        ...     organization_id=org.id,
        ...     user_id=user.id,
        ...     format="csv",
        ...     mode="all",
        ...     product_count=2500,
        ... )
    """

    __tablename__ = "export_jobs"

    # Organization ownership for data isolation
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this export job",
    )

    # User who requested the export
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who initiated the export",
    )

    # Job status: pending -> processing -> completed | failed
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Current job status: pending, processing, completed, failed",
    )

    # Export format: csv, excel, json
    format = Column(
        String(10),
        nullable=False,
        comment="Export file format: csv, excel, json",
    )

    # Export mode: all, filtered, selected, review_queue
    mode = Column(
        String(20),
        nullable=False,
        comment="Export mode: all, filtered, selected, review_queue",
    )

    # Full serialized request for Celery task replay
    request_params = Column(
        JSONB,
        nullable=True,
        comment="Serialized ProductExportRequest for task replay",
    )

    # Product count at the time of job creation
    product_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of products to be exported",
    )

    # Completed file metadata
    file_path = Column(
        String(500),
        nullable=True,
        comment="Storage path of the completed export file",
    )
    file_size_bytes = Column(
        Integer,
        nullable=True,
        comment="Size of the completed export file in bytes",
    )

    # Error tracking
    error_message = Column(
        Text,
        nullable=True,
        comment="Error description (only when status=failed)",
    )

    # Timestamps
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the job finished (success or failure)",
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=DEFAULT_EXPORT_EXPIRY_HOURS),
        comment="When the export file may be cleaned up",
    )

    def __repr__(self) -> str:
        """String representation of the export job."""
        return (
            f"<ExportJob(id={self.id}, status={self.status}, "
            f"format={self.format}, products={self.product_count})>"
        )

    @property
    def is_completed(self) -> bool:
        """Check if the export job has completed successfully."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if the export job has failed."""
        return self.status == "failed"

    @property
    def is_expired(self) -> bool:
        """Check if the export file has expired."""
        if self.expires_at is None:
            return False
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now > expires

    @property
    def file_extension(self) -> str:
        """Get the file extension for the export format."""
        extensions = {
            "csv": "csv",
            "excel": "xlsx",
            "json": "json",
        }
        return extensions.get(self.format, self.format)
