"""
Leaflets API Endpoints.

This module provides endpoints for leaflet upload, management,
and processing status tracking.

Example Usage:
    POST /api/v1/leaflets/upload - Upload a new PDF leaflet
    GET /api/v1/leaflets - List all leaflets
    GET /api/v1/leaflets/{id} - Get leaflet details
    GET /api/v1/leaflets/{id}/status - Get processing status
"""

import asyncio
import logging
import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_read, require_write, get_current_organization, get_db
from app.config import settings
from app.models.leaflet import Leaflet, LeafletPage, LeafletStatus, LeafletSourceType
from app.models.organization import Organization
from app.models.user import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.leaflet import (
    LeafletCreate,
    LeafletDetail,
    LeafletListParams,
    LeafletPageResponse,
    LeafletProcessingStatus,
    LeafletQualityMetrics,
    LeafletResponse,
    LeafletUpdate,
    LeafletUploadResponse,
)
from app.utils.exceptions import NotFoundError, ProcessingError, ValidationException

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_date_field(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 date string, handling the trailing Z produced by JS.

    JavaScript's toISOString() produces dates ending with 'Z' (e.g., '2026-03-23T00:00:00.000Z').
    Python 3.10's datetime.fromisoformat() does not accept 'Z' — it requires '+00:00'.
    Also handles date-only strings from HTML date inputs (e.g., '2025-06-15').
    """
    if not value or not value.strip():
        return None
    v = value.strip()
    # Anchor Z substitution to end of string only
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    parsed = datetime.fromisoformat(v)
    # Promote date-only values to midnight UTC datetime
    if not isinstance(parsed, datetime):
        from datetime import date as date_type
        parsed = datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc)
    # Ensure timezone-aware for DateTime(timezone=True) columns
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def generate_leaflet_id() -> str:
    """Generate a unique leaflet ID."""
    import secrets
    year = datetime.utcnow().strftime("%Y")
    random_part = secrets.token_hex(3).upper()
    return f"LEAF_{year}_{random_part}"


# Allowed MIME types for upload
ALLOWED_PDF_TYPES = ["application/pdf", "application/x-pdf"]
ALLOWED_ZIP_TYPES = ["application/zip", "application/x-zip-compressed", "application/x-zip", "application/octet-stream"]


@router.post(
    "/upload",
    response_model=LeafletUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF or ZIP leaflet",
    description="Upload a new PDF leaflet or ZIP file containing page images for processing.",
)
async def upload_leaflet(
    file: UploadFile = File(..., description="PDF or ZIP file to upload"),
    retailer: Optional[str] = Form(None, description="Retailer name"),
    country: Optional[str] = Form(None, description="Country code (ISO 3166-1)"),
    language: Optional[str] = Form(None, description="Language code (ISO 639-1)"),
    currency: Optional[str] = Form(None, description="Currency code (ISO 4217)"),
    valid_from: Optional[str] = Form(None, description="Validity start date (ISO 8601)"),
    valid_until: Optional[str] = Form(None, description="Validity end date (ISO 8601)"),
    auto_process: bool = Form(True, description="Automatically start processing"),
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Upload a PDF leaflet or ZIP file containing page images for processing.

    The file will be validated, stored, and queued for processing.
    Supported formats:
    - PDF files (with .pdf extension)
    - ZIP files containing images (with .zip extension)

    Args:
        file: PDF or ZIP file to upload
        retailer: Optional retailer name
        country: Optional country code
        language: Optional language code
        currency: Optional currency code
        auto_process: Whether to automatically start processing
        current_user: Currently authenticated user
        db: Database session

    Returns:
        Upload response with leaflet ID

    Raises:
        ValidationException: If file is invalid
    """
    from app.services.leaflet_service import LeafletService

    filename_lower = file.filename.lower()
    is_pdf = filename_lower.endswith(".pdf")
    is_zip = filename_lower.endswith(".zip")

    # Validate file extension
    if not is_pdf and not is_zip:
        raise ValidationException([
            {"field": "file", "message": "File must be a PDF or ZIP archive"}
        ])

    # Validate content type
    if is_pdf and file.content_type not in ALLOWED_PDF_TYPES:
        raise ValidationException([
            {"field": "file", "message": "Invalid file type. Must be PDF."}
        ])
    if is_zip and file.content_type not in ALLOWED_ZIP_TYPES:
        raise ValidationException([
            {"field": "file", "message": "Invalid file type. Must be ZIP."}
        ])

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > settings.max_file_size:
        max_mb = settings.max_file_size / (1024 * 1024)
        raise ValidationException([
            {"field": "file", "message": f"File too large. Maximum size is {max_mb}MB"}
        ])

    # Validate minimum size (avoid empty files)
    if len(content) < 1000:
        raise ValidationException([
            {"field": "file", "message": "File appears to be empty or corrupt"}
        ])

    # Validate file magic bytes
    if is_pdf and not content.startswith(b'%PDF'):
        raise ValidationException([
            {"field": "file", "message": "Invalid PDF file format"}
        ])
    if is_zip and not content.startswith(b'PK\x03\x04'):
        raise ValidationException([
            {"field": "file", "message": "Invalid ZIP file format"}
        ])
    
    # Parse optional date fields
    try:
        parsed_valid_from = _parse_date_field(valid_from)
    except ValueError:
        raise ValidationException([{"field": "valid_from", "message": f"Invalid date format for valid_from: {valid_from}"}])
    try:
        parsed_valid_until = _parse_date_field(valid_until)
    except ValueError:
        raise ValidationException([{"field": "valid_until", "message": f"Invalid date format for valid_until: {valid_until}"}])

    # Use service to create leaflet
    service = LeafletService(db)

    try:
        leaflet = await service.create_leaflet(
            file_content=content,
            filename=file.filename,
            user_id=current_user.id,
            organization_id=current_org.id,
            retailer=retailer,
            country=country,
            language=language,
            currency=currency,
            valid_from=parsed_valid_from,
            valid_until=parsed_valid_until,
        )
    except Exception as e:
        logger.error(f"Failed to create leaflet: {e}")
        raise ValidationException([
            {"field": "file", "message": str(e)}
        ])

    # Check if this is an existing leaflet (duplicate file)
    # The service sets _is_duplicate flag when returning an existing leaflet
    is_existing = getattr(leaflet, '_is_duplicate', False)

    if is_existing:
        logger.info(f"Duplicate file detected: {leaflet.leaflet_id} by user {current_user.email}")
        return {
            "leaflet_id": leaflet.leaflet_id,
            "message": f"This file was previously uploaded. You can view it or reprocess it from the leaflet page.",
            "status": leaflet.status,
            "is_existing": True,
        }

    logger.info(f"Leaflet uploaded: {leaflet.leaflet_id} by user {current_user.email}")

    # Automatically start processing if requested
    if auto_process:
        try:
            await service.start_processing(leaflet.leaflet_id)
            status_value = LeafletStatus.PROCESSING
            message = "Leaflet uploaded and processing started."
        except Exception as e:
            logger.warning(f"Failed to start processing: {e}")
            status_value = LeafletStatus.PENDING
            message = "Leaflet uploaded. Processing will begin shortly."
    else:
        status_value = LeafletStatus.PENDING
        message = "Leaflet uploaded successfully. Use /reprocess to start processing."

    return {
        "leaflet_id": leaflet.leaflet_id,
        "message": message,
        "status": status_value,
        "is_existing": False,
    }


# Allowed image MIME types for multi-image upload
ALLOWED_IMAGE_TYPES = [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/tiff",
    "image/gif",
    "image/bmp",
]


@router.post(
    "/upload/images",
    response_model=LeafletUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple images as a leaflet",
    description="Upload multiple image files to create a single leaflet. Each image becomes a page.",
)
async def upload_images_as_leaflet(
    files: List[UploadFile] = File(..., description="Image files in page order"),
    retailer: Optional[str] = Form(None, description="Retailer name"),
    country: Optional[str] = Form(None, description="Country code (ISO 3166-1)"),
    language: Optional[str] = Form(None, description="Language code (ISO 639-1)"),
    currency: Optional[str] = Form(None, description="Currency code (ISO 4217)"),
    auto_process: bool = Form(True, description="Automatically start processing"),
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Upload multiple images as a single leaflet.

    Each image becomes a page in the leaflet, ordered by upload sequence.
    Supported formats: JPEG, PNG, WEBP, TIFF, GIF, BMP

    Args:
        files: Image files to upload (1-100 files, max 20MB each)
        retailer: Optional retailer name
        country: Optional country code
        language: Optional language code
        currency: Optional currency code
        auto_process: Whether to automatically start processing
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Upload response with leaflet ID

    Raises:
        ValidationException: If images are invalid
    """
    from app.services.leaflet_service import LeafletService

    # Validate file count
    if not files:
        raise ValidationException([
            {"field": "files", "message": "At least one image file is required"}
        ])

    if len(files) > 100:
        raise ValidationException([
            {"field": "files", "message": f"Too many files ({len(files)}). Maximum is 100 images."}
        ])

    # Validate and read all files
    images = []
    total_size = 0
    max_image_size = 20 * 1024 * 1024  # 20MB per image
    max_total_size = 200 * 1024 * 1024  # 200MB total

    for i, file in enumerate(files):
        # Validate file type by extension
        filename_lower = file.filename.lower() if file.filename else ""
        valid_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.gif', '.bmp')

        if not filename_lower.endswith(valid_extensions):
            raise ValidationException([
                {"field": "files", "message": f"File {i+1} ({file.filename}): Unsupported format. Use JPG, PNG, WEBP, TIFF, GIF, or BMP."}
            ])

        # Read content
        content = await file.read()

        # Validate size
        if len(content) > max_image_size:
            raise ValidationException([
                {"field": "files", "message": f"File {i+1} ({file.filename}): Too large ({len(content) / (1024*1024):.1f}MB). Maximum is 20MB per image."}
            ])

        if len(content) < 1000:
            raise ValidationException([
                {"field": "files", "message": f"File {i+1} ({file.filename}): File appears to be empty or corrupt."}
            ])

        total_size += len(content)
        if total_size > max_total_size:
            raise ValidationException([
                {"field": "files", "message": f"Total upload size exceeds 200MB limit."}
            ])

        images.append((content, file.filename or f"image_{i+1}.jpg"))

    # Use service to create leaflet from images
    service = LeafletService(db)

    try:
        leaflet = await service.create_leaflet_from_images(
            images=images,
            user_id=current_user.id,
            organization_id=current_org.id,
            retailer=retailer,
            country=country,
            language=language,
            currency=currency,
        )
    except Exception as e:
        logger.error(f"Failed to create leaflet from images: {e}")
        raise ValidationException([
            {"field": "files", "message": str(e)}
        ])

    logger.info(f"Leaflet created from {len(images)} images: {leaflet.leaflet_id} by user {current_user.email}")

    # Automatically start processing if requested
    if auto_process:
        try:
            await service.start_image_processing(leaflet.leaflet_id)
            status_value = LeafletStatus.EXTRACTING
            message = f"Leaflet created from {len(images)} images. Extraction started."
        except Exception as e:
            logger.warning(f"Failed to start processing: {e}")
            status_value = LeafletStatus.PENDING
            message = f"Leaflet created from {len(images)} images. Processing will begin shortly."
    else:
        status_value = LeafletStatus.PENDING
        message = f"Leaflet created from {len(images)} images successfully."

    return {
        "leaflet_id": leaflet.leaflet_id,
        "message": message,
        "status": status_value,
        "is_existing": False,
    }


@router.post(
    "/prepare-upload",
    status_code=status.HTTP_200_OK,
    summary="Prepare direct upload to storage",
    description="Get a presigned URL for direct file upload to S3/storage.",
)
async def prepare_upload(
    filename: str = Form(..., description="Original filename"),
    file_size: int = Form(..., description="File size in bytes"),
    retailer: Optional[str] = Form(None, description="Retailer name"),
    country: Optional[str] = Form(None, description="Country code (ISO 3166-1)"),
    language: Optional[str] = Form(None, description="Language code (ISO 639-1)"),
    currency: Optional[str] = Form(None, description="Currency code (ISO 4217)"),
    valid_from: Optional[str] = Form(None, description="Validity start date (ISO 8601)"),
    valid_until: Optional[str] = Form(None, description="Validity end date (ISO 8601)"),
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Prepare for direct upload to storage.

    Returns a presigned URL that allows the client to upload directly to S3,
    bypassing the backend for faster uploads.

    Flow:
    1. Client calls this endpoint with file metadata
    2. Backend returns presigned URL and leaflet_id
    3. Client uploads file directly to S3 using presigned URL
    4. Client calls /confirm-upload to finalize

    Returns:
        Presigned URL data and leaflet_id for confirmation
    """
    from app.utils.storage import get_storage_backend, generate_storage_path

    filename_lower = filename.lower()
    is_pdf = filename_lower.endswith(".pdf")
    is_zip = filename_lower.endswith(".zip")

    # Validate filename
    if not is_pdf and not is_zip:
        raise ValidationException([
            {"field": "filename", "message": "File must be a PDF or ZIP"}
        ])

    # Validate file size
    if file_size > settings.max_file_size:
        max_mb = settings.max_file_size / (1024 * 1024)
        raise ValidationException([
            {"field": "file_size", "message": f"File too large. Maximum size is {max_mb}MB"}
        ])

    if file_size < 1000:
        raise ValidationException([
            {"field": "file_size", "message": "File appears to be too small"}
        ])

    # Parse optional date fields (fail fast before allocating resources)
    try:
        parsed_valid_from = _parse_date_field(valid_from)
    except ValueError:
        raise ValidationException([{"field": "valid_from", "message": f"Invalid date format for valid_from: {valid_from}"}])
    try:
        parsed_valid_until = _parse_date_field(valid_until)
    except ValueError:
        raise ValidationException([{"field": "valid_until", "message": f"Invalid date format for valid_until: {valid_until}"}])

    # Determine file type specifics
    if is_pdf:
        source_type = LeafletSourceType.PDF
        mime_type = "application/pdf"
        source_filename = "original.pdf"
    else:
        source_type = LeafletSourceType.IMAGES
        mime_type = "application/zip"
        source_filename = "original.zip"

    # Generate leaflet ID
    leaflet_id = generate_leaflet_id()

    # Ensure unique ID
    while True:
        existing = await db.execute(
            select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
        )
        if not existing.scalar_one_or_none():
            break
        leaflet_id = generate_leaflet_id()

    # Generate storage path
    source_path = generate_storage_path(leaflet_id, source_filename, "source")

    # Get presigned upload URL
    storage = get_storage_backend()
    presigned_data = await storage.generate_presigned_upload_url(
        file_path=source_path,
        content_type=mime_type,
        expires_in=3600,  # 1 hour
    )

    # Create pending leaflet record
    leaflet = Leaflet(
        leaflet_id=leaflet_id,
        user_id=current_user.id,
        organization_id=current_org.id,
        filename=filename,
        file_size=file_size,
        mime_type=mime_type,
        source_type=source_type,
        status=LeafletStatus.PENDING,
        current_step="awaiting_upload",
        retailer=retailer,
        country=country,
        language=language,
        currency=currency,
        valid_from=parsed_valid_from,
        valid_until=parsed_valid_until,
        source_path=source_path,
        storage_bucket=settings.s3_bucket_name if settings.storage_mode != "local" else None,
    )

    db.add(leaflet)
    await db.commit()

    logger.info(f"Prepared upload for leaflet {leaflet_id} by user {current_user.email}")

    return {
        "leaflet_id": leaflet_id,
        "upload_url": presigned_data["url"],
        "upload_fields": presigned_data["fields"],
        "upload_method": presigned_data.get("method", "POST"),
        "storage_path": source_path,
        "expires_in": 3600,
    }


@router.post(
    "/confirm-upload/{leaflet_id}",
    status_code=status.HTTP_200_OK,
    summary="Confirm direct upload completed",
    description="Confirm that direct upload to S3 is complete and start processing.",
)
async def confirm_upload(
    leaflet_id: str,
    auto_process: bool = Form(True, description="Automatically start processing"),
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Confirm that direct upload is complete and optionally start processing.

    Call this after successfully uploading the file to the presigned URL.
    This endpoint verifies the file exists and kicks off background processing.
    """
    from app.utils.storage import get_storage_backend

    # Get leaflet
    result = await db.execute(
        select(Leaflet).where(
            Leaflet.leaflet_id == leaflet_id,
            Leaflet.organization_id == current_org.id,
        )
    )
    leaflet = result.scalar_one_or_none()

    if not leaflet:
        raise NotFoundError("Leaflet", leaflet_id)

    # Verify file was uploaded
    storage = get_storage_backend()
    if not await storage.file_exists(leaflet.source_path):
        raise ValidationException([
            {"field": "file", "message": "File not found in storage. Upload may have failed."}
        ])

    # Update leaflet status
    leaflet.current_step = "uploaded"

    if auto_process:
        # Queue for processing - route to correct task based on source type
        from app.workers.tasks import process_pdf_task, process_zip_task
        from app.models.leaflet import LeafletSourceType

        leaflet.status = LeafletStatus.PROCESSING
        leaflet.current_step = "queued"
        leaflet.progress = 0.0
        await db.commit()

        # Route to appropriate task based on source type
        if leaflet.source_type == LeafletSourceType.IMAGES:
            task_result = process_zip_task.apply_async(
                args=[leaflet_id],
                queue="pdf",
            )
            logger.info(f"Confirmed ZIP upload and queued processing for {leaflet_id}, task_id: {task_result.id}")
        else:
            task_result = process_pdf_task.apply_async(
                args=[leaflet_id],
                queue="pdf",
            )
            logger.info(f"Confirmed PDF upload and queued processing for {leaflet_id}, task_id: {task_result.id}")

        return {
            "leaflet_id": leaflet_id,
            "status": LeafletStatus.PROCESSING,
            "message": "Upload confirmed and processing started.",
        }
    else:
        await db.commit()

        return {
            "leaflet_id": leaflet_id,
            "status": LeafletStatus.PENDING,
            "message": "Upload confirmed. Use /reprocess to start processing.",
        }


@router.post(
    "/upload/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk upload PDF leaflets",
    description="Upload multiple PDF leaflets for processing.",
)
async def bulk_upload_leaflets(
    files: List[UploadFile] = File(..., description="PDF files to upload"),
    retailer: Optional[str] = Form(None, description="Retailer name (applied to all)"),
    country: Optional[str] = Form(None, description="Country code (applied to all)"),
    language: Optional[str] = Form(None, description="Language code (applied to all)"),
    currency: Optional[str] = Form(None, description="Currency code (applied to all)"),
    valid_from: Optional[str] = Form(None, description="Validity start date (ISO 8601, applied to all)"),
    valid_until: Optional[str] = Form(None, description="Validity end date (ISO 8601, applied to all)"),
    auto_process: bool = Form(True, description="Automatically start processing"),
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Upload multiple PDF leaflets for processing.

    Processes up to 20 files in a single request. Each file is validated
    and queued separately, allowing partial success.

    Args:
        files: List of PDF files to upload (max 20)
        retailer: Optional retailer name (applied to all files)
        country: Optional country code (applied to all files)
        language: Optional language code (applied to all files)
        currency: Optional currency code (applied to all files)
        valid_from: Optional validity start date (applied to all files)
        valid_until: Optional validity end date (applied to all files)
        auto_process: Whether to automatically start processing
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Upload results for each file
        
    Raises:
        ValidationException: If no valid files provided
    """
    from app.services.leaflet_service import LeafletService
    
    MAX_FILES = 20
    
    if len(files) > MAX_FILES:
        raise ValidationException([
            {"field": "files", "message": f"Maximum {MAX_FILES} files per request"}
        ])
    
    if len(files) == 0:
        raise ValidationException([
            {"field": "files", "message": "At least one file is required"}
        ])
    
    # Parse optional date fields
    try:
        parsed_valid_from = _parse_date_field(valid_from)
    except ValueError:
        raise ValidationException([{"field": "valid_from", "message": f"Invalid date format for valid_from: {valid_from}"}])
    try:
        parsed_valid_until = _parse_date_field(valid_until)
    except ValueError:
        raise ValidationException([{"field": "valid_until", "message": f"Invalid date format for valid_until: {valid_until}"}])

    service = LeafletService(db)
    results = []
    successful = 0
    failed = 0

    for file in files:
        result = {
            "filename": file.filename,
            "success": False,
            "leaflet_id": None,
            "error": None,
            "status": None,
        }
        
        try:
            # Validate file type
            if not file.filename.lower().endswith(".pdf"):
                result["error"] = "File must be a PDF"
                failed += 1
                results.append(result)
                continue
            
            # Validate content type
            if file.content_type not in ["application/pdf", "application/x-pdf"]:
                result["error"] = "Invalid file type. Must be PDF."
                failed += 1
                results.append(result)
                continue
            
            # Read file content
            content = await file.read()
            
            # Validate file size
            if len(content) > settings.max_file_size:
                max_mb = settings.max_file_size / (1024 * 1024)
                result["error"] = f"File too large. Maximum size is {max_mb}MB"
                failed += 1
                results.append(result)
                continue
            
            # Validate minimum size
            if len(content) < 1000:
                result["error"] = "File appears to be empty or corrupt"
                failed += 1
                results.append(result)
                continue
            
            # Validate PDF header
            if not content.startswith(b'%PDF'):
                result["error"] = "Invalid PDF file format"
                failed += 1
                results.append(result)
                continue
            
            # Create leaflet
            leaflet = await service.create_leaflet(
                file_content=content,
                filename=file.filename,
                user_id=current_user.id,
                organization_id=current_org.id,
                retailer=retailer,
                country=country,
                language=language,
                currency=currency,
                valid_from=parsed_valid_from,
                valid_until=parsed_valid_until,
            )
            
            result["leaflet_id"] = leaflet.leaflet_id
            result["success"] = True

            # Check if this is an existing leaflet (duplicate file)
            is_duplicate = getattr(leaflet, '_is_duplicate', False)

            if is_duplicate:
                result["status"] = leaflet.status.value
                result["is_existing"] = True
                result["message"] = "This file was previously uploaded."
                successful += 1
                logger.info(f"Bulk upload duplicate: {leaflet.leaflet_id} ({file.filename}) by user {current_user.email}")
            else:
                # Start processing if requested (only for new uploads)
                if auto_process:
                    try:
                        await service.start_processing(leaflet.leaflet_id)
                        result["status"] = LeafletStatus.PROCESSING.value
                    except Exception as e:
                        logger.warning(f"Failed to start processing for {leaflet.leaflet_id}: {e}")
                        result["status"] = LeafletStatus.PENDING.value
                else:
                    result["status"] = LeafletStatus.PENDING.value

                result["is_existing"] = False
                successful += 1
                logger.info(f"Bulk upload: {leaflet.leaflet_id} ({file.filename}) by user {current_user.email}")

        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            result["error"] = str(e)
            failed += 1

        results.append(result)
    
    return {
        "message": f"Processed {len(files)} files: {successful} successful, {failed} failed",
        "total": len(files),
        "successful": successful,
        "failed": failed,
        "results": results,
    }


@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="List leaflets",
    description="List all leaflets for the current organization.",
)
async def list_leaflets(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[LeafletStatus] = Query(None, description="Filter by status"),
    retailer: Optional[str] = Query(None, description="Filter by retailer"),
    country: Optional[str] = Query(None, description="Filter by country"),
    search: Optional[str] = Query(None, description="Search filename"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List leaflets for the current organization.

    Args:
        page: Page number
        page_size: Items per page
        status: Filter by processing status
        retailer: Filter by retailer name
        country: Filter by country code
        search: Search in filename
        sort_by: Field to sort by
        sort_order: Sort direction
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Paginated list of leaflets
    """
    # Build base query
    # Super users can see all leaflets across all organizations
    if current_user.is_superuser:
        query = select(Leaflet)
        count_query = select(func.count(Leaflet.id))
    else:
        # Regular users see only their organization's leaflets
        query = select(Leaflet).where(Leaflet.organization_id == current_org.id)
        count_query = select(func.count(Leaflet.id)).where(
            Leaflet.organization_id == current_org.id
        )
    
    # Apply filters
    if status:
        query = query.where(Leaflet.status == status)
        count_query = count_query.where(Leaflet.status == status)
    
    if retailer:
        query = query.where(Leaflet.retailer.ilike(f"%{retailer}%"))
        count_query = count_query.where(Leaflet.retailer.ilike(f"%{retailer}%"))
    
    if country:
        query = query.where(Leaflet.country == country.upper())
        count_query = count_query.where(Leaflet.country == country.upper())
    
    if search:
        query = query.where(Leaflet.filename.ilike(f"%{search}%"))
        count_query = count_query.where(Leaflet.filename.ilike(f"%{search}%"))
    
    # Get total count
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Apply sorting
    sort_column = getattr(Leaflet, sort_by, Leaflet.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Execute query
    result = await db.execute(query)
    leaflets = result.scalars().all()

    # Batch-fetch product counts for all leaflets in a single query
    # instead of N+1 sequential COUNT queries.
    from app.models.product import Product

    leaflet_ids = [leaflet.id for leaflet in leaflets]
    if leaflet_ids:
        counts_result = await db.execute(
            select(Product.leaflet_id, func.count(Product.id))
            .where(Product.leaflet_id.in_(leaflet_ids))
            .group_by(Product.leaflet_id)
        )
        product_counts = {row[0]: row[1] for row in counts_result.all()}
    else:
        product_counts = {}

    items = []
    for leaflet in leaflets:
        response = LeafletResponse.model_validate(leaflet)
        response_dict = response.model_dump()
        response_dict["products_count"] = product_counts.get(leaflet.id, 0)
        items.append(response_dict)

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    ).model_dump()


@router.get(
    "/{leaflet_id}",
    response_model=LeafletDetail,
    summary="Get leaflet details",
    description="Get detailed information about a specific leaflet.",
)
async def get_leaflet(
    leaflet_id: str,
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get leaflet details.

    Args:
        leaflet_id: Leaflet ID (human-readable or UUID)
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Leaflet details

    Raises:
        NotFoundError: If leaflet not found
    """
    from app.utils.storage import get_storage_backend

    # Try to find by leaflet_id first, then by UUID
    # Super users can see all leaflets, regular users only their org's
    if current_user.is_superuser:
        query = select(Leaflet)
    else:
        query = select(Leaflet).where(Leaflet.organization_id == current_org.id)
    
    # Check if it's a UUID
    try:
        uuid_id = UUID(leaflet_id)
        query = query.where(Leaflet.id == uuid_id)
    except ValueError:
        # It's a human-readable ID
        query = query.where(Leaflet.leaflet_id == leaflet_id)
    
    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if leaflet is None:
        raise NotFoundError("Leaflet", leaflet_id)

    from app.models.product import Product

    # Fetch pages and product count concurrently
    pages_result, products_count_result = await asyncio.gather(
        db.execute(
            select(LeafletPage)
            .where(LeafletPage.leaflet_id == leaflet.id)
            .order_by(LeafletPage.page_number)
        ),
        db.execute(
            select(func.count(Product.id)).where(Product.leaflet_id == leaflet.id)
        ),
    )
    pages = pages_result.scalars().all()
    products_count = products_count_result.scalar() or 0

    # Generate fresh presigned URLs for page images concurrently.
    # Each presigned URL generation is a lightweight crypto operation
    # (no network call), but using gather keeps the pattern consistent
    # and future-proof if the storage backend ever changes.
    storage = get_storage_backend()

    async def _build_page_data(page: LeafletPage) -> dict:
        """Build page response dict with presigned URLs."""
        page_data = {
            "id": page.id,
            "page_number": page.page_number,
            "width": page.width,
            "height": page.height,
            "products_count": page.products_count,
            "is_processed": page.is_processed,
            "extraction_confidence": page.extraction_confidence,
            "created_at": page.created_at,
            "updated_at": page.updated_at,
            "image_url": None,
            "thumbnail_url": None,
        }

        # Generate presigned URLs
        if page.image_path:
            try:
                page_data["image_url"] = await storage.get_file_url(
                    page.image_path, expires_in=3600
                )
            except Exception as e:
                logger.warning(
                    f"Failed to get image URL for page {page.page_number}: {e}"
                )

        if page.thumbnail_path:
            try:
                page_data["thumbnail_url"] = await storage.get_file_url(
                    page.thumbnail_path, expires_in=3600
                )
            except Exception as e:
                logger.warning(
                    f"Failed to get thumbnail URL for page {page.page_number}: {e}"
                )

        return page_data

    pages_data = await asyncio.gather(*[_build_page_data(p) for p in pages])

    # Convert leaflet to dict and add pages + product count
    leaflet_dict = {
        "id": leaflet.id,
        "leaflet_id": leaflet.leaflet_id,
        "filename": leaflet.filename,
        "file_size": leaflet.file_size,
        "page_count": leaflet.page_count,
        "status": leaflet.status,
        "status_message": leaflet.status_message,
        "progress": leaflet.progress,
        "current_step": leaflet.current_step,
        "retailer": leaflet.retailer,
        "country": leaflet.country,
        "language": leaflet.language,
        "currency": leaflet.currency,
        "overall_confidence": leaflet.overall_confidence,
        "auto_approved_count": leaflet.auto_approved_count,
        "review_required_count": leaflet.review_required_count,
        "products_count": products_count,
        "valid_from": leaflet.valid_from,
        "valid_until": leaflet.valid_until,
        "processing_started_at": leaflet.processing_started_at,
        "processing_completed_at": leaflet.processing_completed_at,
        "processing_metadata": leaflet.processing_metadata,
        "api_tokens_used": leaflet.api_tokens_used,
        "processing_cost": leaflet.processing_cost,
        "created_at": leaflet.created_at,
        "updated_at": leaflet.updated_at,
        "pages": list(pages_data),
    }

    return leaflet_dict


@router.put(
    "/{leaflet_id}",
    response_model=LeafletResponse,
    summary="Update leaflet",
    description="Update leaflet metadata.",
)
async def update_leaflet(
    leaflet_id: str,
    update_data: LeafletUpdate,
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Leaflet:
    """
    Update leaflet metadata.

    Args:
        leaflet_id: Leaflet ID
        update_data: Fields to update
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Updated leaflet

    Raises:
        NotFoundError: If leaflet not found
    """
    # Find leaflet
    if current_user.is_superuser:
        query = select(Leaflet)
    else:
        query = select(Leaflet).where(Leaflet.organization_id == current_org.id)
    
    try:
        uuid_id = UUID(leaflet_id)
        query = query.where(Leaflet.id == uuid_id)
    except ValueError:
        query = query.where(Leaflet.leaflet_id == leaflet_id)
    
    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if leaflet is None:
        raise NotFoundError("Leaflet", leaflet_id)
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(leaflet, field, value)
    
    await db.commit()
    await db.refresh(leaflet)
    
    logger.info(f"Leaflet updated: {leaflet.leaflet_id}")
    
    return leaflet


@router.delete(
    "/{leaflet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete leaflet",
    description="Delete a leaflet and all associated data including storage files.",
)
async def delete_leaflet(
    leaflet_id: str,
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a leaflet and all associated files.

    This removes:
    - The leaflet record and all related database entries (products, pages, reviews)
    - Source PDF file
    - All page images and thumbnails
    - All product images
    - Entire leaflet folder from storage

    Args:
        leaflet_id: Leaflet ID
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Raises:
        NotFoundError: If leaflet not found
    """
    from app.utils.storage import get_storage_backend

    # Find leaflet
    if current_user.is_superuser:
        query = select(Leaflet)
    else:
        query = select(Leaflet).where(Leaflet.organization_id == current_org.id)

    try:
        uuid_id = UUID(leaflet_id)
        query = query.where(Leaflet.id == uuid_id)
    except ValueError:
        query = query.where(Leaflet.leaflet_id == leaflet_id)

    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()

    if leaflet is None:
        raise NotFoundError("Leaflet", leaflet_id)

    # Store leaflet_id for logging before deletion
    leaflet_readable_id = leaflet.leaflet_id

    # Delete local source PDF file if it exists
    import os
    if leaflet.source_path and os.path.exists(leaflet.source_path):
        try:
            os.remove(leaflet.source_path)
            logger.info(f"Deleted source PDF: {leaflet.source_path}")
        except Exception as e:
            logger.warning(f"Failed to delete source PDF {leaflet.source_path}: {e}")

    # Delete all files from cloud storage for this leaflet
    storage = get_storage_backend()
    leaflet_folder = f"leaflets/{leaflet_readable_id}/"
    try:
        deleted_count = await storage.delete_folder(leaflet_folder)
        logger.info(f"Deleted {deleted_count} files from storage folder: {leaflet_folder}")
    except Exception as e:
        logger.warning(f"Failed to delete storage folder {leaflet_folder}: {e}")

    # Delete leaflet record (cascades to products, pages, and reviews via database constraints)
    await db.delete(leaflet)
    await db.commit()

    logger.info(f"Leaflet deleted completely: {leaflet_readable_id} (database and storage)")


@router.get(
    "/{leaflet_id}/status",
    response_model=LeafletProcessingStatus,
    summary="Get processing status",
    description="Get current processing status for a leaflet.",
)
async def get_processing_status(
    leaflet_id: str,
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get leaflet processing status.

    Args:
        leaflet_id: Leaflet ID
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Processing status

    Raises:
        NotFoundError: If leaflet not found
    """
    # Find leaflet
    if current_user.is_superuser:
        query = select(Leaflet)
    else:
        query = select(Leaflet).where(Leaflet.organization_id == current_org.id)
    
    try:
        uuid_id = UUID(leaflet_id)
        query = query.where(Leaflet.id == uuid_id)
    except ValueError:
        query = query.where(Leaflet.leaflet_id == leaflet_id)
    
    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if leaflet is None:
        raise NotFoundError("Leaflet", leaflet_id)
    
    # Get processed pages count
    from app.models.product import Product
    
    pages_processed = await db.execute(
        select(func.count(LeafletPage.id)).where(
            LeafletPage.leaflet_id == leaflet.id,
            LeafletPage.is_processed == True,
        )
    )
    
    products_found = await db.execute(
        select(func.count(Product.id)).where(Product.leaflet_id == leaflet.id)
    )
    
    return {
        "leaflet_id": leaflet.leaflet_id,
        "status": leaflet.status,
        "progress": leaflet.progress,
        "current_step": leaflet.current_step,
        "message": leaflet.status_message,
        "pages_processed": pages_processed.scalar() or 0,
        "products_found": products_found.scalar() or 0,
        "timestamp": datetime.utcnow(),
    }


@router.get(
    "/{leaflet_id}/pages",
    response_model=List[LeafletPageResponse],
    summary="Get leaflet pages",
    description="Get all pages for a leaflet.",
)
async def get_leaflet_pages(
    leaflet_id: str,
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """
    Get leaflet pages.

    Args:
        leaflet_id: Leaflet ID
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        List of pages

    Raises:
        NotFoundError: If leaflet not found
    """
    from app.utils.storage import get_storage_backend

    # Find leaflet
    if current_user.is_superuser:
        query = select(Leaflet)
    else:
        query = select(Leaflet).where(Leaflet.organization_id == current_org.id)
    
    try:
        uuid_id = UUID(leaflet_id)
        query = query.where(Leaflet.id == uuid_id)
    except ValueError:
        query = query.where(Leaflet.leaflet_id == leaflet_id)
    
    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if leaflet is None:
        raise NotFoundError("Leaflet", leaflet_id)
    
    # Get pages
    pages_result = await db.execute(
        select(LeafletPage)
        .where(LeafletPage.leaflet_id == leaflet.id)
        .order_by(LeafletPage.page_number)
    )
    pages = pages_result.scalars().all()
    
    # Generate fresh presigned URLs for each page concurrently
    storage = get_storage_backend()

    async def _build_page_response(page: LeafletPage) -> dict:
        """Build page response dict with presigned URLs."""
        page_data = {
            "id": page.id,
            "page_number": page.page_number,
            "width": page.width,
            "height": page.height,
            "file_size": page.file_size,
            "format": page.format,
            "products_count": page.products_count or 0,
            "is_processed": page.is_processed,
            "extraction_confidence": page.extraction_confidence,
            "created_at": page.created_at,
            "updated_at": page.updated_at,
            "image_url": None,
            "thumbnail_url": None,
        }

        if page.image_path:
            try:
                page_data["image_url"] = await storage.get_file_url(
                    page.image_path, expires_in=3600
                )
            except Exception as e:
                logger.warning(
                    f"Failed to get image URL for page {page.page_number}: {e}"
                )

        if page.thumbnail_path:
            try:
                page_data["thumbnail_url"] = await storage.get_file_url(
                    page.thumbnail_path, expires_in=3600
                )
            except Exception as e:
                logger.warning(
                    f"Failed to get thumbnail URL for page {page.page_number}: {e}"
                )

        return page_data

    pages_response = await asyncio.gather(
        *[_build_page_response(p) for p in pages]
    )

    return list(pages_response)


@router.post(
    "/{leaflet_id}/reprocess",
    response_model=SuccessResponse,
    summary="Reprocess leaflet",
    description="Queue a leaflet for reprocessing.",
)
async def reprocess_leaflet(
    leaflet_id: str,
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Reprocess a leaflet.

    Args:
        leaflet_id: Leaflet ID
        current_user: Currently authenticated user
        current_org: Current organization (enforces tenant scoping)
        db: Database session

    Returns:
        Success message

    Raises:
        NotFoundError: If leaflet not found in the current organization
        ProcessingError: If leaflet is already processing
    """
    from app.services.leaflet_service import LeafletService

    service = LeafletService(db)

    # Org-scoped lookup prevents cross-tenant reprocess
    await service.start_processing(leaflet_id, organization_id=current_org.id)
    
    logger.info(f"Leaflet queued for reprocessing: {leaflet_id}")
    
    return {
        "success": True,
        "message": "Leaflet queued for processing",
        "data": {"leaflet_id": leaflet_id},
    }


@router.post(
    "/{leaflet_id}/extract",
    response_model=SuccessResponse,
    summary="Extract products from leaflet",
    description="Trigger VLM product extraction for a processed leaflet.",
)
async def extract_products(
    leaflet_id: str,
    request: Request,
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Trigger product extraction for a leaflet.

    The leaflet must have completed PDF processing (status: extracting).
    This queues the VLM extraction task.

    Args:
        leaflet_id: Leaflet ID
        request: FastAPI request object (for client IP extraction)
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Success message with task ID

    Raises:
        NotFoundError: If leaflet not found
        ProcessingError: If leaflet not ready for extraction
    """
    from app.workers.tasks import extract_products_task

    # Capture client IP for audit logging
    client_ip = request.client.host if request.client else None

    # Note: VLM provider check is done in the Celery task itself.
    # The task checks both organization-level and platform-level providers,
    # and handles missing providers gracefully with proper status updates.

    # Find leaflet
    if current_user.is_superuser:
        query = select(Leaflet)
    else:
        query = select(Leaflet).where(Leaflet.organization_id == current_org.id)
    
    try:
        uuid_id = UUID(leaflet_id)
        query = query.where(Leaflet.id == uuid_id)
    except ValueError:
        query = query.where(Leaflet.leaflet_id == leaflet_id)
    
    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if leaflet is None:
        raise NotFoundError("Leaflet", leaflet_id)
    
    # Check if ready for extraction
    if leaflet.status not in [LeafletStatus.EXTRACTING, LeafletStatus.VALIDATING]:
        raise ProcessingError(
            f"Leaflet is not ready for extraction. Current status: {leaflet.status.value}"
        )
    
    # Check if pages exist
    pages_count = await db.execute(
        select(func.count(LeafletPage.id)).where(LeafletPage.leaflet_id == leaflet.id)
    )
    if pages_count.scalar() == 0:
        raise ProcessingError("Leaflet has no processed pages")
    
    # Queue extraction task with client IP for audit logging
    task_result = extract_products_task.apply_async(
        args=[leaflet.leaflet_id],
        kwargs={"request_ip": client_ip},
        queue="extraction",
    )

    logger.info(
        f"Extraction queued for {leaflet_id}, task_id: {task_result.id}, client_ip: {client_ip}"
    )
    
    return {
        "success": True,
        "message": "Product extraction queued",
        "data": {
            "leaflet_id": leaflet.leaflet_id,
            "task_id": task_result.id,
        },
    }


@router.post(
    "/{leaflet_id}/extract-images",
    response_model=SuccessResponse,
    summary="Extract product images",
    description="Extract product images from page images using bounding boxes.",
)
async def extract_product_images(
    leaflet_id: str,
    force: bool = Query(False, description="Force re-extraction of all images, even existing ones"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
) -> dict:
    """
    Trigger product image extraction for a leaflet.

    The leaflet must have products extracted (status: reviewing or completed).
    This queues the image extraction task.

    Args:
        leaflet_id: The leaflet to process
        force: If True, clears existing images and re-extracts all

    Returns:
        Task status

    Raises:
        NotFoundError: If leaflet not found
        ProcessingError: If leaflet not ready for image extraction
    """
    from app.workers.tasks import extract_product_images_task
    from app.models.product import Product

    # Get leaflet
    if current_user.is_superuser:
        query = select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
    else:
        query = select(Leaflet).where(
            Leaflet.leaflet_id == leaflet_id,
            Leaflet.organization_id == current_org.id,
        )

    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if not leaflet:
        raise NotFoundError("Leaflet not found")
    
    # Check if ready for image extraction (needs products to exist)
    # Allow any non-processing status - the task will check for products
    invalid_statuses = [LeafletStatus.UPLOADING, LeafletStatus.PROCESSING]
    
    if leaflet.status in invalid_statuses:
        raise ProcessingError(
            f"Leaflet is not ready for image extraction. "
            f"Current status: {leaflet.status.value}. "
            f"Please wait for processing to complete."
        )
    
    # Check if there are products
    products_result = await db.execute(
        select(Product.id).where(Product.leaflet_id == leaflet.id).limit(1)
    )
    if not products_result.scalar_one_or_none():
        raise ProcessingError(
            "No products found for this leaflet. Run product extraction first."
        )
    
    # If force mode, clear existing image data so all products will be re-extracted
    if force:
        clear_result = await db.execute(
            select(Product).where(Product.leaflet_id == leaflet.id)
        )
        products = clear_result.scalars().all()
        images_cleared = 0
        for product in products:
            if product.image_storage_type is not None:
                product.image_storage_type = None
                product.image_base64 = None
                product.image_url = None
                product.image_path = None
                product.image_format = None
                product.image_width = None
                product.image_height = None
                product.image_size_bytes = None
                product.image_quality_score = None
                images_cleared += 1
        await db.commit()
        logger.info(f"Cleared {images_cleared} existing images for re-extraction")
    
    # Queue image extraction task
    task_result = extract_product_images_task.apply_async(
        args=[leaflet_id],
        queue="extraction",
    )
    
    logger.info(f"Queued image extraction for {leaflet_id}, task_id={task_result.id}, force={force}")
    
    return {
        "success": True,
        "message": "Product image extraction queued" + (" (force re-extract)" if force else ""),
        "data": {
            "leaflet_id": leaflet.leaflet_id,
            "task_id": task_result.id,
            "force": force,
        },
    }


@router.delete(
    "/{leaflet_id}/extraction",
    response_model=SuccessResponse,
    summary="Clear extraction data",
    description="Remove all extracted products and images from a leaflet without deleting the PDF.",
)
async def clear_extraction_data(
    leaflet_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
) -> dict:
    """
    Clear all extraction data for a leaflet.

    This removes all extracted products and their images while keeping
    the original PDF and page images. Useful for re-running extraction
    from scratch.

    Args:
        leaflet_id: The leaflet to clear

    Returns:
        Cleanup statistics

    Raises:
        NotFoundError: If leaflet not found
        ProcessingError: If leaflet is currently being processed
    """
    from app.services.leaflet_service import LeafletService

    # Get leaflet to verify ownership and check status
    if current_user.is_superuser:
        query = select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
    else:
        query = select(Leaflet).where(
            Leaflet.leaflet_id == leaflet_id,
            Leaflet.organization_id == current_org.id,
        )

    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if not leaflet:
        raise NotFoundError("Leaflet not found")
    
    # Don't allow clearing while processing or extracting
    if leaflet.status in [LeafletStatus.PROCESSING, LeafletStatus.EXTRACTING]:
        raise ProcessingError(
            f"Cannot clear extraction data while leaflet is being processed. "
            f"Current status: {leaflet.status.value}"
        )
    
    # Perform cleanup
    service = LeafletService(db)
    cleanup_stats = await service.cleanup_extraction_data(
        leaflet_id=leaflet_id,
        user_id=current_user.id,
    )
    
    # Set leaflet status to validating so extraction can be re-triggered
    leaflet.status = LeafletStatus.VALIDATING
    leaflet.current_step = "ready_for_extraction"
    leaflet.status_message = "Extraction data cleared. Ready for re-extraction."
    leaflet.progress = 0.30
    await db.commit()
    
    logger.info(
        f"Cleared extraction data for {leaflet_id}: "
        f"{cleanup_stats['products_deleted']} products, "
        f"{cleanup_stats['storage_files_deleted']} files deleted"
    )
    
    return {
        "success": True,
        "message": "Extraction data cleared successfully",
        "data": {
            "leaflet_id": leaflet_id,
            "products_deleted": cleanup_stats["products_deleted"],
            "reviews_deleted": cleanup_stats["reviews_deleted"],
            "storage_files_deleted": cleanup_stats["storage_files_deleted"],
        },
    }


@router.get(
    "/debug/celery-status",
    summary="Check Celery status",
    description="Debug endpoint to check Celery worker status.",
    include_in_schema=False,
)
async def check_celery_status() -> dict:
    """
    Debug endpoint to check if Celery is working.
    
    Returns:
        Celery status information
    """
    from app.workers.celery_app import celery_app
    
    try:
        # Try to ping the Celery workers
        inspect = celery_app.control.inspect()
        
        # Get active workers
        active_workers = inspect.active()
        registered_tasks = inspect.registered()
        stats = inspect.stats()
        
        return {
            "success": True,
            "celery_status": "connected",
            "active_workers": active_workers,
            "registered_tasks": registered_tasks,
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Celery status check failed: {e}")
        return {
            "success": False,
            "celery_status": "error",
            "error": str(e),
        }


@router.post(
    "/debug/trigger-process/{leaflet_id}",
    summary="Manually trigger processing",
    description="Debug endpoint to manually trigger PDF/ZIP processing.",
    include_in_schema=False,
)
async def trigger_process(
    leaflet_id: str,
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Debug endpoint to manually trigger processing.
    Routes to correct task based on source type.
    """
    from app.workers.tasks import process_pdf_task, process_zip_task
    from app.models.leaflet import LeafletSourceType

    # Check leaflet exists
    if current_user.is_superuser:
        query = select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
    else:
        query = select(Leaflet).where(
            Leaflet.leaflet_id == leaflet_id,
            Leaflet.organization_id == current_org.id,
        )

    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()

    if leaflet is None:
        raise NotFoundError("Leaflet", leaflet_id)

    # Trigger task with explicit queue - route based on source type
    try:
        if leaflet.source_type == LeafletSourceType.IMAGES:
            task_result = process_zip_task.apply_async(
                args=[leaflet_id],
                queue="pdf",
            )
            task_type = "ZIP"
        else:
            task_result = process_pdf_task.apply_async(
                args=[leaflet_id],
                queue="pdf",
            )
            task_type = "PDF"

        logger.info(f"Manually triggered {task_type} processing for {leaflet_id}, task_id: {task_result.id}")

        return {
            "success": True,
            "message": f"{task_type} task queued successfully",
            "task_id": task_result.id,
            "leaflet_id": leaflet_id,
            "queue": "pdf",
            "source_type": leaflet.source_type.value if leaflet.source_type else "pdf",
        }
    except Exception as e:
        logger.error(f"Failed to queue task: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.get(
    "/debug/page-urls/{leaflet_id}",
    summary="Debug page URLs",
    description="Debug endpoint to check page URLs.",
    include_in_schema=False,
)
async def debug_page_urls(
    leaflet_id: str,
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Debug endpoint to check what URLs are stored and generated for pages.
    """
    from app.utils.storage import get_storage_backend

    # Get leaflet
    if current_user.is_superuser:
        query = select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
    else:
        query = select(Leaflet).where(
            Leaflet.leaflet_id == leaflet_id,
            Leaflet.organization_id == current_org.id,
        )

    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if leaflet is None:
        raise NotFoundError("Leaflet", leaflet_id)
    
    # Get pages
    pages_result = await db.execute(
        select(LeafletPage)
        .where(LeafletPage.leaflet_id == leaflet.id)
        .order_by(LeafletPage.page_number)
    )
    pages = pages_result.scalars().all()
    
    storage = get_storage_backend()
    storage_info = {
        "storage_type": type(storage).__name__,
        "storage_mode": settings.storage_mode,
    }
    
    pages_debug = []
    for page in pages:
        page_info = {
            "page_number": page.page_number,
            "image_path_stored": page.image_path,
            "thumbnail_path_stored": page.thumbnail_path,
            "image_url_stored": page.image_url,
        }
        
        # Try to generate fresh URLs
        if page.thumbnail_path:
            try:
                # Check if file exists
                exists = await storage.file_exists(page.thumbnail_path)
                page_info["thumbnail_exists"] = exists
                
                if exists:
                    fresh_url = await storage.get_file_url(page.thumbnail_path, expires_in=3600)
                    page_info["thumbnail_url_fresh"] = fresh_url
            except Exception as e:
                page_info["thumbnail_error"] = str(e)
        
        if page.image_path:
            try:
                exists = await storage.file_exists(page.image_path)
                page_info["image_exists"] = exists
            except Exception as e:
                page_info["image_error"] = str(e)
        
        pages_debug.append(page_info)
    
    return {
        "leaflet_id": leaflet_id,
        "storage_info": storage_info,
        "pages": pages_debug,
    }


@router.get(
    "/{leaflet_id}/diagnostic",
    summary="Get leaflet diagnostic info",
    description="Get diagnostic information about a leaflet including product counts.",
)
async def get_leaflet_diagnostic(
    leaflet_id: str,
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get diagnostic information about a leaflet.

    Returns:
        Diagnostic info including leaflet status, page count, and product count
    """
    from app.models.product import Product

    # Get leaflet
    if current_user.is_superuser:
        query = select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
    else:
        query = select(Leaflet).where(
            Leaflet.leaflet_id == leaflet_id,
            Leaflet.organization_id == current_org.id
        )

    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if not leaflet:
        raise NotFoundError("Leaflet", leaflet_id)
    
    # Count pages
    pages_result = await db.execute(
        select(func.count(LeafletPage.id)).where(
            LeafletPage.leaflet_id == leaflet.id
        )
    )
    page_count = pages_result.scalar() or 0
    
    # Count products - using leaflet.id (UUID) not leaflet.leaflet_id (string)
    products_result = await db.execute(
        select(func.count(Product.id)).where(
            Product.leaflet_id == leaflet.id
        )
    )
    product_count = products_result.scalar() or 0
    
    # Get sample products if any exist
    sample_products_result = await db.execute(
        select(Product).where(Product.leaflet_id == leaflet.id).limit(3)
    )
    sample_products = sample_products_result.scalars().all()
    
    return {
        "leaflet": {
            "id": str(leaflet.id),
            "leaflet_id": leaflet.leaflet_id,
            "status": leaflet.status.value if leaflet.status else None,
            "current_step": leaflet.current_step,
            "progress": leaflet.progress,
            "page_count_stored": leaflet.page_count,
        },
        "database_counts": {
            "pages_in_db": page_count,
            "products_in_db": product_count,
        },
        "sample_products": [
            {
                "id": str(p.id),
                "product_name": p.product_name,
                "brand": p.brand,
                "review_status": p.review_status.value if p.review_status else None,
            }
            for p in sample_products
        ],
        "user_id": str(current_user.id),
    }


@router.post(
    "/debug/trigger-extraction/{leaflet_id}",
    summary="Manually trigger product extraction",
    description="Debug endpoint to manually trigger product extraction.",
    include_in_schema=False,
)
async def trigger_extraction_debug(
    leaflet_id: str,
    request: Request,
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Debug endpoint to manually trigger product extraction.
    """
    from app.workers.tasks import extract_products_task

    # Capture client IP for audit logging
    client_ip = request.client.host if request.client else None

    # Check leaflet exists
    if current_user.is_superuser:
        query = select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
    else:
        query = select(Leaflet).where(
            Leaflet.leaflet_id == leaflet_id,
            Leaflet.organization_id == current_org.id,
        )

    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if leaflet is None:
        raise NotFoundError("Leaflet", leaflet_id)
    
    # Get page count
    pages_result = await db.execute(
        select(func.count(LeafletPage.id)).where(LeafletPage.leaflet_id == leaflet.id)
    )
    page_count = pages_result.scalar() or 0
    
    if page_count == 0:
        return {
            "success": False,
            "error": "No pages found for leaflet. PDF processing may not have completed.",
            "leaflet_status": leaflet.status.value if leaflet.status else None,
        }
    
    # Trigger extraction task with explicit queue and client IP
    try:
        task_result = extract_products_task.apply_async(
            args=[leaflet_id],
            kwargs={"request_ip": client_ip},
            queue="extraction",
        )

        logger.info(f"Manually triggered extraction for {leaflet_id}, task_id: {task_result.id}, client_ip: {client_ip}")
        
        return {
            "success": True,
            "message": f"Extraction task queued successfully",
            "task_id": task_result.id,
            "leaflet_id": leaflet_id,
            "queue": "extraction",
            "page_count": page_count,
            "current_status": leaflet.status.value if leaflet.status else None,
        }
    except Exception as e:
        logger.error(f"Failed to queue extraction task: {e}")
        return {
            "success": False,
            "error": str(e),
        }