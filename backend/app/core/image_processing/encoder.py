"""
Image Encoder Module.

Provides base64 encoding and format conversion for product images.
Supports multiple output formats with quality control.

Example Usage:
    from app.core.image_processing.encoder import ImageEncoder
    
    encoder = ImageEncoder()
    base64_data = encoder.encode_to_base64(image, format="JPEG", quality=85)
"""

import base64
import logging
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Optional, Tuple, Union

from PIL import Image

logger = logging.getLogger(__name__)


class EncodingFormat(str, Enum):
    """Supported image encoding formats."""
    JPEG = "JPEG"
    PNG = "PNG"
    WEBP = "WEBP"


@dataclass
class EncodingResult:
    """
    Result of image encoding operation.
    
    Attributes:
        success: Whether encoding succeeded
        data: Encoded data (base64 string or bytes)
        format: Output format used
        size_bytes: Size of encoded data
        mime_type: MIME type of encoded image
        data_url: Complete data URL (data:mime;base64,...)
        error: Error message if failed
    """
    success: bool
    data: Optional[str] = None
    format: Optional[EncodingFormat] = None
    size_bytes: int = 0
    mime_type: Optional[str] = None
    data_url: Optional[str] = None
    error: Optional[str] = None


class ImageEncoder:
    """
    Encodes images to base64 and various formats.
    
    Supports JPEG, PNG, and WebP formats with configurable
    quality settings. Provides both raw base64 and data URLs.
    
    Attributes:
        default_format: Default output format
        default_quality: Default JPEG/WebP quality (0-100)
        optimize: Whether to optimize output
        
    Example:
        >>> encoder = ImageEncoder(default_format=EncodingFormat.JPEG)
        >>> result = encoder.encode_to_base64(image, quality=85)
        >>> if result.success:
        ...     print(f"Encoded to {result.size_bytes} bytes")
    """
    
    # Format to MIME type mapping
    MIME_TYPES = {
        EncodingFormat.JPEG: "image/jpeg",
        EncodingFormat.PNG: "image/png",
        EncodingFormat.WEBP: "image/webp",
    }
    
    # Default quality settings per format
    DEFAULT_QUALITY = {
        EncodingFormat.JPEG: 85,
        EncodingFormat.PNG: None,  # PNG doesn't use quality
        EncodingFormat.WEBP: 85,
    }
    
    def __init__(
        self,
        default_format: EncodingFormat = EncodingFormat.PNG,
        default_quality: int = 85,
        optimize: bool = True,
    ):
        """
        Initialize the encoder.
        
        Args:
            default_format: Default output format
            default_quality: Default quality for lossy formats
            optimize: Whether to optimize output size
        """
        self.default_format = default_format
        self.default_quality = default_quality
        self.optimize = optimize
    
    def encode_to_base64(
        self,
        image: Image.Image,
        format: Optional[EncodingFormat] = None,
        quality: Optional[int] = None,
        include_data_url: bool = True,
    ) -> EncodingResult:
        """
        Encode an image to base64.
        
        Args:
            image: PIL Image to encode
            format: Output format (uses default if None)
            quality: Quality for lossy formats (0-100)
            include_data_url: Whether to include data URL prefix
            
        Returns:
            EncodingResult with base64 data
        """
        try:
            # Use defaults if not specified
            format = format or self.default_format
            quality = quality or self.DEFAULT_QUALITY.get(format, self.default_quality)
            
            # Convert image mode if needed for JPEG
            if format == EncodingFormat.JPEG and image.mode in ("RGBA", "P", "LA"):
                # Create white background for transparency
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(image, mask=image.split()[-1] if "A" in image.mode else None)
                image = background
            elif format == EncodingFormat.JPEG and image.mode != "RGB":
                image = image.convert("RGB")
            
            # Encode to bytes
            buffer = BytesIO()
            save_kwargs = {"format": format.value, "optimize": self.optimize}
            
            if format in (EncodingFormat.JPEG, EncodingFormat.WEBP):
                save_kwargs["quality"] = quality
            
            image.save(buffer, **save_kwargs)
            image_bytes = buffer.getvalue()
            
            # Convert to base64
            base64_data = base64.b64encode(image_bytes).decode("utf-8")
            
            # Build result
            mime_type = self.MIME_TYPES[format]
            data_url = f"data:{mime_type};base64,{base64_data}" if include_data_url else None
            
            logger.debug(
                f"Encoded image to {format.value}: "
                f"{len(image_bytes)} bytes, {len(base64_data)} base64 chars"
            )
            
            return EncodingResult(
                success=True,
                data=base64_data,
                format=format,
                size_bytes=len(image_bytes),
                mime_type=mime_type,
                data_url=data_url,
            )
            
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            return EncodingResult(
                success=False,
                error=str(e),
            )
    
    def encode_to_bytes(
        self,
        image: Image.Image,
        format: Optional[EncodingFormat] = None,
        quality: Optional[int] = None,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Encode an image to bytes.
        
        Args:
            image: PIL Image to encode
            format: Output format
            quality: Quality for lossy formats
            
        Returns:
            Tuple of (bytes, error_message)
        """
        try:
            format = format or self.default_format
            quality = quality or self.DEFAULT_QUALITY.get(format, self.default_quality)
            
            # Handle RGBA to RGB conversion for JPEG
            if format == EncodingFormat.JPEG and image.mode in ("RGBA", "P", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(image, mask=image.split()[-1] if "A" in image.mode else None)
                image = background
            elif format == EncodingFormat.JPEG and image.mode != "RGB":
                image = image.convert("RGB")
            
            buffer = BytesIO()
            save_kwargs = {"format": format.value, "optimize": self.optimize}
            
            if format in (EncodingFormat.JPEG, EncodingFormat.WEBP):
                save_kwargs["quality"] = quality
            
            image.save(buffer, **save_kwargs)
            return buffer.getvalue(), None
            
        except Exception as e:
            return None, str(e)
    
    def decode_from_base64(
        self,
        base64_data: str,
    ) -> Tuple[Optional[Image.Image], Optional[str]]:
        """
        Decode a base64 string to PIL Image.
        
        Args:
            base64_data: Base64 encoded image data
            
        Returns:
            Tuple of (PIL Image, error_message)
        """
        try:
            # Remove data URL prefix if present
            if base64_data.startswith("data:"):
                base64_data = base64_data.split(",", 1)[1]
            
            # Decode base64
            image_bytes = base64.b64decode(base64_data)
            
            # Load image
            buffer = BytesIO(image_bytes)
            image = Image.open(buffer)
            
            return image, None
            
        except Exception as e:
            return None, str(e)
    
    def estimate_encoded_size(
        self,
        image: Image.Image,
        format: EncodingFormat = EncodingFormat.JPEG,
        quality: int = 85,
    ) -> int:
        """
        Estimate the encoded size of an image.
        
        Useful for making storage decisions without
        actually encoding the full image.
        
        Args:
            image: PIL Image
            format: Target format
            quality: Target quality
            
        Returns:
            Estimated size in bytes
        """
        width, height = image.size
        pixels = width * height
        
        # Rough estimates based on format and quality
        if format == EncodingFormat.PNG:
            # PNG is lossless, size depends on content complexity
            # Estimate: ~3 bytes per pixel for typical content
            return int(pixels * 2.5)
        
        elif format == EncodingFormat.JPEG:
            # JPEG compression varies with quality
            # Rough formula: pixels * bytes_per_pixel * quality_factor
            quality_factor = quality / 100
            return int(pixels * 0.5 * quality_factor + 5000)
        
        elif format == EncodingFormat.WEBP:
            # WebP is generally 25-35% smaller than JPEG
            jpeg_estimate = int(pixels * 0.5 * (quality / 100) + 5000)
            return int(jpeg_estimate * 0.7)
        
        return pixels * 3  # Fallback: uncompressed estimate
    
    def get_optimal_format(
        self,
        image: Image.Image,
        target_size: Optional[int] = None,
        prefer_quality: bool = True,
    ) -> Tuple[EncodingFormat, int]:
        """
        Determine optimal format and quality for an image.
        
        Args:
            image: PIL Image to analyze
            target_size: Target size in bytes (optional)
            prefer_quality: Prefer quality over size
            
        Returns:
            Tuple of (format, quality)
        """
        has_transparency = image.mode in ("RGBA", "LA", "P")
        
        # If image has transparency, use PNG or WebP
        if has_transparency:
            if target_size and target_size < 100_000:
                return EncodingFormat.WEBP, 85
            return EncodingFormat.PNG, 100
        
        # For non-transparent images
        if prefer_quality:
            # PNG for small images, JPEG for larger
            if image.width * image.height < 50_000:  # ~225x225
                return EncodingFormat.PNG, 100
            return EncodingFormat.JPEG, 90
        else:
            # Prefer smaller file size
            return EncodingFormat.WEBP, 80


def encode_image_to_base64(
    image: Union[Image.Image, str, bytes],
    format: EncodingFormat = EncodingFormat.JPEG,
    quality: int = 85,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Convenience function to encode an image to base64.
    
    Args:
        image: PIL Image, path string, or image bytes
        format: Output format
        quality: Quality for lossy formats
        
    Returns:
        Tuple of (base64_string, error_message)
    """
    encoder = ImageEncoder()
    
    # Load image if path or bytes
    if isinstance(image, str):
        try:
            image = Image.open(image)
        except Exception as e:
            return None, f"Failed to load image: {e}"
    elif isinstance(image, bytes):
        try:
            image = Image.open(BytesIO(image))
        except Exception as e:
            return None, f"Failed to decode image bytes: {e}"
    
    result = encoder.encode_to_base64(image, format, quality, include_data_url=False)
    
    if result.success:
        return result.data, None
    return None, result.error