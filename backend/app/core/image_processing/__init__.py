"""
Image Processing Module.

This module provides image extraction, encoding, quality scoring,
storage management, and bounding box refinement for product images.

Example Usage:
    from app.core.image_processing import (
        ImageExtractor,
        ImageEncoder,
        StorageManager,
        QualityScorer,
        BoundingBoxRefiner,
    )
    
    extractor = ImageExtractor()
    product_image = extractor.extract_product_image(
        page_image_path="/path/to/page.png",
        bounding_box={"x": 50, "y": 120, "width": 280, "height": 350},
        product_id="prod_001"
    )
    
    # Optionally refine bounding boxes using computer vision
    refiner = BoundingBoxRefiner()
    refined_bbox = refiner.refine_bounding_box(page_image, bounding_box)
"""

from app.core.image_processing.extractor import ImageExtractor
from app.core.image_processing.encoder import ImageEncoder, EncodingFormat
from app.core.image_processing.storage import StorageManager, StorageDecision
from app.core.image_processing.quality import QualityScorer, QualityReport

# Import bbox refiner (optional - depends on OpenCV)
try:
    from app.core.image_processing.bbox_refiner import (
        BoundingBoxRefiner,
        RefinementResult,
        refine_product_bboxes,
    )
    BBOX_REFINEMENT_AVAILABLE = True
except ImportError:
    BBOX_REFINEMENT_AVAILABLE = False
    BoundingBoxRefiner = None
    RefinementResult = None
    refine_product_bboxes = None

# Import OCR-based bbox detector (optional - depends on EasyOCR)
try:
    from app.core.image_processing.ocr_bbox_detector import (
        OCRBoundingBoxDetector,
        get_bbox_detector,
    )
    OCR_BBOX_DETECTION_AVAILABLE = True
except ImportError:
    OCR_BBOX_DETECTION_AVAILABLE = False
    OCRBoundingBoxDetector = None
    get_bbox_detector = None

# Import bounding box visualizer for two-pass verification
from app.core.image_processing.bbox_visualizer import (
    BBoxVisualizer,
    get_bbox_visualizer,
    BBOX_COLORS,
    COLOR_NAMES,
)

# Import grid overlay for grid-based bounding box detection
from app.core.image_processing.grid_overlay import (
    GridOverlay,
    get_grid_overlay,
)

# PaddleOCR detector - lazy loading to avoid import-time issues
# PaddleOCR tries to create directories on import, which can fail in containers
# Use is_paddle_ocr_available() to check availability at runtime

def is_paddle_ocr_available() -> bool:
    """Check if PaddleOCR is available (lazy check)."""
    try:
        from paddleocr import PaddleOCR
        return True
    except ImportError:
        return False

def get_paddle_ocr_detector():
    """Get PaddleOCR detector (lazy import)."""
    from app.core.image_processing.paddle_ocr_detector import get_paddle_ocr_detector as _get_detector
    return _get_detector()

# Set to None - use is_paddle_ocr_available() for runtime check
PADDLE_OCR_AVAILABLE = None  # Use is_paddle_ocr_available() instead
PaddleOCRDetector = None  # Import lazily when needed

__all__ = [
    "ImageExtractor",
    "ImageEncoder",
    "EncodingFormat",
    "StorageManager",
    "StorageDecision",
    "QualityScorer",
    "QualityReport",
    "BoundingBoxRefiner",
    "RefinementResult",
    "refine_product_bboxes",
    "BBOX_REFINEMENT_AVAILABLE",
    "OCRBoundingBoxDetector",
    "get_bbox_detector",
    "OCR_BBOX_DETECTION_AVAILABLE",
    "BBoxVisualizer",
    "get_bbox_visualizer",
    "BBOX_COLORS",
    "COLOR_NAMES",
    "GridOverlay",
    "get_grid_overlay",
    "PaddleOCRDetector",
    "get_paddle_ocr_detector",
    "is_paddle_ocr_available",
    "PADDLE_OCR_AVAILABLE",
]