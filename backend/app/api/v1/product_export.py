"""
Product Export API Endpoints.

This module provides endpoints for exporting product data across multiple
leaflets, with support for filtering, explicit selection, and asynchronous
export jobs for large result sets.

Endpoints:
    POST /api/v1/products/export          - Create product export
    POST /api/v1/products/export/preview  - Preview export counts
    GET  /api/v1/products/export/{id}/status   - Check async job status
    GET  /api/v1/products/export/{id}/download - Download completed export

Design notes:
    - Small exports (<1000 products) are returned as a direct file download
      via StreamingResponse.
    - Large exports (1000+ products) are dispatched as an async Celery task
      and the client polls for completion.
    - All endpoints respect organization-level data isolation: regular users
      only see their own organization's products; superusers see all.
    - Authentication: JWT (Bearer) or API key (X-API-Key).

Example Usage:
    # Export all approved products as CSV
    POST /api/v1/products/export
    {
        "format": "csv",
        "image_storage": "url",
        "mode": "filtered",
        "filters": {
            "review_status": ["approved", "auto_approved"]
        }
    }
"""

import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_export, get_current_organization, get_db
from app.models.export_job import ExportJob
from app.models.leaflet import Leaflet
from app.models.organization import Organization
from app.models.product import Product, ReviewStatus
from app.models.user import User
from app.schemas.product_export import (
    ExportFormat,
    ExportJobStatus,
    ExportMode,
    ProductExportJobResponse,
    ProductExportPreviewResponse,
    ProductExportRequest,
    ProductExportStatusResponse,
)
from app.services.export_service import ExportService
from app.utils.exceptions import APIException, NotFoundError, ValidationException

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Products below this threshold are exported synchronously (direct download).
# Above this threshold, export is dispatched as an async Celery task.
SYNC_EXPORT_THRESHOLD = 1000

