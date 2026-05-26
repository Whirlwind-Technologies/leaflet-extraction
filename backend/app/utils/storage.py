"""
Storage Utilities Module.

This module provides a unified interface for file storage operations,
supporting local filesystem, AWS S3, and MinIO backends.

Example Usage:
    from app.utils.storage import get_storage_backend
    
    storage = get_storage_backend()
    
    # Upload a file
    url = await storage.upload_file(
        file_content=content,
        file_path="leaflets/LEAF_001/page_01.png"
    )
    
    # Download a file
    content = await storage.download_file("leaflets/LEAF_001/page_01.png")
    
    # Delete a file
    await storage.delete_file("leaflets/LEAF_001/page_01.png")
"""

import asyncio
import hashlib
import logging
import mimetypes
import os
import shutil
from abc import ABC, abstractmethod
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Optional, Union

import aiofiles
import aiofiles.os

from app.config import settings

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def upload_file(
        self,
        file_content: Union[bytes, BinaryIO],
        file_path: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload a file to storage.
        
        Args:
            file_content: File content as bytes or file-like object
            file_path: Destination path in storage
            content_type: Optional MIME type
            
        Returns:
            URL or path to the uploaded file
        """
        pass

    @abstractmethod
    async def download_file(self, file_path: str) -> bytes:
        """
        Download a file from storage.
        
        Args:
            file_path: Path to file in storage
            
        Returns:
            File content as bytes
        """
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            file_path: Path to file in storage
            
        Returns:
            True if deleted successfully
        """
        pass

    @abstractmethod
    async def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            file_path: Path to file in storage
            
        Returns:
            True if file exists
        """
        pass

    @abstractmethod
    async def get_file_url(self, file_path: str, expires_in: int = 3600) -> str:
        """
        Get a URL for accessing the file.
        
        Args:
            file_path: Path to file in storage
            expires_in: URL expiration time in seconds (for signed URLs)
            
        Returns:
            URL to access the file
        """
        pass

    @abstractmethod
    async def list_files(self, prefix: str) -> list[str]:
        """
        List files with a given prefix.
        
        Args:
            prefix: Path prefix to filter files
            
        Returns:
            List of file paths
        """
        pass

    @abstractmethod
    async def delete_folder(self, prefix: str) -> int:
        """
        Delete all files with a given prefix.

        Args:
            prefix: Path prefix for files to delete

        Returns:
            Number of files deleted
        """
        pass

    @abstractmethod
    async def generate_presigned_upload_url(
        self,
        file_path: str,
        content_type: str = "application/pdf",
        expires_in: int = 3600,
    ) -> dict:
        """
        Generate a presigned URL for direct file upload.

        Args:
            file_path: Destination path in storage
            content_type: Expected content type
            expires_in: URL expiration time in seconds

        Returns:
            Dict with 'url' and 'fields' for form-based upload
        """
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize local storage backend.
        
        Args:
            base_path: Base directory for storage
        """
        self.base_path = Path(base_path or settings.local_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized local storage at: {self.base_path}")

    def _get_full_path(self, file_path: str) -> Path:
        """Get full filesystem path for a file."""
        return self.base_path / file_path

    async def upload_file(
        self,
        file_content: Union[bytes, BinaryIO],
        file_path: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file to local storage."""
        full_path = self._get_full_path(file_path)
        
        # Ensure directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get bytes from content
        if isinstance(file_content, bytes):
            data = file_content
        else:
            data = file_content.read()
        
        # Write file asynchronously
        async with aiofiles.open(full_path, 'wb') as f:
            await f.write(data)
        
        logger.debug(f"Uploaded file to local storage: {file_path}")
        return str(full_path)

    async def download_file(self, file_path: str) -> bytes:
        """Download a file from local storage."""
        full_path = self._get_full_path(file_path)
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        async with aiofiles.open(full_path, 'rb') as f:
            content = await f.read()
        
        return content

    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from local storage."""
        full_path = self._get_full_path(file_path)
        
        try:
            if full_path.exists():
                await aiofiles.os.remove(full_path)
                logger.debug(f"Deleted file from local storage: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False

    async def file_exists(self, file_path: str) -> bool:
        """Check if a file exists in local storage."""
        full_path = self._get_full_path(file_path)
        return full_path.exists()

    async def get_file_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Get file path (URL not applicable for local storage)."""
        full_path = self._get_full_path(file_path)
        return str(full_path)

    async def list_files(self, prefix: str) -> list[str]:
        """List files with a given prefix."""
        base = self._get_full_path(prefix)
        files = []
        
        if base.exists():
            if base.is_dir():
                for path in base.rglob("*"):
                    if path.is_file():
                        relative = path.relative_to(self.base_path)
                        files.append(str(relative))
            elif base.is_file():
                files.append(prefix)
        
        return files

    async def delete_folder(self, prefix: str) -> int:
        """Delete all files with a given prefix."""
        base = self._get_full_path(prefix)
        deleted = 0

        if base.exists():
            if base.is_dir():
                # Delete directory and all contents
                shutil.rmtree(base)
                deleted = 1  # Count as 1 folder operation
                logger.debug(f"Deleted folder from local storage: {prefix}")
            else:
                await self.delete_file(prefix)
                deleted = 1

        return deleted

    async def generate_presigned_upload_url(
        self,
        file_path: str,
        content_type: str = "application/pdf",
        expires_in: int = 3600,
    ) -> dict:
        """
        Generate upload URL for local storage.

        Local storage has no presigned-PUT equivalent, and the previously
        advertised ``/api/v1/leaflets/upload-direct`` endpoint does not
        exist. Returning ``supported=False`` lets the frontend skip the
        direct-upload optimisation and fall back to the standard
        multipart upload endpoint instead of trying a URL that 404s.
        """
        return {
            "url": None,
            "fields": {},
            "method": "POST",
            "use_form_data": True,
            "supported": False,
            "reason": "Direct upload is only available for S3/MinIO storage backends.",
        }


class S3StorageBackend(StorageBackend):
    """AWS S3 / MinIO storage backend."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None,
        secure: bool = True,
    ):
        """
        Initialize S3/MinIO storage backend.
        
        Args:
            bucket_name: S3 bucket name
            endpoint_url: Custom endpoint URL (for MinIO)
            access_key: AWS access key ID
            secret_key: AWS secret access key
            region: AWS region
            secure: Use HTTPS (for MinIO)
        """
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3")
        
        self.bucket_name = bucket_name or settings.s3_bucket_name
        
        # Determine if using MinIO or AWS S3
        if settings.storage_mode == "minio":
            # Internal endpoint for Docker communication
            internal_endpoint = endpoint_url or f"{'https' if settings.minio_secure else 'http'}://{settings.minio_endpoint}"
            self.client = boto3.client(
                's3',
                endpoint_url=internal_endpoint,
                aws_access_key_id=access_key or settings.minio_access_key,
                aws_secret_access_key=secret_key or settings.minio_secret_key,
                config=Config(signature_version='s3v4'),
            )
            self.endpoint_url = internal_endpoint
            
            # Public endpoint for presigned URLs (accessible from browser)
            # Use MINIO_PUBLIC_ENDPOINT env var, or default to localhost:9000
            public_endpoint = os.getenv('MINIO_PUBLIC_ENDPOINT', 'localhost:9000')
            self.public_endpoint_url = f"http://{public_endpoint}"
            
            # Create a separate client for generating presigned URLs with public endpoint
            self.presign_client = boto3.client(
                's3',
                endpoint_url=self.public_endpoint_url,
                aws_access_key_id=access_key or settings.minio_access_key,
                aws_secret_access_key=secret_key or settings.minio_secret_key,
                config=Config(signature_version='s3v4'),
            )
            logger.info(f"MinIO internal endpoint: {internal_endpoint}, public endpoint: {self.public_endpoint_url}")
        else:
            # AWS S3 - use signature v4 for compatibility
            self.client = boto3.client(
                's3',
                aws_access_key_id=access_key or settings.aws_access_key_id,
                aws_secret_access_key=secret_key or settings.aws_secret_access_key,
                region_name=region or settings.aws_region,
                config=Config(signature_version='s3v4'),
            )
            self.endpoint_url = None
            self.public_endpoint_url = None
            self.presign_client = self.client  # Use same client for AWS S3
            logger.info(f"Initialized AWS S3 storage in region: {region or settings.aws_region}")
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
        
        logger.info(f"Initialized S3 storage with bucket: {self.bucket_name}")

    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
            except Exception as e:
                logger.warning(f"Could not create bucket: {e}")

    async def upload_file(
        self,
        file_content: Union[bytes, BinaryIO],
        file_path: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file to S3."""
        # Get bytes from content
        if isinstance(file_content, bytes):
            data = BytesIO(file_content)
        else:
            data = file_content
        
        # Determine content type
        if content_type is None:
            content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        
        # Upload to S3
        extra_args = {'ContentType': content_type}
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.upload_fileobj(
                data,
                self.bucket_name,
                file_path,
                ExtraArgs=extra_args,
            )
        )
        
        logger.debug(f"Uploaded file to S3: {file_path}")
        
        # Return URL
        return await self.get_file_url(file_path)

    async def download_file(self, file_path: str) -> bytes:
        """Download a file from S3."""
        buffer = BytesIO()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.download_fileobj(
                self.bucket_name,
                file_path,
                buffer,
            )
        )
        
        buffer.seek(0)
        return buffer.read()

    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from S3."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_path,
                )
            )
            logger.debug(f"Deleted file from S3: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False

    async def file_exists(self, file_path: str) -> bool:
        """Check if a file exists in S3."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.client.head_object(
                    Bucket=self.bucket_name,
                    Key=file_path,
                )
            )
            return True
        except Exception:
            return False

    async def get_file_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Get a presigned URL for the file.
        
        Uses the public endpoint URL for MinIO so the URL is accessible from browsers.
        """
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            lambda: self.presign_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_path,
                },
                ExpiresIn=expires_in,
            )
        )
        return url

    async def list_files(self, prefix: str) -> list[str]:
        """List files with a given prefix."""
        files = []
        
        loop = asyncio.get_event_loop()
        paginator = self.client.get_paginator('list_objects_v2')
        
        def _list():
            result = []
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get('Contents', []):
                    result.append(obj['Key'])
            return result
        
        files = await loop.run_in_executor(None, _list)
        return files

    async def delete_folder(self, prefix: str) -> int:
        """Delete all files with a given prefix."""
        files = await self.list_files(prefix)
        deleted = 0

        for file_path in files:
            if await self.delete_file(file_path):
                deleted += 1

        return deleted

    async def generate_presigned_upload_url(
        self,
        file_path: str,
        content_type: str = "application/pdf",
        expires_in: int = 3600,
    ) -> dict:
        """
        Generate a presigned URL for direct S3 upload.

        Uses presigned POST for browser-compatible uploads.
        """
        loop = asyncio.get_event_loop()

        def _generate():
            # Generate presigned POST data for direct upload
            return self.client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=file_path,
                Fields={
                    "Content-Type": content_type,
                },
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, 100 * 1024 * 1024],  # 1 byte to 100MB
                ],
                ExpiresIn=expires_in,
            )

        result = await loop.run_in_executor(None, _generate)

        return {
            "url": result["url"],
            "fields": result["fields"],
            "method": "POST",
            "use_form_data": True,
        }


# Storage backend singleton
_storage_backend: Optional[StorageBackend] = None


def get_storage_backend() -> StorageBackend:
    """
    Get the configured storage backend.
    
    Returns:
        StorageBackend instance based on configuration
    """
    global _storage_backend
    
    if _storage_backend is None:
        if settings.storage_mode == "local":
            _storage_backend = LocalStorageBackend()
        elif settings.storage_mode in ("s3", "minio"):
            _storage_backend = S3StorageBackend()
        else:
            raise ValueError(f"Unknown storage mode: {settings.storage_mode}")
    
    return _storage_backend


def reset_storage_backend():
    """Reset the storage backend (useful for testing)."""
    global _storage_backend
    _storage_backend = None


# Utility functions

def compute_file_hash(content: bytes) -> str:
    """
    Compute SHA256 hash of file content.
    
    Args:
        content: File content as bytes
        
    Returns:
        Hex string of SHA256 hash
    """
    return hashlib.sha256(content).hexdigest()


def generate_storage_path(
    leaflet_id: str,
    filename: str,
    subfolder: str = "source",
) -> str:
    """
    Generate a storage path for a file.
    
    Args:
        leaflet_id: Unique leaflet identifier
        filename: Original filename
        subfolder: Subfolder within leaflet directory
        
    Returns:
        Storage path string
    """
    return f"leaflets/{leaflet_id}/{subfolder}/{filename}"


def generate_page_path(
    leaflet_id: str,
    page_number: int,
    extension: str = "png",
) -> str:
    """
    Generate a storage path for a page image.
    
    Args:
        leaflet_id: Unique leaflet identifier
        page_number: Page number (1-indexed)
        extension: File extension
        
    Returns:
        Storage path string
    """
    return f"leaflets/{leaflet_id}/pages/page_{page_number:03d}.{extension}"


def generate_thumbnail_path(
    leaflet_id: str,
    page_number: int,
    extension: str = "jpg",
) -> str:
    """
    Generate a storage path for a page thumbnail.
    
    Args:
        leaflet_id: Unique leaflet identifier
        page_number: Page number (1-indexed)
        extension: File extension
        
    Returns:
        Storage path string
    """
    return f"leaflets/{leaflet_id}/thumbnails/thumb_{page_number:03d}.{extension}"


def generate_product_image_path(
    leaflet_id: str,
    page_number: int,
    product_index: int,
    extension: str = "png",
) -> str:
    """
    Generate a storage path for a product image.
    
    Args:
        leaflet_id: Unique leaflet identifier
        page_number: Page number (1-indexed)
        product_index: Product index on the page (1-indexed)
        extension: File extension
        
    Returns:
        Storage path string
    """
    return f"leaflets/{leaflet_id}/products/page_{page_number:03d}_product_{product_index:02d}.{extension}"