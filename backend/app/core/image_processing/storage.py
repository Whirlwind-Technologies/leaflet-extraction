"""
Storage Manager Module.

Handles intelligent storage decisions for product images,
choosing between base64 encoding and file storage based on
image size, use case, and configuration.

Example Usage:
    from app.core.image_processing.storage import StorageManager
    
    manager = StorageManager(bucket_name="leaflet-images")
    result = manager.store_product_image(image, product_id, leaflet_id)
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from urllib.parse import urljoin

from PIL import Image

from app.core.image_processing.encoder import (
    EncodingFormat,
    ImageEncoder,
)

logger = logging.getLogger(__name__)


class StorageType(str, Enum):
    """Storage type for images."""
    BASE64 = "base64"
    FILE = "file"
    CDN = "cdn"


@dataclass
class StorageDecision:
    """
    Decision about how to store an image.
    
    Attributes:
        storage_type: Chosen storage method
        format: Image format to use
        quality: Compression quality
        reason: Reason for the decision
        estimated_size: Estimated storage size
    """
    storage_type: StorageType
    format: EncodingFormat
    quality: int
    reason: str
    estimated_size: int = 0


@dataclass
class StorageResult:
    """
    Result of storing an image.
    
    Attributes:
        success: Whether storage succeeded
        storage_type: How the image was stored
        base64_data: Base64 data (if stored as base64)
        file_url: File URL (if stored as file)
        file_path: Local file path (if applicable)
        format: Image format used
        size_bytes: Actual size in bytes
        width: Image width
        height: Image height
        checksum: MD5 checksum of image data
        error: Error message if failed
    """
    success: bool
    storage_type: Optional[StorageType] = None
    base64_data: Optional[str] = None
    file_url: Optional[str] = None
    file_path: Optional[str] = None
    format: Optional[EncodingFormat] = None
    size_bytes: int = 0
    width: int = 0
    height: int = 0
    checksum: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    error: Optional[str] = None


class StorageManager:
    """
    Manages image storage decisions and operations.
    
    Intelligently chooses between base64 encoding and file storage
    based on image size, use case, and configuration. Supports
    local filesystem and S3-compatible object storage.
    
    Storage Decision Logic:
        - Base64 for images < 100KB (single payload, no extra requests)
        - Base64 for images 100-200KB (medium, still efficient)
        - File storage for images > 200KB (CDN caching, lazy loading)
        
    Attributes:
        base64_threshold: Max bytes for base64 storage
        file_threshold: Min bytes for file storage
        storage_path: Local storage directory
        bucket_name: S3 bucket name (if using S3)
        cdn_url: CDN URL prefix for file URLs
        
    Example:
        >>> manager = StorageManager(bucket_name="leaflet-images")
        >>> result = manager.store_product_image(
        ...     image=pil_image,
        ...     product_id="prod_001",
        ...     leaflet_id="LEAF_2025_001234"
        ... )
        >>> if result.storage_type == StorageType.BASE64:
        ...     print(f"Base64 data: {result.base64_data[:50]}...")
        >>> else:
        ...     print(f"File URL: {result.file_url}")
    """
    
    # Size thresholds (bytes)
    BASE64_THRESHOLD = 100_000  # 100KB
    FILE_THRESHOLD = 200_000    # 200KB
    MAX_IMAGE_SIZE = 5_000_000  # 5MB
    
    def __init__(
        self,
        storage_path: Optional[Union[str, Path]] = None,
        bucket_name: Optional[str] = None,
        cdn_url: Optional[str] = None,
        base64_threshold: int = BASE64_THRESHOLD,
        file_threshold: int = FILE_THRESHOLD,
        s3_client: Optional[Any] = None,
    ):
        """
        Initialize the storage manager.
        
        Args:
            storage_path: Local directory for file storage
            bucket_name: S3 bucket name
            cdn_url: CDN URL prefix
            base64_threshold: Max size for base64 storage
            file_threshold: Min size for file storage
            s3_client: Boto3 S3 client (optional)
        """
        self.storage_path = Path(storage_path) if storage_path else Path("./storage/images")
        self.bucket_name = bucket_name
        self.cdn_url = cdn_url or ""
        self.base64_threshold = base64_threshold
        self.file_threshold = file_threshold
        self.s3_client = s3_client
        self.encoder = ImageEncoder()
        
        # Ensure local storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def decide_storage(
        self,
        image: Image.Image,
        use_case: str = "api",
    ) -> StorageDecision:
        """
        Decide how to store an image.
        
        Args:
            image: PIL Image to store
            use_case: Use case (api, web, mobile, archive)
            
        Returns:
            StorageDecision with recommended storage method
        """
        width, height = image.size
        
        # Estimate compressed size
        estimated_size = self.encoder.estimate_encoded_size(
            image,
            EncodingFormat.JPEG,
            quality=85
        )
        
        # Determine optimal format
        has_transparency = image.mode in ("RGBA", "LA", "P")
        format = EncodingFormat.PNG if has_transparency else EncodingFormat.JPEG
        quality = 90 if format == EncodingFormat.JPEG else 100
        
        # Make decision based on use case and size
        if use_case == "archive":
            # Always use file storage for archival
            return StorageDecision(
                storage_type=StorageType.FILE,
                format=EncodingFormat.PNG,
                quality=100,
                reason="archival_storage",
                estimated_size=estimated_size,
            )
        
        if estimated_size < self.base64_threshold:
            # Small images: base64 is efficient
            return StorageDecision(
                storage_type=StorageType.BASE64,
                format=format,
                quality=quality,
                reason="small_image_efficient_embedding",
                estimated_size=estimated_size,
            )
        
        elif estimated_size < self.file_threshold:
            # Medium images: base64 for single payload
            return StorageDecision(
                storage_type=StorageType.BASE64,
                format=format,
                quality=85,  # Slightly reduce quality
                reason="medium_image_single_payload",
                estimated_size=estimated_size,
            )
        
        else:
            # Large images: file storage with CDN
            return StorageDecision(
                storage_type=StorageType.FILE if not self.cdn_url else StorageType.CDN,
                format=format,
                quality=85,
                reason="large_image_cdn_caching",
                estimated_size=estimated_size,
            )
    
    def store_product_image(
        self,
        image: Image.Image,
        product_id: str,
        leaflet_id: str,
        page_number: int = 1,
        force_storage_type: Optional[StorageType] = None,
    ) -> StorageResult:
        """
        Store a product image using optimal storage method.
        
        Args:
            image: PIL Image to store
            product_id: Product identifier
            leaflet_id: Leaflet identifier
            page_number: Page number in leaflet
            force_storage_type: Force a specific storage type
            
        Returns:
            StorageResult with storage details
        """
        try:
            width, height = image.size
            
            # Decide storage method
            if force_storage_type:
                decision = StorageDecision(
                    storage_type=force_storage_type,
                    format=EncodingFormat.JPEG if force_storage_type == StorageType.FILE else EncodingFormat.PNG,
                    quality=85,
                    reason="forced",
                )
            else:
                decision = self.decide_storage(image)
            
            # Store based on decision
            if decision.storage_type == StorageType.BASE64:
                return self._store_as_base64(
                    image, product_id, leaflet_id, page_number, decision
                )
            else:
                return self._store_as_file(
                    image, product_id, leaflet_id, page_number, decision
                )
                
        except Exception as e:
            logger.error(f"Failed to store product image {product_id}: {e}")
            return StorageResult(
                success=False,
                error=str(e),
            )
    
    def _store_as_base64(
        self,
        image: Image.Image,
        product_id: str,
        leaflet_id: str,
        page_number: int,
        decision: StorageDecision,
    ) -> StorageResult:
        """Store image as base64."""
        result = self.encoder.encode_to_base64(
            image,
            format=decision.format,
            quality=decision.quality,
            include_data_url=False,
        )
        
        if not result.success:
            return StorageResult(
                success=False,
                error=result.error,
            )
        
        # Calculate checksum
        checksum = hashlib.md5(result.data.encode()).hexdigest()
        
        return StorageResult(
            success=True,
            storage_type=StorageType.BASE64,
            base64_data=result.data,
            format=decision.format,
            size_bytes=result.size_bytes,
            width=image.width,
            height=image.height,
            checksum=checksum,
            metadata={
                "product_id": product_id,
                "leaflet_id": leaflet_id,
                "page_number": page_number,
                "quality": decision.quality,
                "reason": decision.reason,
            },
        )
    
    def _store_as_file(
        self,
        image: Image.Image,
        product_id: str,
        leaflet_id: str,
        page_number: int,
        decision: StorageDecision,
    ) -> StorageResult:
        """Store image as file (local or S3)."""
        # Generate filename
        ext = "jpg" if decision.format == EncodingFormat.JPEG else decision.format.value.lower()
        filename = f"{leaflet_id}_page{page_number:02d}_{product_id}.{ext}"
        
        # Encode image
        image_bytes, error = self.encoder.encode_to_bytes(
            image,
            format=decision.format,
            quality=decision.quality,
        )
        
        if error:
            return StorageResult(
                success=False,
                error=error,
            )
        
        # Calculate checksum
        checksum = hashlib.md5(image_bytes).hexdigest()
        
        # Store to S3 or local filesystem
        if self.s3_client and self.bucket_name:
            file_url = self._upload_to_s3(
                image_bytes,
                leaflet_id,
                filename,
                decision.format,
            )
            file_path = None
        else:
            file_path = self._save_to_local(
                image_bytes,
                leaflet_id,
                filename,
            )
            file_url = self._generate_url(leaflet_id, filename)
        
        return StorageResult(
            success=True,
            storage_type=StorageType.CDN if self.cdn_url else StorageType.FILE,
            file_url=file_url,
            file_path=file_path,
            format=decision.format,
            size_bytes=len(image_bytes),
            width=image.width,
            height=image.height,
            checksum=checksum,
            metadata={
                "product_id": product_id,
                "leaflet_id": leaflet_id,
                "page_number": page_number,
                "filename": filename,
                "quality": decision.quality,
                "reason": decision.reason,
            },
        )
    
    def _save_to_local(
        self,
        image_bytes: bytes,
        leaflet_id: str,
        filename: str,
    ) -> str:
        """Save image to local filesystem."""
        # Create leaflet directory
        leaflet_dir = self.storage_path / leaflet_id / "products"
        leaflet_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = leaflet_dir / filename
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        
        logger.debug(f"Saved image to {file_path}")
        return str(file_path)
    
    def _upload_to_s3(
        self,
        image_bytes: bytes,
        leaflet_id: str,
        filename: str,
        format: EncodingFormat,
    ) -> str:
        """Upload image to S3."""
        if not self.s3_client or not self.bucket_name:
            raise ValueError("S3 client and bucket name required")
        
        # Build S3 key
        s3_key = f"leaflets/{leaflet_id}/products/{filename}"
        
        # Determine content type
        content_type = {
            EncodingFormat.JPEG: "image/jpeg",
            EncodingFormat.PNG: "image/png",
            EncodingFormat.WEBP: "image/webp",
        }.get(format, "image/jpeg")
        
        # Upload
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=image_bytes,
            ContentType=content_type,
        )
        
        logger.debug(f"Uploaded image to s3://{self.bucket_name}/{s3_key}")
        
        # Return URL
        if self.cdn_url:
            return urljoin(self.cdn_url, s3_key)
        return f"s3://{self.bucket_name}/{s3_key}"
    
    def _generate_url(self, leaflet_id: str, filename: str) -> str:
        """Generate URL for stored file."""
        if self.cdn_url:
            return urljoin(self.cdn_url, f"leaflets/{leaflet_id}/products/{filename}")
        return f"/storage/images/{leaflet_id}/products/{filename}"
    
    def get_image(
        self,
        storage_result: StorageResult,
    ) -> Tuple[Optional[Image.Image], Optional[str]]:
        """
        Retrieve an image from storage.
        
        Args:
            storage_result: Previous storage result
            
        Returns:
            Tuple of (PIL Image, error_message)
        """
        try:
            if storage_result.storage_type == StorageType.BASE64:
                return self.encoder.decode_from_base64(storage_result.base64_data)
            
            elif storage_result.file_path:
                return Image.open(storage_result.file_path), None
            
            elif storage_result.file_url and self.s3_client:
                # Download from S3
                # Extract key from URL
                s3_key = storage_result.file_url.replace(f"s3://{self.bucket_name}/", "")
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                )
                return Image.open(BytesIO(response["Body"].read())), None
            
            else:
                return None, "Cannot retrieve image: unknown storage location"
                
        except Exception as e:
            return None, str(e)
    
    def delete_image(
        self,
        storage_result: StorageResult,
    ) -> bool:
        """
        Delete an image from storage.
        
        Args:
            storage_result: Storage result with location info
            
        Returns:
            True if deleted successfully
        """
        try:
            if storage_result.storage_type == StorageType.BASE64:
                # Base64 data is typically stored in database, not managed here
                return True
            
            elif storage_result.file_path:
                Path(storage_result.file_path).unlink(missing_ok=True)
                return True
            
            elif storage_result.file_url and self.s3_client:
                s3_key = storage_result.file_url.replace(f"s3://{self.bucket_name}/", "")
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete image: {e}")
            return False