# Content-type mapping for export formats
CONTENT_TYPES = {
    ExportFormat.CSV: "text/csv; charset=utf-8",
    ExportFormat.EXCEL: (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    ExportFormat.JSON: "application/json; charset=utf-8",
}

# File extension mapping for export formats
FILE_EXTENSIONS = {
    ExportFormat.CSV: "csv",
    ExportFormat.EXCEL: "xlsx",
    ExportFormat.JSON: "json",
}


# ---------------------------------------------------------------------------
# POST /export/preview  (must be declared BEFORE /export/{export_id}/...)
# ---------------------------------------------------------------------------

@router.post(
    "/export/preview",
    response_model=ProductExportPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview product export",
    description=(
        "Return the number of products and estimated file size for an export "
        "request without actually generating the file. Use this to show a "
        "confirmation dialog in the UI before triggering a potentially large "
        "export."
    ),
)
async def preview_product_export(
    request_body: ProductExportRequest,
    current_user: User = Depends(require_export),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> ProductExportPreviewResponse:
    """
    Count products matching the export criteria and estimate file size.

    This endpoint executes the same query that the export endpoint would use
    but only retrieves aggregate counts (COUNT + COUNT DISTINCT leaflet_id),
    making it fast even for large data sets.

    The estimated file size is a rough approximation based on the product
    count, chosen format, and image_storage setting:
    - CSV without images: ~0.5 KB per product
    - CSV with image URLs: ~0.6 KB per product
    - Excel without images: ~0.7 KB per product
    - JSON without images: ~1.0 KB per product
    - JSON with base64 images: ~50 KB per product

    Args:
        request_body: Export parameters defining mode, filters, and format.
        current_user: Authenticated user (JWT or API key).
        current_org: Active organization context.
        db: Async database session.

    Returns:
        ProductExportPreviewResponse with product_count, leaflet_count,
        and estimated_file_size.
    """
    # Validate selected product_ids belong to this organization
    if request_body.mode == ExportMode.SELECTED and request_body.product_ids:
        await _validate_product_ids_ownership(
            db, request_body.product_ids, current_org.id
        )

    service = ExportService(db)
    product_count, leaflet_count = await service.count_products_for_export(
        request_body, current_org.id
    )

    estimated_size = service.estimate_file_size(
        product_count,
        request_body.format.value,
        request_body.image_storage.value,
    )

    logger.info(
        f"Export preview: {product_count} products across {leaflet_count} leaflets, "
        f"estimated size: {estimated_size}, org_id={current_org.id}"
    )

    return ProductExportPreviewResponse(
        product_count=product_count,
        leaflet_count=leaflet_count,
        estimated_file_size=estimated_size,
    )


# ---------------------------------------------------------------------------
# POST /export  (main export trigger)
# ---------------------------------------------------------------------------

@router.post(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export products",
    description=(
        "Export product data across one or more leaflets.\n\n"
        "**Sync path** (< 1000 products): Returns the file directly as a "
        "streaming download. The response Content-Type will be "
        "`text/csv`, `application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet`, or `application/json` depending on the "
        "requested format.\n\n"
        "**Async path** (>= 1000 products): Returns a "
        "`ProductExportJobResponse` (HTTP 202) with an `export_id`. "
        "Poll `GET /products/export/{export_id}/status` until the job "
        "completes, then download via "
        "`GET /products/export/{export_id}/download`."
    ),
    responses={
        200: {
            "description": (
                "Direct file download (small export). "
                "Content-Type varies by format."
            ),
            "content": {
                "text/csv": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                "application/json": {},
            },
        },
        202: {
            "description": "Async export job created (large export).",
            "model": ProductExportJobResponse,
        },
    },
)
async def export_products(
    request_body: ProductExportRequest,
    current_user: User = Depends(require_export),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """
    Export products matching the specified criteria.

    Workflow:
    1. Build a SQLAlchemy query based on the export mode:
       - ``all``: All products in the organization.
       - ``filtered``: Products matching the supplied filter criteria
         (same filters as ``GET /api/v1/products``).
       - ``selected``: Explicit product IDs (max 500).
       - ``review_queue``: Products with status pending or needs_correction.
    2. Execute a COUNT query to determine export size.
    3. If count < 1000: execute the full query, serialize to the requested
       format, and return a StreamingResponse.
    4. If count >= 1000: enqueue a Celery task, persist an ExportJob record,
       and return an ``ProductExportJobResponse`` with HTTP 202.

    All queries are scoped to the authenticated user's organization
    (superusers can access all organizations).

    The response type depends on export size:
    - Small exports return a ``StreamingResponse`` (binary file).
    - Large exports return a ``ProductExportJobResponse`` (JSON, HTTP 202).

    Args:
        request_body: Export parameters defining mode, format, filters,
                      product_ids, and image_storage preference.
        current_user: Authenticated user (JWT or API key).
        current_org: Active organization context.
        db: Async database session.

    Returns:
        StreamingResponse for small exports, or
        ProductExportJobResponse for large exports (HTTP 202).

    Raises:
        ValidationException: If request body is invalid (handled by Pydantic
                             and the model_validator on ProductExportRequest).
        NotFoundError: If a specified leaflet_id does not exist.
    """
    # Validate selected product_ids belong to this organization
    if request_body.mode == ExportMode.SELECTED and request_body.product_ids:
        await _validate_product_ids_ownership(
            db, request_body.product_ids, current_org.id
        )

    service = ExportService(db)
    product_count, leaflet_count = await service.count_products_for_export(
        request_body, current_org.id
    )

    logger.info(
        f"Export request: {product_count} products, format={request_body.format.value}, "
        f"mode={request_body.mode.value}, org_id={current_org.id}"
    )

    if product_count == 0:
        logger.info(
            f"Export request matched 0 products, returning empty file with headers. "
            f"mode={request_body.mode.value}, org_id={current_org.id}"
        )

    # ---- Sync path: small exports ----
    if product_count < SYNC_EXPORT_THRESHOLD:
        file_buffer = await service.export_products(
            request_body, current_org.id
        )

        content_type = CONTENT_TYPES[request_body.format]
        extension = FILE_EXTENSIONS[request_body.format]
        today = datetime.utcnow().strftime("%Y-%m-%d")
        filename = f"leafxtract-products-{today}.{extension}"

        return StreamingResponse(
            content=file_buffer,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    # ---- Async path: large exports ----

    # Rate-limit: at most 5 concurrent pending/processing exports per user
    pending_count_result = await db.execute(
        select(func.count(ExportJob.id)).where(
            ExportJob.user_id == current_user.id,
            ExportJob.status.in_(["pending", "processing"]),
        )
    )
    pending_count = pending_count_result.scalar() or 0
    if pending_count >= 5:
        raise ValidationException(
            "You have too many pending exports. Please wait for them to "
            "complete before starting a new one."
        )

    # Serialize request for Celery task
    request_data = request_body.model_dump(mode="json")

    # Create ExportJob record
    export_job = ExportJob(
        organization_id=current_org.id,
        user_id=current_user.id,
        status="pending",
        format=request_body.format.value,
        mode=request_body.mode.value,
        request_params=request_data,
        product_count=product_count,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(export_job)
    await db.flush()  # Get the generated ID before commit

    export_job_id = str(export_job.id)

    # Dispatch Celery task
    from app.workers.tasks import export_products_task

    export_products_task.apply_async(
        args=[export_job_id, request_data],
        countdown=1,  # Small delay to ensure DB commit visibility
    )

    logger.info(
        f"Async export job created: {export_job_id}, "
        f"{product_count} products, format={request_body.format.value}"
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=ProductExportJobResponse(
            export_id=export_job.id,
            status=ExportJobStatus.PENDING,
            product_count=product_count,
            message=(
                f"Export job created for {product_count} products. "
                f"Poll the status endpoint for progress."
            ),
        ).model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# GET /export/{export_id}/status
# ---------------------------------------------------------------------------

@router.get(
    "/export/{export_id}/status",
    response_model=ProductExportStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get export job status",
    description=(
        "Check the current status of an asynchronous export job. "
        "Poll this endpoint until `status` is `completed` or `failed`. "
        "When completed, the response includes a presigned `download_url` "
        "that expires after 1 hour."
    ),
)
async def get_export_status(
    export_id: UUID = Path(
        description="Unique identifier of the export job",
    ),
    current_user: User = Depends(require_export),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> ProductExportStatusResponse:
    """
    Retrieve the current status of an async export job.

    The export job must belong to the same organization as the
    authenticated user (or the user must be a superuser).

    Status transitions:
        pending -> processing -> completed
        pending -> processing -> failed

    When status is ``completed``:
    - ``download_url`` contains a presigned S3 URL (expires in 1 hour).
    - ``file_size`` contains the human-readable file size.
    - ``completed_at`` contains the completion timestamp.

    When status is ``failed``:
    - ``error_message`` contains a description of what went wrong.

    Args:
        export_id: UUID of the export job.
        current_user: Authenticated user (JWT or API key).
        current_org: Active organization context.
        db: Async database session.

    Returns:
        ProductExportStatusResponse with current job state.

    Raises:
        NotFoundError: If the export job does not exist or does not
                       belong to the user's organization.
    """
    export_job = await _get_export_job(db, export_id, current_org.id)

    # Check if the export file has expired
    if export_job.is_expired:
        raise APIException(
            message="Export file has expired and has been deleted",
            error_code="EXPORT_EXPIRED",
            status_code=410,
        )

    # Generate download URL if completed
    download_url = None
    file_size = None
    if export_job.status == "completed" and export_job.file_path:
        from app.utils.export_storage import get_export_download_url
        from app.services.export_service import _format_file_size

        try:
            download_url = await get_export_download_url(
                organization_id=current_org.id,
                export_id=str(export_job.id),
                file_format=export_job.file_extension,
            )
        except FileNotFoundError:
            logger.warning(
                f"Export file not found for completed job {export_id}, "
                f"file may have been cleaned up"
            )

        if export_job.file_size_bytes:
            file_size = _format_file_size(export_job.file_size_bytes)

    return ProductExportStatusResponse(
        export_id=export_job.id,
        status=ExportJobStatus(export_job.status),
        product_count=export_job.product_count,
        file_size=file_size,
        download_url=download_url,
        format=ExportFormat(export_job.format),
        created_at=export_job.created_at,
        completed_at=export_job.completed_at,
        error_message=export_job.error_message,
    )


# ---------------------------------------------------------------------------
# GET /export/{export_id}/download
# ---------------------------------------------------------------------------

@router.get(
    "/export/{export_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download completed export",
    description=(
        "Download the file produced by a completed async export job. "
        "This endpoint redirects to a presigned S3 URL or streams the "
        "file directly, depending on storage configuration. "
        "Returns 404 if the job does not exist, 409 if the job has not "
        "completed yet."
    ),
    responses={
        200: {
            "description": "Export file download.",
            "content": {
                "text/csv": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                "application/json": {},
            },
        },
        404: {"description": "Export job not found."},
        409: {"description": "Export job has not completed yet."},
    },
)
async def download_export(
    export_id: UUID = Path(
        description="Unique identifier of the export job",
    ),
    current_user: User = Depends(require_export),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """
    Download the file for a completed export job.

    Behavior:
    - If the job status is ``completed`` and the file exists in S3:
      returns a StreamingResponse with the appropriate Content-Type and
      Content-Disposition headers.
    - If the job status is ``pending`` or ``processing``: raises a
      CONFLICT error (409) indicating the job is not ready.
    - If the job status is ``failed``: raises a CONFLICT error (409)
      with the failure message.
    - If the job does not exist or belongs to another organization:
      raises NOT_FOUND (404).

    The Content-Type is determined by the export format:
    - csv   -> text/csv
    - excel -> application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
    - json  -> application/json

    Args:
        export_id: UUID of the export job.
        current_user: Authenticated user (JWT or API key).
        current_org: Active organization context.
        db: Async database session.

    Returns:
        StreamingResponse with the export file.

    Raises:
        NotFoundError: If the export job does not exist or does not
                       belong to the user's organization.
        APIException (409): If the export job has not completed yet or
                            has failed.
    """
    export_job = await _get_export_job(db, export_id, current_org.id)

    # Check job status
    if export_job.status in ("pending", "processing"):
        raise APIException(
            message=(
                f"Export job is still {export_job.status}. "
                f"Please wait for it to complete."
            ),
            error_code="EXPORT_NOT_READY",
            status_code=409,
        )

    if export_job.status == "failed":
        raise APIException(
            message=f"Export job failed: {export_job.error_message or 'Unknown error'}",
            error_code="EXPORT_FAILED",
            status_code=409,
        )

    if not export_job.file_path:
        raise APIException(
            message="Export file path is missing. The file may have been cleaned up.",
            error_code="EXPORT_FILE_MISSING",
            status_code=409,
        )

    # Download file from storage
    from app.utils.storage import get_storage_backend

    storage = get_storage_backend()

    try:
        file_bytes = await storage.download_file(export_job.file_path)
    except Exception as exc:
        logger.error(
            f"Failed to download export file for job {export_id}: {exc}"
        )
        raise APIException(
            message="Export file could not be retrieved. It may have expired.",
            error_code="EXPORT_FILE_MISSING",
            status_code=409,
        )

    # Determine content type and filename
    export_format = ExportFormat(export_job.format)
    content_type = CONTENT_TYPES[export_format]
    extension = FILE_EXTENSIONS[export_format]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"leafxtract-products-{today}.{extension}"

    return StreamingResponse(
        content=BytesIO(file_bytes),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(file_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_export_job(
    db: AsyncSession,
    export_id: UUID,
    organization_id: UUID,
) -> ExportJob:
    """
    Fetch an ExportJob by ID with organization ownership verification.

    Args:
        db: Async database session.
        export_id: UUID of the export job.
        organization_id: Organization UUID for data isolation.

    Returns:
        ExportJob instance.

    Raises:
        NotFoundError: If the job does not exist or does not belong
                       to the organization.
    """
    result = await db.execute(
        select(ExportJob).where(
            ExportJob.id == export_id,
            ExportJob.organization_id == organization_id,
        )
    )
    export_job = result.scalar_one_or_none()

    if export_job is None:
        raise NotFoundError("ExportJob", str(export_id))

    return export_job


async def _validate_product_ids_ownership(
    db: AsyncSession,
    product_ids: list,
    organization_id: UUID,
) -> None:
    """
    Verify that every product ID belongs to the given organization.

    Args:
        db: Async database session.
        product_ids: List of product UUIDs.
        organization_id: Organization UUID.

    Raises:
        ValidationException: If any product does not belong to the org.
    """
    result = await db.execute(
        select(func.count(Product.id)).where(
            Product.id.in_(product_ids),
            Product.organization_id == organization_id,
        )
    )
    accessible_count = result.scalar()

    if accessible_count != len(product_ids):
        missing_count = len(product_ids) - accessible_count
        raise ValidationException(
            [{
                "field": "product_ids",
                "message": (
                    f"{missing_count} of {len(product_ids)} product IDs "
                    f"do not exist or do not belong to your organization."
                ),
            }],
            message="Some product IDs are invalid or inaccessible",
        )
