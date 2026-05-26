"""
Product Export Pydantic Schemas.

This module provides request and response schemas for the product-level
export API, which supports exporting products across multiple leaflets
with filtering, selection, and async job support.

Endpoints served:
    POST /api/v1/products/export          - Create export (sync or async)
    POST /api/v1/products/export/preview  - Preview export counts
    GET  /api/v1/products/export/{id}/status   - Check async job status
    GET  /api/v1/products/export/{id}/download - Download completed export

Example Usage:
    from app.schemas.product_export import (
        ProductExportRequest,
        ProductExportPreviewResponse,
    )

    # Export all approved products as CSV
    request = ProductExportRequest(
        format="csv",
        image_storage="url",
        mode="filtered",
        filters=ProductExportFilters(
            review_status=["approved", "auto_approved"],
        ),
    )
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import BaseSchema


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExportFormat(str, Enum):
    """Supported export file formats."""
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"


class ExportImageStorage(str, Enum):
    """How product images are included in the export."""
    URL = "url"
    BASE64 = "base64"
    NONE = "none"


class ExportMode(str, Enum):
    """
    Determines which products are included in the export.

    Attributes:
        ALL: Export all products visible to the organization.
        FILTERED: Export products matching the supplied filter criteria.
        SELECTED: Export an explicit list of product IDs.
        REVIEW_QUEUE: Export products currently in the review queue
                      (pending + needs_correction).
    """
    ALL = "all"
    FILTERED = "filtered"
    SELECTED = "selected"
    REVIEW_QUEUE = "review_queue"


class ExportJobStatus(str, Enum):
    """Status of an asynchronous export job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Nested filter schemas
# ---------------------------------------------------------------------------

