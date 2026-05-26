"""
Leaflet Service Module.

This module contains business logic for leaflet operations,
including upload handling, processing orchestration, and status management.

Example Usage:
    from app.services.leaflet_service import LeafletService

    service = LeafletService(db_session)

    # Upload a new leaflet
    leaflet = await service.create_leaflet(
        file_content=pdf_bytes,
        filename="promo.pdf",
        user_id=user.id,
        organization_id=organization.id,
        retailer="SuperMart",
    )

    # Start processing
    await service.start_processing(leaflet.leaflet_id)
"""

import hashlib
import logging
import secrets
import string
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.leaflet import Leaflet, LeafletPage, LeafletStatus, LeafletSourceType
from app.models.product import Product
from app.utils.storage import (
    get_storage_backend,
    generate_storage_path,
    compute_file_hash,
)
from app.utils.exceptions import (
    DuplicateError,
    NotFoundError,
    ProcessingError,
    ValidationException,
)

logger = logging.getLogger(__name__)


class LeafletService:
    """
    Service class for leaflet operations.
    
    This class encapsulates all business logic related to leaflets,
    providing a clean interface for the API layer.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the leaflet service.
        
        Args:
            db: Async database session
        """
        self.db = db
        self.storage = get_storage_backend()

    @staticmethod
    def generate_leaflet_id() -> str:
        """
        Generate a unique human-readable leaflet ID.
        
        Format: LEAF_YYYY_XXXXXX (e.g., LEAF_2025_A7B3C9)
        
        Returns:
            Unique leaflet identifier
        """
        year = datetime.utcnow().year
        random_part = ''.join(
            secrets.choice(string.ascii_uppercase + string.digits)
            for _ in range(6)
        )
        return f"LEAF_{year}_{random_part}"

    async def create_leaflet(
        self,
        file_content: bytes,
        filename: str,
        user_id: UUID,
        organization_id: UUID,
        retailer: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        currency: Optional[str] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        check_duplicate: bool = True,
    ) -> Leaflet:
        """
        Create a new leaflet from uploaded PDF or ZIP file.

        This method:
        1. Validates the file content (PDF or ZIP)
        2. Checks for duplicates (optional)
        3. Stores the file
        4. Creates the database record

        Args:
            file_content: PDF or ZIP file content as bytes
            filename: Original filename
            user_id: ID of the uploading user
            organization_id: ID of the organization (for multi-tenant data isolation)
            retailer: Optional retailer name
            country: Optional country code
            language: Optional language code
            currency: Optional currency code
            valid_from: Optional validity start date
            valid_until: Optional validity end date
            check_duplicate: Whether to check for duplicate files

        Returns:
            Created Leaflet instance

        Raises:
            ValidationException: If file is invalid
            DuplicateError: If file already exists (when check_duplicate=True)
        """
        # Determine file type
        filename_lower = filename.lower()
        is_pdf = filename_lower.endswith(".pdf")
        is_zip = filename_lower.endswith(".zip")

        if is_pdf:
            source_type = LeafletSourceType.PDF
            mime_type = "application/pdf"
            source_filename = "original.pdf"
            # Validate PDF
            if not file_content.startswith(b'%PDF'):
                raise ValidationException([
                    {"field": "file", "message": "Invalid PDF file"}
                ])
        elif is_zip:
            source_type = LeafletSourceType.IMAGES
            mime_type = "application/zip"
            source_filename = "original.zip"
            # Validate ZIP
            if not file_content.startswith(b'PK\x03\x04'):
                raise ValidationException([
                    {"field": "file", "message": "Invalid ZIP file"}
                ])
        else:
            raise ValidationException([
                {"field": "file", "message": "File must be PDF or ZIP"}
            ])

        # Check file size
        if len(file_content) > settings.max_file_size:
            max_mb = settings.max_file_size / (1024 * 1024)
            raise ValidationException([
                {"field": "file", "message": f"File too large. Maximum is {max_mb}MB"}
            ])

        # Compute file hash
        file_hash = compute_file_hash(file_content)

        # Check for duplicates within organization
        if check_duplicate:
            existing = await self.db.execute(
                select(Leaflet).where(
                    Leaflet.organization_id == organization_id,
                    Leaflet.file_hash == file_hash,
                )
            )
            existing_leaflet = existing.scalar_one_or_none()
            if existing_leaflet:
                # Return existing leaflet with a flag indicating it's a duplicate
                existing_leaflet._is_duplicate = True
                return existing_leaflet

        # Generate leaflet ID
        leaflet_id = self.generate_leaflet_id()

        # Ensure unique ID
        while True:
            existing = await self.db.execute(
                select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
            )
            if not existing.scalar_one_or_none():
                break
            leaflet_id = self.generate_leaflet_id()

        # Store file
        source_path = generate_storage_path(leaflet_id, source_filename, "source")
        await self.storage.upload_file(
            file_content=file_content,
            file_path=source_path,
            content_type=mime_type,
        )

        # Get page count (only for PDF)
        page_count = None
        if is_pdf:
            try:
                from app.core.intake.pdf_processor import get_pdf_processor
                processor = get_pdf_processor()
                page_count = await processor.get_page_count(file_content)
            except Exception as e:
                logger.warning(f"Could not get page count: {e}")
        elif is_zip:
            try:
                from app.core.intake.zip_processor import get_zip_processor
                processor = get_zip_processor()
                page_count = await processor.get_image_count(file_content)
            except Exception as e:
                logger.warning(f"Could not get image count from ZIP: {e}")

        # Create leaflet record
        leaflet = Leaflet(
            leaflet_id=leaflet_id,
            user_id=user_id,
            organization_id=organization_id,
            filename=filename,
            file_size=len(file_content),
            file_hash=file_hash,
            mime_type=mime_type,
            source_type=source_type,
            page_count=page_count,
            status=LeafletStatus.PENDING,
            retailer=retailer,
            country=country,
            language=language,
            currency=currency,
            valid_from=valid_from,
            valid_until=valid_until,
            source_path=source_path,
            storage_bucket=settings.s3_bucket_name if settings.storage_mode != "local" else None,
        )

        self.db.add(leaflet)
        await self.db.commit()
        await self.db.refresh(leaflet)

        logger.info(f"Created leaflet {leaflet_id} for user {user_id}")

        return leaflet

    async def start_processing(
        self,
        leaflet_id: str,
        organization_id: Optional[UUID] = None,
    ) -> bool:
        """
        Start async processing of a leaflet.

        This queues the PDF or ZIP for background processing via Celery.
        Routes to the appropriate task based on source_type.

        Args:
            leaflet_id: The leaflet ID to process
            organization_id: If provided, the leaflet must belong to this
                organization. Used by external endpoints to prevent
                cross-tenant access. Internal callers that just created the
                leaflet may omit this.

        Returns:
            True if processing was started

        Raises:
            NotFoundError: If leaflet not found or not in the given organization
            ProcessingError: If leaflet is already processing
        """
        # Get leaflet (scoped to organization when provided)
        query = select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
        if organization_id is not None:
            query = query.where(Leaflet.organization_id == organization_id)

        result = await self.db.execute(query)
        leaflet = result.scalar_one_or_none()

        if leaflet is None:
            raise NotFoundError("Leaflet", leaflet_id)

        # Check if already processing
        if leaflet.status in [LeafletStatus.PROCESSING, LeafletStatus.EXTRACTING]:
            raise ProcessingError(
                message="Leaflet is already being processed",
                stage="start",
                leaflet_id=leaflet_id,
            )

        # Update status
        leaflet.status = LeafletStatus.PROCESSING
        leaflet.current_step = "queued"
        leaflet.progress = 0.0
        await self.db.commit()

        # Route to appropriate task based on source type
        if leaflet.source_type == LeafletSourceType.IMAGES:
            from app.workers.tasks import process_zip_task
            task_result = process_zip_task.apply_async(
                args=[leaflet_id],
                queue="pdf",  # Use same queue for now
            )
            logger.info(f"Queued leaflet {leaflet_id} (ZIP) for processing, task_id: {task_result.id}")
        else:
            from app.workers.tasks import process_pdf_task
            task_result = process_pdf_task.apply_async(
                args=[leaflet_id],
                queue="pdf",
            )
            logger.info(f"Queued leaflet {leaflet_id} (PDF) for processing, task_id: {task_result.id}")

        return True

    async def get_leaflet(
        self,
        leaflet_id: str,
        user_id: Optional[UUID] = None,
    ) -> Optional[Leaflet]:
        """
        Get a leaflet by ID.
        
        Args:
            leaflet_id: Leaflet ID (human-readable or UUID)
            user_id: Optional user ID for ownership check
            
        Returns:
            Leaflet instance or None
        """
        query = select(Leaflet)

        # Try as UUID first, then as leaflet_id
        try:
            uuid_id = UUID(leaflet_id)
            query = query.where(Leaflet.id == uuid_id)
        except ValueError:
            query = query.where(Leaflet.leaflet_id == leaflet_id)

        if user_id:
            query = query.where(Leaflet.user_id == user_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_leaflet_with_pages(
        self,
        leaflet_id: str,
        user_id: Optional[UUID] = None,
    ) -> Optional[Leaflet]:
        """
        Get a leaflet with its pages.
        
        Args:
            leaflet_id: Leaflet ID
            user_id: Optional user ID for ownership check
            
        Returns:
            Leaflet instance with pages loaded
        """
        from sqlalchemy.orm import selectinload

        query = select(Leaflet).options(selectinload(Leaflet.pages))

        try:
            uuid_id = UUID(leaflet_id)
            query = query.where(Leaflet.id == uuid_id)
        except ValueError:
            query = query.where(Leaflet.leaflet_id == leaflet_id)

        if user_id:
            query = query.where(Leaflet.user_id == user_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_processing_status(self, leaflet_id: str) -> dict:
        """
        Get detailed processing status for a leaflet.
        
        Args:
            leaflet_id: Leaflet ID
            
        Returns:
            Dict with status information
        """
        leaflet = await self.get_leaflet_with_pages(leaflet_id)

        if leaflet is None:
            raise NotFoundError("Leaflet", leaflet_id)

        # Count products
        product_count = await self.db.execute(
            select(func.count(Product.id)).where(Product.leaflet_id == leaflet.id)
        )

        # Count pages processed
        pages_processed = sum(1 for p in leaflet.pages if p.is_processed)

        return {
            "leaflet_id": leaflet.leaflet_id,
            "status": leaflet.status.value,
            "progress": leaflet.progress,
            "current_step": leaflet.current_step,
            "page_count": leaflet.page_count,
            "pages_processed": pages_processed,
            "products_found": product_count.scalar(),
            "processing_started_at": leaflet.processing_started_at,
            "processing_completed_at": leaflet.processing_completed_at,
            "error_message": leaflet.status_message if leaflet.status == LeafletStatus.FAILED else None,
        }

    async def delete_leaflet(
        self,
        leaflet_id: str,
        user_id: UUID,
    ) -> bool:
        """
        Delete a leaflet and all associated data.
        
        Args:
            leaflet_id: Leaflet ID to delete
            user_id: User ID for ownership check
            
        Returns:
            True if deleted
            
        Raises:
            NotFoundError: If leaflet not found
        """
        leaflet = await self.get_leaflet(leaflet_id, user_id)

        if leaflet is None:
            raise NotFoundError("Leaflet", leaflet_id)

        # Delete files from storage
        try:
            prefix = f"leaflets/{leaflet.leaflet_id}/"
            await self.storage.delete_folder(prefix)
        except Exception as e:
            logger.warning(f"Failed to delete storage files: {e}")

        # Delete from database (cascade will handle pages and products)
        await self.db.delete(leaflet)
        await self.db.commit()

        logger.info(f"Deleted leaflet {leaflet_id}")

        return True

    async def list_leaflets(
        self,
        user_id: UUID,
        status: Optional[LeafletStatus] = None,
        retailer: Optional[str] = None,
        country: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Leaflet], int]:
        """
        List leaflets with filtering and pagination.
        
        Args:
            user_id: User ID to filter by
            status: Optional status filter
            retailer: Optional retailer filter
            country: Optional country filter
            search: Optional search term
            page: Page number (1-indexed)
            page_size: Items per page
            sort_by: Field to sort by
            sort_order: Sort direction (asc/desc)
            
        Returns:
            Tuple of (leaflets list, total count)
        """
        query = select(Leaflet).where(Leaflet.user_id == user_id)

        # Apply filters
        if status:
            query = query.where(Leaflet.status == status)
        if retailer:
            query = query.where(Leaflet.retailer.ilike(f"%{retailer}%"))
        if country:
            query = query.where(Leaflet.country == country)
        if search:
            query = query.where(
                Leaflet.filename.ilike(f"%{search}%") |
                Leaflet.leaflet_id.ilike(f"%{search}%") |
                Leaflet.retailer.ilike(f"%{search}%")
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply sorting
        sort_column = getattr(Leaflet, sort_by, Leaflet.created_at)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        leaflets = result.scalars().all()

        return list(leaflets), total

    async def cleanup_extraction_data(
        self,
        leaflet_id: str,
        user_id: Optional[UUID] = None,
    ) -> dict:
        """
        Clean up all extraction data for a leaflet before re-extraction.
        
        This method:
        1. Deletes all product records
        2. Deletes product images from storage
        3. Resets leaflet extraction-related counters
        4. Resets page product counts
        
        This ensures no duplicate data when re-running extraction.
        
        Args:
            leaflet_id: Leaflet ID to clean up
            user_id: Optional user ID for ownership check
            
        Returns:
            Dict with cleanup statistics
            
        Raises:
            NotFoundError: If leaflet not found
        """
        from app.models.product import Product, ProductReview
        
        # Get leaflet
        leaflet = await self.get_leaflet(leaflet_id, user_id)
        if leaflet is None:
            raise NotFoundError("Leaflet", leaflet_id)
        
        logger.info(f"Starting extraction cleanup for leaflet {leaflet_id}")
        
        # Track cleanup stats
        stats = {
            "products_deleted": 0,
            "reviews_deleted": 0,
            "images_deleted": 0,
            "storage_files_deleted": 0,
        }
        
        # Get all products for this leaflet
        products_result = await self.db.execute(
            select(Product).where(Product.leaflet_id == leaflet.id)
        )
        products = products_result.scalars().all()
        
        # Collect image paths to delete from storage
        image_paths_to_delete = []
        for product in products:
            if product.image_path:
                image_paths_to_delete.append(product.image_path)
            if product.image_url and "leaflets/" in product.image_url:
                # Extract path from URL if it's a storage path
                # URL might be presigned, extract the key
                try:
                    if "/" in product.image_url:
                        path_parts = product.image_url.split("leaflets/")
                        if len(path_parts) > 1:
                            # Get path up to any query params
                            path = "leaflets/" + path_parts[1].split("?")[0]
                            image_paths_to_delete.append(path)
                except Exception as e:
                    logger.warning(f"Could not extract image path from URL: {e}")
        
        # Delete product reviews first (due to foreign key)
        for product in products:
            reviews_result = await self.db.execute(
                select(ProductReview).where(ProductReview.product_id == product.id)
            )
            reviews = reviews_result.scalars().all()
            for review in reviews:
                await self.db.delete(review)
                stats["reviews_deleted"] += 1
        
        # Delete products
        for product in products:
            await self.db.delete(product)
            stats["products_deleted"] += 1
        
        # Commit database deletions
        await self.db.commit()
        
        # Delete product images from storage
        for image_path in image_paths_to_delete:
            try:
                if await self.storage.file_exists(image_path):
                    await self.storage.delete_file(image_path)
                    stats["storage_files_deleted"] += 1
            except Exception as e:
                logger.warning(f"Failed to delete image {image_path}: {e}")
        
        # Also delete the entire products folder for this leaflet
        products_folder = f"leaflets/{leaflet.leaflet_id}/products/"
        try:
            deleted_count = await self.storage.delete_folder(products_folder)
            if deleted_count > 0:
                stats["images_deleted"] = deleted_count
                logger.info(f"Deleted products folder: {products_folder}")
        except Exception as e:
            logger.warning(f"Failed to delete products folder: {e}")
        
        # Reset leaflet extraction-related counters
        leaflet.auto_approved_count = 0
        leaflet.review_required_count = 0
        leaflet.overall_confidence = None
        leaflet.api_tokens_used = 0
        leaflet.processing_cost = 0.0
        leaflet.processing_completed_at = None
        
        # Reset processing metadata extraction fields
        if leaflet.processing_metadata:
            # Keep PDF processing data, remove extraction data
            keys_to_remove = [
                "extraction_completed_at",
                "total_products_extracted",
                "auto_approved_count",
                "review_required_count",
                "input_tokens",
                "output_tokens",
                "merged_products",
                "duplicates_removed",
                "parallel_extraction",
            ]
            for key in keys_to_remove:
                leaflet.processing_metadata.pop(key, None)
        
        # Reset page product counts
        pages_result = await self.db.execute(
            select(LeafletPage).where(LeafletPage.leaflet_id == leaflet.id)
        )
        pages = pages_result.scalars().all()
        for page in pages:
            page.products_count = 0
            # Keep is_processed=True since pages are still processed
        
        await self.db.commit()
        await self.db.refresh(leaflet)
        
        logger.info(
            f"Extraction cleanup complete for {leaflet_id}: "
            f"{stats['products_deleted']} products, "
            f"{stats['reviews_deleted']} reviews, "
            f"{stats['storage_files_deleted']} files deleted"
        )
        
        return stats

    async def create_leaflet_from_images(
        self,
        images: list[tuple[bytes, str]],  # List of (content, filename) tuples
        user_id: UUID,
        organization_id: UUID,
        retailer: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Leaflet:
        """
        Create a new leaflet from directly uploaded images.

        This method:
        1. Generates a unique leaflet ID
        2. Processes each image via ImageProcessor
        3. Creates LeafletPage records
        4. Creates the Leaflet record (no source file)

        Args:
            images: List of (image_content, filename) tuples in page order
            user_id: ID of the uploading user
            organization_id: ID of the organization
            retailer: Optional retailer name
            country: Optional country code
            language: Optional language code
            currency: Optional currency code

        Returns:
            Created Leaflet instance

        Raises:
            ValidationException: If no valid images provided
            ProcessingError: If image processing fails
        """
        from app.core.intake.image_processor import get_image_processor

        if not images:
            raise ValidationException([
                {"field": "files", "message": "At least one image is required"}
            ])

        # Generate leaflet ID
        leaflet_id = self.generate_leaflet_id()

        # Ensure unique ID
        while True:
            existing = await self.db.execute(
                select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
            )
            if not existing.scalar_one_or_none():
                break
            leaflet_id = self.generate_leaflet_id()

        # Process images via ImageProcessor
        image_processor = get_image_processor()
        processing_result = await image_processor.process_images(images, leaflet_id)

        if not processing_result.success:
            raise ProcessingError(
                message=processing_result.error_message or "Image processing failed",
                stage="image_processing",
                leaflet_id=leaflet_id,
            )

        if processing_result.page_count == 0:
            raise ValidationException([
                {"field": "files", "message": "No valid images found"}
            ])

        # Calculate total file size from original images
        total_size = sum(len(content) for content, _ in images)

        # Create leaflet record
        leaflet = Leaflet(
            leaflet_id=leaflet_id,
            user_id=user_id,
            organization_id=organization_id,
            filename=f"{leaflet_id}_images.zip",  # Virtual filename
            file_size=total_size,
            file_hash=None,  # No single source file
            mime_type="image/mixed",
            source_type=LeafletSourceType.IMAGES,
            page_count=processing_result.page_count,
            status=LeafletStatus.PENDING,
            retailer=retailer,
            country=country,
            language=language,
            currency=currency,
            source_path=None,  # No source file for direct image upload
            storage_bucket=settings.s3_bucket_name if settings.storage_mode != "local" else None,
        )

        self.db.add(leaflet)
        await self.db.flush()  # Get leaflet.id for LeafletPage records

        # Create LeafletPage records
        for page_result in processing_result.pages:
            leaflet_page = LeafletPage(
                leaflet_id=leaflet.id,
                page_number=page_result.page_number,
                image_path=page_result.image_path,
                thumbnail_path=page_result.thumbnail_path,
                width=page_result.width,
                height=page_result.height,
                is_processed=True,  # Images are already processed
            )
            self.db.add(leaflet_page)

        await self.db.commit()
        await self.db.refresh(leaflet)

        logger.info(
            f"Created leaflet {leaflet_id} from {processing_result.page_count} images "
            f"for user {user_id}"
        )

        return leaflet

    async def start_image_processing(self, leaflet_id: str) -> bool:
        """
        Start extraction processing for an image-based leaflet.

        This is used when images are already uploaded and processed.
        It queues the extraction task directly (skipping PDF/ZIP processing).

        Args:
            leaflet_id: The leaflet ID to process

        Returns:
            True if processing was started

        Raises:
            NotFoundError: If leaflet not found
            ProcessingError: If leaflet is already processing
        """
        # Get leaflet
        result = await self.db.execute(
            select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
        )
        leaflet = result.scalar_one_or_none()

        if leaflet is None:
            raise NotFoundError("Leaflet", leaflet_id)

        # Check if already processing
        if leaflet.status in [LeafletStatus.PROCESSING, LeafletStatus.EXTRACTING]:
            raise ProcessingError(
                message="Leaflet is already being processed",
                stage="start",
                leaflet_id=leaflet_id,
            )

        # Update status directly to EXTRACTING (pages already exist)
        leaflet.status = LeafletStatus.EXTRACTING
        leaflet.current_step = "queued_for_extraction"
        leaflet.progress = 0.1
        await self.db.commit()

        # Queue extraction task directly (skip PDF/ZIP processing)
        from app.workers.tasks import extract_products_task
        task_result = extract_products_task.apply_async(
            args=[leaflet_id],
            queue="extraction",
        )
        logger.info(
            f"Queued leaflet {leaflet_id} (images) for extraction, task_id: {task_result.id}"
        )

        return True

    async def update_leaflet_metadata(
        self,
        leaflet_id: str,
        user_id: UUID,
        retailer: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        currency: Optional[str] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
    ) -> Leaflet:
        """
        Update leaflet metadata.
        
        Args:
            leaflet_id: Leaflet ID to update
            user_id: User ID for ownership check
            retailer: New retailer name
            country: New country code
            language: New language code
            currency: New currency code
            valid_from: Validity start date
            valid_until: Validity end date
            
        Returns:
            Updated Leaflet instance
            
        Raises:
            NotFoundError: If leaflet not found
        """
        leaflet = await self.get_leaflet(leaflet_id, user_id)

        if leaflet is None:
            raise NotFoundError("Leaflet", leaflet_id)

        # Update fields
        if retailer is not None:
            leaflet.retailer = retailer
        if country is not None:
            leaflet.country = country
        if language is not None:
            leaflet.language = language
        if currency is not None:
            leaflet.currency = currency
        if valid_from is not None:
            leaflet.valid_from = valid_from
        if valid_until is not None:
            leaflet.valid_until = valid_until

        await self.db.commit()
        await self.db.refresh(leaflet)

        return leaflet