class ProductExportFilters(BaseSchema):
    """
    Filter criteria for mode='filtered' exports.

    These fields mirror the query parameters accepted by
    ``GET /api/v1/products`` (see ``products.py:list_products``).

    Attributes:
        search: Free-text search on product_name (case-insensitive ILIKE).
        review_status: One or more review statuses to include.
        leaflet_id: Restrict to products from a specific leaflet
                    (UUID or human-readable ID like LEAF_2025_...).
        category: Exact category name match.
        brand: Case-insensitive brand name match (ILIKE).
        min_confidence: Minimum overall confidence threshold (0.0 - 1.0).
        page_number: Restrict to a specific page within the leaflet.
        validation_passed: Filter by whether validation rules passed.
        sort_by: Column name to sort by (default: created_at).
        sort_order: Sort direction.

    Example:
        >>> filters = ProductExportFilters(
        ...     search="Coca-Cola",
        ...     review_status=["approved", "auto_approved"],
        ...     min_confidence=0.8,
        ... )
    """

    search: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Search product name (case-insensitive)",
    )
    review_status: Optional[List[str]] = Field(
        default=None,
        description=(
            "Filter by review status. Accepted values: pending, "
            "auto_approved, approved, rejected, needs_correction."
        ),
    )
    leaflet_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Filter by leaflet (UUID or human-readable ID)",
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Filter by exact category name",
    )
    brand: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Filter by brand name (case-insensitive)",
    )
    min_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum overall confidence threshold",
    )
    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="Filter by page number within leaflet",
    )
    validation_passed: Optional[bool] = Field(
        default=None,
        description="Filter by validation status",
    )
    sort_by: str = Field(
        default="created_at",
        description="Column name to sort results by",
    )
    sort_order: Literal["asc", "desc"] = Field(
        default="desc",
        description="Sort direction",
    )

    @field_validator("review_status")
    @classmethod
    def validate_review_statuses(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Ensure every supplied status value is a known ReviewStatus."""
        if v is None:
            return v
        allowed = {"pending", "auto_approved", "approved", "rejected", "needs_correction"}
        for status in v:
            if status not in allowed:
                raise ValueError(
                    f"Invalid review_status '{status}'. "
                    f"Must be one of: {', '.join(sorted(allowed))}"
                )
        return v

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        """Restrict sort_by to columns that exist on the Product model."""
        allowed = {
            "created_at", "updated_at", "product_name", "brand",
            "regular_price", "discounted_price", "discount_percentage",
            "confidence", "page_number", "review_status", "review_priority",
            "category",
        }
        if v not in allowed:
            raise ValueError(
                f"Invalid sort_by '{v}'. Must be one of: {', '.join(sorted(allowed))}"
            )
        return v


class ReviewQueueExportFilters(BaseSchema):
    """
    Filter criteria for mode='review_queue' exports.

    Mirrors the query parameters on ``GET /api/v1/products/review-queue``.

    Attributes:
        leaflet_id: Optional leaflet restriction (UUID or human-readable).
    """

    leaflet_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Filter review queue by leaflet (UUID or human-readable ID)",
    )


# ---------------------------------------------------------------------------
# Main request schema
# ---------------------------------------------------------------------------

class ProductExportRequest(BaseSchema):
    """
    Request body for ``POST /api/v1/products/export`` and
    ``POST /api/v1/products/export/preview``.

    The ``mode`` field determines which set of products is exported and
    which companion field (``filters``, ``product_ids``, or
    ``review_queue_filters``) is expected.

    Mutual exclusivity rules enforced by the model validator:
    - mode="all"          -- filters, product_ids, review_queue_filters must all be None
    - mode="filtered"     -- filters is required; product_ids and review_queue_filters must be None
    - mode="selected"     -- product_ids is required; filters and review_queue_filters must be None
    - mode="review_queue" -- review_queue_filters is optional; filters and product_ids must be None

    Attributes:
        format: Export file format (csv, excel, json).
        image_storage: How to include product images (url, base64, none).
        mode: Which products to include in the export.
        filters: Filter criteria (required when mode='filtered').
        product_ids: Explicit product UUIDs (required when mode='selected', max 500).
        review_queue_filters: Optional filters for review queue export.

    Example:
        >>> # Export selected products as Excel with no images
        >>> req = ProductExportRequest(
        ...     format="excel",
        ...     image_storage="none",
        ...     mode="selected",
        ...     product_ids=[uuid1, uuid2, uuid3],
        ... )
    """

    format: ExportFormat = Field(
        default=ExportFormat.CSV,
        description="Export file format",
    )
    image_storage: ExportImageStorage = Field(
        default=ExportImageStorage.URL,
        description="How to include product images in the export",
    )
    mode: ExportMode = Field(
        description="Which products to include in the export",
    )

    # Mode-specific payloads (mutually exclusive)
    filters: Optional[ProductExportFilters] = Field(
        default=None,
        description="Filter criteria (only valid when mode='filtered')",
    )
    product_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Explicit product UUIDs to export (only valid when mode='selected', max 500)",
    )
    review_queue_filters: Optional[ReviewQueueExportFilters] = Field(
        default=None,
        description="Review queue filters (only valid when mode='review_queue')",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("product_ids")
    @classmethod
    def validate_product_ids_length(cls, v: Optional[List[UUID]]) -> Optional[List[UUID]]:
        """Enforce maximum of 500 product IDs and no duplicates."""
        if v is None:
            return v
        if len(v) == 0:
            raise ValueError("product_ids must contain at least 1 ID when provided")
        if len(v) > 500:
            raise ValueError(
                f"Maximum 500 product IDs allowed, got {len(v)}"
            )
        if len(v) != len(set(v)):
            raise ValueError("product_ids must not contain duplicates")
        return v

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "ProductExportRequest":
        """
        Enforce mutual exclusivity between mode and its companion fields.

        Raises:
            ValueError: If the wrong companion fields are provided for the
                        selected mode.
        """
        mode = self.mode

        if mode == ExportMode.ALL:
            if self.filters is not None:
                raise ValueError("'filters' must not be provided when mode='all'")
            if self.product_ids is not None:
                raise ValueError("'product_ids' must not be provided when mode='all'")
            if self.review_queue_filters is not None:
                raise ValueError(
                    "'review_queue_filters' must not be provided when mode='all'"
                )

        elif mode == ExportMode.FILTERED:
            if self.filters is None:
                raise ValueError("'filters' is required when mode='filtered'")
            if self.product_ids is not None:
                raise ValueError(
                    "'product_ids' must not be provided when mode='filtered'"
                )
            if self.review_queue_filters is not None:
                raise ValueError(
                    "'review_queue_filters' must not be provided when mode='filtered'"
                )

        elif mode == ExportMode.SELECTED:
            if self.product_ids is None:
                raise ValueError("'product_ids' is required when mode='selected'")
            if self.filters is not None:
                raise ValueError(
                    "'filters' must not be provided when mode='selected'"
                )
            if self.review_queue_filters is not None:
                raise ValueError(
                    "'review_queue_filters' must not be provided when mode='selected'"
                )

        elif mode == ExportMode.REVIEW_QUEUE:
            if self.filters is not None:
                raise ValueError(
                    "'filters' must not be provided when mode='review_queue'"
                )
            if self.product_ids is not None:
                raise ValueError(
                    "'product_ids' must not be provided when mode='review_queue'"
                )
            # review_queue_filters is optional for this mode

        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Export all products as CSV",
                    "value": {
                        "format": "csv",
                        "image_storage": "url",
                        "mode": "all",
                    },
                },
                {
                    "summary": "Export filtered products as Excel",
                    "value": {
                        "format": "excel",
                        "image_storage": "none",
                        "mode": "filtered",
                        "filters": {
                            "review_status": ["approved", "auto_approved"],
                            "min_confidence": 0.8,
                            "sort_by": "created_at",
                            "sort_order": "desc",
                        },
                    },
                },
                {
                    "summary": "Export selected products as JSON",
                    "value": {
                        "format": "json",
                        "image_storage": "base64",
                        "mode": "selected",
                        "product_ids": [
                            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                            "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                        ],
                    },
                },
                {
                    "summary": "Export review queue for a specific leaflet",
                    "value": {
                        "format": "csv",
                        "image_storage": "url",
                        "mode": "review_queue",
                        "review_queue_filters": {
                            "leaflet_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                        },
                    },
                },
            ]
        }
    }


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ProductExportPreviewResponse(BaseSchema):
    """
    Response for ``POST /api/v1/products/export/preview``.

    Provides a count of products that would be included in the export
    along with an estimated file size, without actually generating the
    export file.

    Attributes:
        product_count: Number of products matching the export criteria.
        leaflet_count: Number of distinct leaflets represented.
        estimated_file_size: Human-readable estimated file size
                            (e.g. "1.2 MB").

    Example:
        >>> response = ProductExportPreviewResponse(
        ...     product_count=347,
        ...     leaflet_count=12,
        ...     estimated_file_size="1.2 MB",
        ... )
    """

    product_count: int = Field(
        ge=0,
        description="Number of products matching the export criteria",
    )
    leaflet_count: int = Field(
        ge=0,
        description="Number of distinct leaflets represented in the export",
    )
    estimated_file_size: str = Field(
        description="Human-readable estimated file size (e.g. '1.2 MB')",
    )


class ProductExportJobResponse(BaseSchema):
    """
    Response for ``POST /api/v1/products/export`` when the export is
    processed asynchronously (1000+ products).

    The client should poll ``GET /api/v1/products/export/{export_id}/status``
    until the job reaches ``completed`` or ``failed``.

    Attributes:
        export_id: Unique identifier for the export job.
        status: Initial job status (always 'pending').
        product_count: Number of products to be exported.
        message: Human-readable status message.

    Example:
        >>> response = ProductExportJobResponse(
        ...     export_id=UUID("..."),
        ...     status=ExportJobStatus.PENDING,
        ...     product_count=2450,
        ...     message="Export job created. Poll status endpoint for progress.",
        ... )
    """

    export_id: UUID = Field(
        description="Unique identifier for the export job",
    )
    status: ExportJobStatus = Field(
        description="Current job status",
    )
    product_count: int = Field(
        ge=0,
        description="Number of products to be exported",
    )
    message: str = Field(
        description="Human-readable status message",
    )


class ProductExportStatusResponse(BaseSchema):
    """
    Response for ``GET /api/v1/products/export/{export_id}/status``.

    Attributes:
        export_id: Unique identifier for the export job.
        status: Current job status.
        product_count: Number of products in the export.
        file_size: Human-readable file size (available when completed).
        download_url: Presigned download URL (available when completed,
                      expires after 1 hour).
        format: Export format that was requested.
        created_at: When the export job was created.
        completed_at: When the export job finished (null if not yet done).
        error_message: Error description (only when status='failed').

    Example:
        >>> response = ProductExportStatusResponse(
        ...     export_id=UUID("..."),
        ...     status=ExportJobStatus.COMPLETED,
        ...     product_count=2450,
        ...     file_size="4.2 MB",
        ...     download_url="https://s3.../exports/...",
        ...     format=ExportFormat.CSV,
        ...     created_at=datetime.utcnow(),
        ...     completed_at=datetime.utcnow(),
        ... )
    """

    export_id: UUID = Field(
        description="Unique identifier for the export job",
    )
    status: ExportJobStatus = Field(
        description="Current job status",
    )
    product_count: int = Field(
        ge=0,
        description="Number of products in the export",
    )
    file_size: Optional[str] = Field(
        default=None,
        description="Human-readable file size (available when completed)",
    )
    download_url: Optional[str] = Field(
        default=None,
        description="Presigned download URL (available when completed, expires after 1 hour)",
    )
    format: ExportFormat = Field(
        description="Export format that was requested",
    )
    created_at: datetime = Field(
        description="When the export job was created",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When the export job completed (null if still processing)",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error description (only populated when status='failed')",
    )
