"""
PaddleOCR-based Bounding Box Detector.

Uses PaddleOCR to detect text regions and clusters them into product bounding boxes.
This provides more accurate bounding boxes than VLM estimation.

Now includes visual boundary detection for irregular layouts.

Example Usage:
    from app.core.image_processing.paddle_ocr_detector import PaddleOCRDetector

    detector = PaddleOCRDetector()
    results = detector.detect_product_regions(image_path)
    # results = [{"bbox": {"x": 50, "y": 100, "width": 300, "height": 400}, "texts": [...]}]
"""

import os
# Set PaddlePaddle environment variables BEFORE importing paddle
# These disable PIR (Paddle IR) and oneDNN which cause compatibility issues in 3.x
os.environ['FLAGS_use_mkldnn'] = '0'  # Disable oneDNN/MKLDNN
os.environ['FLAGS_enable_pir_api'] = '0'  # Disable PIR API
os.environ['FLAGS_enable_pir_in_executor'] = '0'  # Disable PIR in executor
os.environ['FLAGS_pir_apply_inplace_pass'] = '0'  # Disable PIR inplace pass
os.environ['FLAGS_allocator_strategy'] = 'naive_best_fit'
os.environ['MKLDNN_CACHE_CAPACITY'] = '0'  # Disable MKLDNN cache

import logging
import gc
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
from io import BytesIO

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Try to import visual boundary detector
try:
    from app.core.image_processing.visual_boundary_detector import (
        VisualBoundaryDetector,
        is_visual_detection_available,
    )
    VISUAL_DETECTION_AVAILABLE = is_visual_detection_available()
except ImportError:
    VISUAL_DETECTION_AVAILABLE = False
    VisualBoundaryDetector = None

# Lazy load PaddleOCR to avoid import errors if not installed
# CRITICAL: PaddleOCR 3.x has state corruption issues - instances become corrupted after first prediction
# Solution: Create FRESH instances for each detection and dispose after use
import os as _os
import threading as _threading
_ocr_init_lock = _threading.Lock()  # Lock to prevent simultaneous initialization
_ocr_call_count = {}  # pid -> call count (for diagnostics)

# Maximum image dimension for OCR (larger images cause memory issues and slowdowns)
MAX_OCR_IMAGE_DIMENSION = 4000  # pixels


def create_fresh_paddle_ocr():
    """
    Create a FRESH PaddleOCR instance for single-use.

    IMPORTANT: PaddleOCR 3.x has state corruption after first prediction.
    To avoid this, we create a new instance for each detection call
    and let it be garbage collected after use.

    Uses a lock to prevent multiple simultaneous initializations which
    can cause "Interface already registered" errors.
    """
    current_pid = _os.getpid()

    # Track call count for diagnostics
    if current_pid not in _ocr_call_count:
        _ocr_call_count[current_pid] = 0
    _ocr_call_count[current_pid] += 1
    call_num = _ocr_call_count[current_pid]

    # Acquire lock to prevent simultaneous initialization
    with _ocr_init_lock:
        logger.info(f"[OCR INIT] Creating FRESH PaddleOCR instance #{call_num} for PID {current_pid}...")
        try:
            from paddleocr import PaddleOCR
            # PaddleOCR 3.x uses different initialization
            # Disable extra processing for speed
            ocr = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
            logger.info(f"[OCR INIT] PaddleOCR 3.x instance #{call_num} created successfully!")
            return ocr
        except ImportError as e:
            logger.error(f"[OCR INIT] PaddleOCR not available: {e}")
            raise
        except TypeError as e:
            # Fallback for older PaddleOCR versions
            logger.info(f"[OCR INIT] PaddleOCR 3.x init failed with TypeError: {e}, trying legacy...")
            try:
                from paddleocr import PaddleOCR
                ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang='en',
                    show_log=False,
                    use_gpu=False,
                )
                logger.info(f"[OCR INIT] PaddleOCR (legacy) instance #{call_num} created successfully!")
                return ocr
            except Exception as e:
                logger.error(f"[OCR INIT] PaddleOCR initialization failed: {e}")
                raise
        except Exception as e:
            logger.error(f"[OCR INIT] Unexpected error during PaddleOCR init: {type(e).__name__}: {e}", exc_info=True)
            raise


def resize_image_for_ocr(image: Union[bytes, np.ndarray, str, Path], max_dim: int = MAX_OCR_IMAGE_DIMENSION) -> Tuple[bytes, float]:
    """
    Resize image if it exceeds maximum dimension for OCR.

    Large images (6000x8000+) cause:
    1. Memory issues
    2. Very slow OCR processing
    3. Higher chance of state corruption

    Args:
        image: Image in bytes, numpy array, or path
        max_dim: Maximum dimension (width or height)

    Returns:
        Tuple of (resized_image_bytes, scale_factor)
        scale_factor is used to adjust bounding box coordinates back to original size
    """
    # Load image
    if isinstance(image, (str, Path)):
        pil_image = Image.open(image)
    elif isinstance(image, bytes):
        pil_image = Image.open(BytesIO(image))
    elif isinstance(image, np.ndarray):
        pil_image = Image.fromarray(image)
    else:
        raise ValueError(f"Unsupported image type: {type(image)}")

    original_width, original_height = pil_image.size

    # Check if resizing is needed
    if original_width <= max_dim and original_height <= max_dim:
        # No resize needed, return original as bytes
        if isinstance(image, bytes):
            return image, 1.0
        else:
            buffer = BytesIO()
            pil_image.save(buffer, format='PNG')
            return buffer.getvalue(), 1.0

    # Calculate scale factor
    scale = min(max_dim / original_width, max_dim / original_height)
    new_width = int(original_width * scale)
    new_height = int(original_height * scale)

    logger.info(f"[OCR RESIZE] Resizing image from {original_width}x{original_height} to {new_width}x{new_height} (scale={scale:.3f})")

    # Resize using high-quality resampling
    resized = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Convert to bytes
    buffer = BytesIO()
    resized.save(buffer, format='PNG')

    return buffer.getvalue(), scale


# Keep the old function name for backward compatibility but make it create fresh instances
def get_paddle_ocr():
    """
    Get PaddleOCR instance - now creates FRESH instance each time.

    DEPRECATED: Use create_fresh_paddle_ocr() directly for clarity.
    This function now just calls create_fresh_paddle_ocr() for backward compatibility.
    """
    return create_fresh_paddle_ocr()


class PaddleOCRDetector:
    """
    Detects product regions using PaddleOCR text detection.

    Uses OCR to find text regions, then clusters them into product bounding boxes.
    Now with grid-aware clustering for accurate product card detection.
    """

    def __init__(
        self,
        min_cluster_gap: int = 50,  # Reduced from 100 - tighter clustering
        min_product_width: int = 120,  # Slightly smaller min
        min_product_height: int = 150,
        padding: int = 10,  # Reduced padding for tighter crops
    ):
        """
        Initialize the detector.

        Args:
            min_cluster_gap: Maximum pixel gap between text boxes to be in same cluster
            min_product_width: Minimum product bounding box width
            min_product_height: Minimum product bounding box height
            padding: Padding to add around detected regions
        """
        self.min_cluster_gap = min_cluster_gap
        self.min_product_width = min_product_width
        self.min_product_height = min_product_height
        self.padding = padding

    def detect_text_boxes(
        self,
        image: Union[str, Path, bytes, np.ndarray],
        scale_factor: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Detect all text boxes in an image using PaddleOCR.

        IMPORTANT: Creates a FRESH PaddleOCR instance for each call to avoid
        state corruption issues in PaddleOCR 3.x.

        Args:
            image: Image path, bytes, or numpy array
            scale_factor: Scale factor to apply to coordinates (for resized images)

        Returns:
            List of text boxes with coordinates and text:
            [{"box": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]], "text": "...", "confidence": 0.95}]
        """
        import tempfile

        # Step 1: Resize large images to prevent memory issues and slowdowns
        resized_image, resize_scale = resize_image_for_ocr(image)
        total_scale = scale_factor / resize_scale  # Inverse scale to get back to original coords

        # Step 2: Save to temp file for PaddleOCR 3.x compatibility
        # PaddleOCR 3.x works better with file paths than bytes
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        img_input = temp_file.name
        ocr = None  # Initialize for cleanup in finally block
        try:
            temp_file.write(resized_image)
            temp_file.close()

            # Step 3: Create FRESH PaddleOCR instance (avoids state corruption)
            logger.info(f"[OCR DETECT] Creating fresh PaddleOCR instance...")
            ocr = create_fresh_paddle_ocr()

            # Step 4: Run OCR prediction
            logger.info(f"[OCR DETECT] Running PaddleOCR 3.x predict...")
            try:
                result = ocr.predict(input=img_input)
                logger.info(f"[OCR DETECT] PaddleOCR predict completed successfully!")
                logger.info(f"[OCR DETECT] Result type: {type(result)}, length: {len(result) if hasattr(result, '__len__') else 'N/A'}")
                parsed = self._parse_v3_result(result)
            except (AttributeError, NotImplementedError, RuntimeError) as e:
                # Fallback to legacy API on compatibility issues
                logger.warning(f"[OCR DETECT] PaddleOCR 3.x predict failed: {type(e).__name__}: {e}")
                logger.info("[OCR DETECT] Trying legacy API...")
                try:
                    result = ocr.ocr(img_input)
                    parsed = self._parse_legacy_result(result)
                except TypeError:
                    try:
                        result = ocr.ocr(img_input, cls=True)
                        parsed = self._parse_legacy_result(result)
                    except Exception as inner_e:
                        logger.error(f"[OCR DETECT] PaddleOCR all APIs failed: {type(inner_e).__name__}: {inner_e}")
                        parsed = []
                except Exception as legacy_e:
                    logger.error(f"[OCR DETECT] PaddleOCR legacy API failed: {type(legacy_e).__name__}: {legacy_e}")
                    parsed = []

            # Step 5: Scale coordinates back to original image size
            if resize_scale != 1.0 and parsed:
                logger.info(f"[OCR DETECT] Scaling {len(parsed)} boxes back by {1/resize_scale:.3f}")
                for box in parsed:
                    box["x"] = box["x"] / resize_scale
                    box["y"] = box["y"] / resize_scale
                    box["width"] = box["width"] / resize_scale
                    box["height"] = box["height"] / resize_scale
                    # Also scale the box polygon if present
                    if "box" in box and box["box"]:
                        box["box"] = [[p[0] / resize_scale, p[1] / resize_scale] for p in box["box"]]

            logger.info(f"[OCR DETECT] Parsed {len(parsed)} text boxes from result")
            return parsed

        except Exception as e:
            logger.error(f"[OCR DETECT] Unexpected error during OCR: {type(e).__name__}: {e}", exc_info=True)
            return []
        finally:
            # Step 6: Clean up temp file
            try:
                os.unlink(img_input)
            except:
                pass

            # Step 7: Force garbage collection to clean up the PaddleOCR instance
            # This helps prevent memory buildup and state corruption
            if ocr is not None:
                del ocr
            gc.collect()

    def _parse_v3_result(self, result) -> List[Dict[str, Any]]:
        """Parse PaddleOCR 3.x result format."""
        text_boxes = []

        if not result:
            logger.warning("[PARSE] No text detected by PaddleOCR")
            return []

        logger.info(f"[PARSE] Parsing {len(result)} result items")

        for res_idx, res in enumerate(result):
            # PaddleOCR 3.x returns result objects with different structure
            # Try to extract text detection results
            try:
                logger.debug(f"[PARSE] Result {res_idx}: type={type(res).__name__}")

                # Get the OCR results - structure varies by version
                if hasattr(res, 'rec_texts') and hasattr(res, 'dt_polys'):
                    texts = res.rec_texts
                    boxes = res.dt_polys
                    scores = res.rec_scores if hasattr(res, 'rec_scores') else [0.9] * len(texts)
                    logger.info(f"[PARSE] Direct attributes: {len(texts)} texts")

                    for i, (text, box, score) in enumerate(zip(texts, boxes, scores)):
                        if not text or not text.strip():
                            continue

                        # Convert polygon to bounding box
                        xs = [p[0] for p in box]
                        ys = [p[1] for p in box]

                        text_boxes.append({
                            "box": box.tolist() if hasattr(box, 'tolist') else box,
                            "x": float(min(xs)),
                            "y": float(min(ys)),
                            "width": float(max(xs) - min(xs)),
                            "height": float(max(ys) - min(ys)),
                            "text": text,
                            "confidence": float(score),
                        })
                elif hasattr(res, 'json'):
                    # Try JSON output - PaddleOCR 3.x nests data under 'res' key
                    json_data = res.json
                    logger.debug(f"[PARSE] JSON output, keys: {json_data.keys() if isinstance(json_data, dict) else type(json_data)}")

                    # Check if data is nested under 'res' key (PaddleOCR 3.3.x format)
                    if isinstance(json_data, dict) and 'res' in json_data:
                        data = json_data['res']
                        logger.info(f"[PARSE] Using nested 'res' data, keys: {data.keys() if isinstance(data, dict) else type(data)}")
                    else:
                        data = json_data

                    if isinstance(data, dict) and 'rec_texts' in data:
                        texts = data['rec_texts']
                        polys = data['dt_polys']
                        scores_list = data.get('rec_scores', [0.9] * len(texts))
                        logger.info(f"[PARSE] JSON found {len(texts)} texts")

                        for i, text in enumerate(texts):
                            if not text or not text.strip():
                                continue

                            box = polys[i]
                            score = scores_list[i] if i < len(scores_list) else 0.9

                            xs = [p[0] for p in box]
                            ys = [p[1] for p in box]

                            text_boxes.append({
                                "box": box,
                                "x": float(min(xs)),
                                "y": float(min(ys)),
                                "width": float(max(xs) - min(xs)),
                                "height": float(max(ys) - min(ys)),
                                "text": text,
                                "confidence": float(score),
                            })
                    else:
                        logger.warning(f"[PARSE] No rec_texts in data: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                else:
                    logger.warning(f"[PARSE] Unknown result format: {type(res)}, attrs: {dir(res)[:10]}")
            except Exception as e:
                logger.error(f"[PARSE] Error parsing PaddleOCR 3.x result: {e}", exc_info=True)
                continue

        logger.info(f"[PARSE] PaddleOCR detected {len(text_boxes)} text regions")
        return text_boxes

    def _parse_legacy_result(self, result) -> List[Dict[str, Any]]:
        """Parse legacy PaddleOCR result format."""
        text_boxes = []

        if not result or not result[0]:
            logger.warning("No text detected by PaddleOCR")
            return []

        for line in result[0]:
            box = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            text = line[1][0]
            confidence = line[1][1]

            # Convert box to simple format
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]

            text_boxes.append({
                "box": box,
                "x": min(xs),
                "y": min(ys),
                "width": max(xs) - min(xs),
                "height": max(ys) - min(ys),
                "text": text,
                "confidence": confidence,
            })

        logger.info(f"PaddleOCR detected {len(text_boxes)} text regions")
        return text_boxes

    # =========================================================================
    # TEXT CLASSIFICATION METHODS
    # =========================================================================

    def _is_price_text(self, text: str) -> bool:
        """
        Check if text looks like a price (e.g., "5,99", "€2.50", "1.99€").
        Prices are key anchors - each product has its own bold price.
        """
        import re
        price_patterns = [
            r'^\d+[.,]\d{2}$',           # 5,99 or 5.99
            r'^[€$£]\s*\d+[.,]\d{2}$',   # €5,99
            r'^\d+[.,]\d{2}\s*[€$£]$',   # 5,99€
            r'^\d+[.,]\d{2}\s*EUR$',     # 5,99 EUR
            r'^\d+[.,]\d{2}\s*€$',       # 5,99 € (with space)
            r'^\d{1,3}$',                # Single price like "199" (cents) or "2" (euros)
            r'^\d+[.,]-$',               # 5,- format
            r'^\d+[.,]\d{2}\s*kn$',      # Croatian Kuna
            r'^\d+[.,]\d{2}\s*rsd$',     # Serbian Dinar
            r'^\d+[.,]\d{2}\s*din$',     # Dinar abbreviation
        ]
        text = text.strip()
        # Also check for superscript prices like "1⁹⁹"
        if any(c in text for c in '⁰¹²³⁴⁵⁶⁷⁸⁹'):
            return True
        return any(re.match(p, text, re.IGNORECASE) for p in price_patterns)

    def _is_discount_text(self, text: str) -> bool:
        """Check if text is a discount badge (e.g., "-30%", "2+1", "AKTION")."""
        import re
        text_upper = text.strip().upper()
        text_clean = text.strip()

        discount_patterns = [
            r'^-?\d+\s*%$',              # -30% or 30%
            r'^\d+\+\d+$',               # 2+1
            r'^CENEJE\s*\d*\s*%?',       # Slovenian "cheaper"
        ]

        if any(re.match(p, text_clean, re.IGNORECASE) for p in discount_patterns):
            return True

        # Common discount keywords (expanded for Balkan region)
        discount_keywords = [
            'AKCIJA', 'AKTION', 'SALE', 'POPUST', 'SNIŽENJE',
            'PONUDA', 'PROMO', 'SPECIAL', 'GRATIS', 'FREE',
            'MEGA', 'SUPER', 'TOP', 'CENEJE', 'CENA',
            'UGODNO', 'RASPRODAJA', 'OUTLET', 'NOVO',
            'ODLIČNA', 'KAKOVOST',
        ]
        return any(kw in text_upper for kw in discount_keywords)

    def _is_unit_text(self, text: str) -> bool:
        """Check if text is unit/weight info (e.g., "500 g", "per kg", "1 L")."""
        import re
        text = text.strip().lower()
        unit_patterns = [
            r'^\d+\s*(g|kg|ml|l|cl|dl)$',      # 500 g, 1 kg, 750 ml
            r'^\d+[.,]\d+\s*(g|kg|ml|l)$',     # 1.5 kg, 0.5 l
            r'^per\s*(kg|l|100g|100ml)$',      # per kg
            r'^\d+\s*(kos|pcs|kom|st|ks)$',    # pieces
            r'^\d+\s*x\s*\d+',                 # 6x500ml
            r'^cca\.?\s*\d+',                  # cca 13 x 6,5 cm
            r'^\d+\s*x\s*\d+\s*(g|ml)$',       # 4 x 75 g
            r'^pakirano',                       # "pakirano" (packaged)
            r'^\d+\s*cm$',                      # dimensions
        ]
        return any(re.match(p, text, re.IGNORECASE) for p in unit_patterns)

    def _is_product_name_text(self, text: str) -> bool:
        """
        Check if text is likely a product name (longer text, not price/unit/discount).
        Product names are usually bold or larger text.
        """
        text = text.strip()
        # Product names are typically longer and not special types
        if len(text) < 3:
            return False
        if self._is_price_text(text):
            return False
        if self._is_discount_text(text):
            return False
        if self._is_unit_text(text):
            return False
        # Likely a product name if it contains letters and is reasonably long
        return len(text) >= 4 and any(c.isalpha() for c in text)

    def _classify_text_box(self, box: Dict[str, Any]) -> str:
        """
        Classify a text box into one of: price, discount, unit, name, other.
        """
        text = box.get("text", "").strip()
        if self._is_price_text(text):
            return "price"
        if self._is_discount_text(text):
            return "discount"
        if self._is_unit_text(text):
            return "unit"
        if self._is_product_name_text(text):
            return "name"
        return "other"

    # =========================================================================
    # GEOMETRY & ALIGNMENT METHODS
    # =========================================================================

    def _get_box_center(self, box: Dict[str, Any]) -> Tuple[float, float]:
        """Get center point of a box."""
        return (
            box["x"] + box["width"] / 2,
            box["y"] + box["height"] / 2
        )

    def _distance_between_boxes(self, box1: Dict[str, Any], box2: Dict[str, Any]) -> float:
        """Calculate Euclidean distance between box centers."""
        c1 = self._get_box_center(box1)
        c2 = self._get_box_center(box2)
        return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5

    def _is_vertically_aligned(self, box1: Dict[str, Any], box2: Dict[str, Any], tolerance: float = 0.3) -> bool:
        """
        Check if two boxes are vertically aligned (one above/below the other).
        Tolerance is fraction of box width allowed for horizontal offset.
        """
        # Check horizontal overlap
        x1_center = box1["x"] + box1["width"] / 2
        x2_center = box2["x"] + box2["width"] / 2
        max_width = max(box1["width"], box2["width"])
        return abs(x1_center - x2_center) < max_width * (1 + tolerance)

    def _is_horizontally_aligned(self, box1: Dict[str, Any], box2: Dict[str, Any], tolerance: float = 0.5) -> bool:
        """
        Check if two boxes are horizontally aligned (same row).
        Tolerance is fraction of box height allowed for vertical offset.
        """
        y1_center = box1["y"] + box1["height"] / 2
        y2_center = box2["y"] + box2["height"] / 2
        max_height = max(box1["height"], box2["height"])
        return abs(y1_center - y2_center) < max_height * (1 + tolerance)

    def _alignment_score(self, box1: Dict[str, Any], box2: Dict[str, Any]) -> float:
        """
        Calculate alignment score between two boxes (0-1).
        Higher score = better alignment (vertical or horizontal).
        """
        v_aligned = self._is_vertically_aligned(box1, box2)
        h_aligned = self._is_horizontally_aligned(box1, box2)

        if v_aligned and h_aligned:
            return 1.0
        elif v_aligned or h_aligned:
            return 0.7
        else:
            return 0.3

    def _is_compact_cluster(self, cluster: List[Dict[str, Any]], max_aspect_ratio: float = 3.0) -> bool:
        """
        Check if cluster forms a compact rectangular region.
        Rejects clusters that are too elongated (not a product card shape).
        """
        if len(cluster) < 2:
            return True

        bbox = self._get_cluster_bbox(cluster)
        width = bbox["width"]
        height = bbox["height"]

        if width == 0 or height == 0:
            return False

        aspect_ratio = max(width / height, height / width)
        return aspect_ratio <= max_aspect_ratio

    # =========================================================================
    # GRID DETECTION METHODS
    # =========================================================================

    def _detect_grid_columns(
        self,
        text_boxes: List[Dict[str, Any]],
        image_width: int,
        min_column_gap: int = 30,
    ) -> List[Tuple[int, int]]:
        """
        Detect column boundaries from text box positions.

        Uses clustering of x-coordinates to find column edges.
        Returns list of (start_x, end_x) tuples for each column.
        """
        if not text_boxes:
            return [(0, image_width)]

        # Collect all x-coordinates (left and right edges of text boxes)
        x_positions = []
        for box in text_boxes:
            x_positions.append(box["x"])
            x_positions.append(box["x"] + box["width"])

        x_positions.sort()

        # Find significant gaps in x-positions (potential column boundaries)
        gaps = []
        for i in range(1, len(x_positions)):
            gap = x_positions[i] - x_positions[i-1]
            if gap > min_column_gap:
                gaps.append((x_positions[i-1], x_positions[i], gap))

        # If few gaps found, try to estimate columns from box centers
        if len(gaps) < 2:
            return self._estimate_columns_from_centers(text_boxes, image_width)

        # Build column ranges from gaps
        columns = []
        gaps.sort(key=lambda g: g[2], reverse=True)  # Sort by gap size

        # Take the largest gaps as column boundaries
        # Typically leaflets have 3-5 columns
        boundary_gaps = sorted(gaps[:5], key=lambda g: g[0])

        start_x = 0
        for gap in boundary_gaps:
            col_end = gap[0]
            col_start_next = gap[1]

            if col_end - start_x > self.min_product_width:
                columns.append((start_x, col_end))

            start_x = col_start_next

        # Add final column
        if image_width - start_x > self.min_product_width:
            columns.append((start_x, image_width))

        logger.debug(f"Detected {len(columns)} columns: {columns}")
        return columns if columns else [(0, image_width)]

    def _estimate_columns_from_centers(
        self,
        text_boxes: List[Dict[str, Any]],
        image_width: int,
    ) -> List[Tuple[int, int]]:
        """
        Estimate columns by clustering text box centers.
        Fallback when gap detection doesn't work well.
        """
        # Get center x of each text box
        centers = [box["x"] + box["width"] / 2 for box in text_boxes]

        # Simple k-means style clustering
        # Estimate number of columns based on image width
        estimated_cols = max(2, min(6, image_width // 400))
        col_width = image_width / estimated_cols

        columns = []
        for i in range(estimated_cols):
            start = int(i * col_width)
            end = int((i + 1) * col_width)
            columns.append((start, end))

        return columns

    def _detect_grid_rows(
        self,
        text_boxes: List[Dict[str, Any]],
        image_height: int,
        min_row_gap: int = 40,
    ) -> List[Tuple[int, int]]:
        """
        Detect row boundaries from text box positions.

        Returns list of (start_y, end_y) tuples for each row.
        """
        if not text_boxes:
            return [(0, image_height)]

        # Collect all y-coordinates
        y_positions = []
        for box in text_boxes:
            y_positions.append(box["y"])
            y_positions.append(box["y"] + box["height"])

        y_positions.sort()

        # Find significant gaps in y-positions (potential row boundaries)
        gaps = []
        for i in range(1, len(y_positions)):
            gap = y_positions[i] - y_positions[i-1]
            if gap > min_row_gap:
                gaps.append((y_positions[i-1], y_positions[i], gap))

        if not gaps:
            return [(0, image_height)]

        # Build row ranges from gaps
        rows = []
        gaps.sort(key=lambda g: g[0])  # Sort by position

        start_y = 0
        for gap in gaps:
            row_end = gap[0]

            if row_end - start_y > self.min_product_height:
                rows.append((start_y, row_end + self.padding))

            start_y = gap[1] - self.padding

        # Add final row
        if image_height - start_y > self.min_product_height:
            rows.append((start_y, image_height))

        logger.debug(f"Detected {len(rows)} rows")
        return rows if rows else [(0, image_height)]

    def _get_grid_cell(
        self,
        box: Dict[str, Any],
        columns: List[Tuple[int, int]],
        rows: List[Tuple[int, int]],
    ) -> Tuple[int, int]:
        """
        Determine which grid cell a text box belongs to.

        Returns (col_idx, row_idx) tuple.
        """
        box_center_x = box["x"] + box["width"] / 2
        box_center_y = box["y"] + box["height"] / 2

        col_idx = 0
        for i, (start, end) in enumerate(columns):
            if start <= box_center_x < end:
                col_idx = i
                break

        row_idx = 0
        for i, (start, end) in enumerate(rows):
            if start <= box_center_y < end:
                row_idx = i
                break

        return (col_idx, row_idx)

    def _cluster_within_grid_cell(
        self,
        boxes: List[Dict[str, Any]],
        cell_bounds: Tuple[int, int, int, int],
    ) -> List[List[Dict[str, Any]]]:
        """
        Cluster text boxes within a single grid cell.

        Uses price-anchored clustering but constrained to the cell.

        Args:
            boxes: Text boxes within this cell
            cell_bounds: (x_start, y_start, x_end, y_end)

        Returns:
            List of clusters (each cluster is a list of boxes)
        """
        if not boxes:
            return []

        # Classify boxes
        for box in boxes:
            box["_type"] = self._classify_text_box(box)

        price_boxes = [b for b in boxes if b["_type"] == "price"]
        name_boxes = [b for b in boxes if b["_type"] == "name"]
        other_boxes = [b for b in boxes if b["_type"] in ("unit", "discount", "other")]

        # If only one price, this is likely one product
        if len(price_boxes) == 1:
            # All boxes belong to one product
            return [boxes]

        # If no prices or multiple prices, use sub-clustering
        if not price_boxes:
            # No prices - treat entire cell as one product
            return [boxes]

        # Multiple prices - might be multiple products in cell
        # Use vertical position to split
        clusters = []
        used = set()

        # Sort prices by y position
        price_boxes_sorted = sorted(price_boxes, key=lambda b: b["y"])

        for price_box in price_boxes_sorted:
            cluster = [price_box]
            used.add(id(price_box))

            # Find closest name above or at same level
            best_name = None
            best_dist = float('inf')

            for name_box in name_boxes:
                if id(name_box) in used:
                    continue

                # Name should be above or at same level as price
                if name_box["y"] <= price_box["y"] + price_box["height"]:
                    dist = abs(name_box["y"] - price_box["y"])
                    if dist < best_dist:
                        best_dist = dist
                        best_name = name_box

            if best_name:
                cluster.append(best_name)
                used.add(id(best_name))

            # Add other boxes that are vertically between name and price
            cluster_top = min(b["y"] for b in cluster)
            cluster_bottom = max(b["y"] + b["height"] for b in cluster)

            for other in other_boxes:
                if id(other) in used:
                    continue

                # Check if vertically overlapping with cluster
                other_center_y = other["y"] + other["height"] / 2
                if cluster_top - 30 <= other_center_y <= cluster_bottom + 30:
                    cluster.append(other)
                    used.add(id(other))

            clusters.append(cluster)

        # Handle unused boxes
        unused_boxes = [b for b in boxes if id(b) not in used]
        if unused_boxes and clusters:
            # Assign to nearest cluster
            for box in unused_boxes:
                best_cluster = None
                best_dist = float('inf')

                for cluster in clusters:
                    cluster_bbox = self._get_cluster_bbox(cluster)
                    dist = self._distance_to_bbox(box, cluster_bbox)
                    if dist < best_dist:
                        best_dist = dist
                        best_cluster = cluster

                if best_cluster and best_dist < 100:
                    best_cluster.append(box)

        return clusters

    def _distance_to_bbox(self, box: Dict[str, Any], bbox: Dict[str, int]) -> float:
        """Calculate distance from box center to bbox center."""
        box_cx = box["x"] + box["width"] / 2
        box_cy = box["y"] + box["height"] / 2
        bbox_cx = bbox["x"] + bbox["width"] / 2
        bbox_cy = bbox["y"] + bbox["height"] / 2
        return ((box_cx - bbox_cx) ** 2 + (box_cy - bbox_cy) ** 2) ** 0.5

    # =========================================================================
    # GRID-AWARE CLUSTERING (New Main Algorithm)
    # =========================================================================

    def cluster_text_boxes(
        self,
        text_boxes: List[Dict[str, Any]],
        image_width: int,
        image_height: int,
    ) -> List[Dict[str, Any]]:
        """
        Cluster text boxes into product offer groups using GRID-AWARE clustering.

        New algorithm:
        1. Detect grid structure (columns and rows) from text positions
        2. Assign each text box to a grid cell
        3. Cluster within each grid cell (price-anchored)
        4. Generate tight bounding boxes per product

        This prevents merging products across column/row boundaries.

        Args:
            text_boxes: List of detected text boxes
            image_width: Image width for boundary clamping
            image_height: Image height for boundary clamping

        Returns:
            List of product regions with bounding boxes and texts
        """
        if not text_boxes:
            return []

        # Step 1: Detect grid structure
        columns = self._detect_grid_columns(text_boxes, image_width)
        rows = self._detect_grid_rows(text_boxes, image_height)

        logger.info(f"Detected grid: {len(columns)} columns x {len(rows)} rows")

        # Step 2: Assign text boxes to grid cells
        grid_cells = {}  # (col_idx, row_idx) -> list of boxes

        for box in text_boxes:
            cell = self._get_grid_cell(box, columns, rows)
            if cell not in grid_cells:
                grid_cells[cell] = []
            grid_cells[cell].append(box)

        logger.info(f"Distributed text boxes across {len(grid_cells)} grid cells")

        # Step 3: Cluster within each grid cell
        all_clusters = []

        for (col_idx, row_idx), cell_boxes in grid_cells.items():
            # Get cell bounds
            col_start, col_end = columns[col_idx] if col_idx < len(columns) else (0, image_width)
            row_start, row_end = rows[row_idx] if row_idx < len(rows) else (0, image_height)
            cell_bounds = (col_start, row_start, col_end, row_end)

            # Cluster within this cell
            cell_clusters = self._cluster_within_grid_cell(cell_boxes, cell_bounds)

            for cluster in cell_clusters:
                all_clusters.append({
                    "boxes": cluster,
                    "cell": (col_idx, row_idx),
                    "cell_bounds": cell_bounds,
                })

        # Step 4: Convert clusters to product regions with TIGHT bounding boxes
        product_regions = []

        for cluster_idx, cluster_data in enumerate(all_clusters):
            cluster = cluster_data["boxes"]
            cell_bounds = cluster_data["cell_bounds"]

            if not cluster:
                continue

            # Get tight bbox from cluster boxes (not cell bounds)
            bbox = self._get_cluster_bbox(cluster)

            # Apply minimal padding
            x = max(0, bbox["x"] - self.padding)
            y = max(0, bbox["y"] - self.padding)
            width = bbox["width"] + 2 * self.padding
            height = bbox["height"] + 2 * self.padding

            # Clamp to cell bounds (don't exceed cell)
            cell_x_start, cell_y_start, cell_x_end, cell_y_end = cell_bounds
            x = max(x, cell_x_start)
            y = max(y, cell_y_start)
            if x + width > cell_x_end:
                width = cell_x_end - x
            if y + height > cell_y_end:
                height = cell_y_end - y

            # Clamp to image bounds
            width = min(width, image_width - x)
            height = min(height, image_height - y)

            # Skip if too small
            if width < self.min_product_width or height < self.min_product_height:
                continue

            # Extend upward to capture product image
            # Product images are typically above the text in leaflets
            # Estimate image height based on text cluster height
            text_cluster_height = bbox["height"]
            estimated_image_height = int(text_cluster_height * 0.8)  # Image ~80% of text height

            # Extend y upward but stay within cell bounds
            extended_y = max(cell_y_start, y - estimated_image_height)
            height_increase = y - extended_y
            y = extended_y
            height = height + height_increase

            # Classify boxes for metadata
            texts = [b["text"] for b in cluster]
            types = [self._classify_text_box(b) for b in cluster]

            has_price = "price" in types
            has_name = "name" in types

            product_regions.append({
                "bbox": {
                    "x": int(x),
                    "y": int(y),
                    "width": int(width),
                    "height": int(height),
                },
                "texts": texts,
                "text_count": len(texts),
                "combined_text": " ".join(texts),
                "has_price": has_price,
                "has_name": has_name,
                "cluster_id": cluster_idx,
                "grid_cell": cluster_data["cell"],
            })

        # Sort by position (top-left to bottom-right, row by row)
        product_regions.sort(key=lambda r: (r["bbox"]["y"] // 100, r["bbox"]["x"]))

        logger.info(f"Created {len(product_regions)} product regions from {len(all_clusters)} clusters")
        return product_regions

    def _should_join_cluster(
        self,
        box: Dict[str, Any],
        cluster: List[Dict[str, Any]],
        cluster_bbox: Dict[str, int],
    ) -> bool:
        """
        Determine if a box should join an existing cluster.

        Criteria:
        - Spatially close to cluster
        - Aligned vertically or horizontally with cluster members
        - Would not break cluster compactness
        """
        # Check proximity
        if not self._is_close_to_cluster(box, cluster_bbox):
            return False

        # Check alignment with at least one cluster member
        aligned_with_any = False
        for member in cluster:
            if self._is_vertically_aligned(box, member) or self._is_horizontally_aligned(box, member):
                aligned_with_any = True
                break

        return aligned_with_any

    def _fallback_proximity_clustering(
        self,
        text_boxes: List[Dict[str, Any]],
        image_width: int,
        image_height: int,
    ) -> List[Dict[str, Any]]:
        """
        Fallback clustering when no prices are detected.
        Uses simple proximity-based clustering.
        """
        sorted_boxes = sorted(text_boxes, key=lambda b: (b["y"], b["x"]))

        clusters = []
        used = set()

        for i, box in enumerate(sorted_boxes):
            if i in used:
                continue

            cluster = [box]
            used.add(i)

            cluster_changed = True
            while cluster_changed:
                cluster_changed = False
                cluster_bbox = self._get_cluster_bbox(cluster)

                for j, other_box in enumerate(sorted_boxes):
                    if j in used:
                        continue

                    if self._is_close_to_cluster(other_box, cluster_bbox):
                        test_cluster = cluster + [other_box]
                        if self._is_compact_cluster(test_cluster):
                            cluster.append(other_box)
                            used.add(j)
                            cluster_changed = True

            clusters.append(cluster)

        # Convert to regions
        product_regions = []
        for cluster in clusters:
            bbox = self._get_cluster_bbox(cluster)

            x = max(0, bbox["x"] - self.padding)
            y = max(0, bbox["y"] - self.padding)
            width = min(bbox["width"] + 2 * self.padding, image_width - x)
            height = min(bbox["height"] + 2 * self.padding, image_height - y)

            if width < self.min_product_width or height < self.min_product_height:
                continue

            texts = [b["text"] for b in cluster]

            product_regions.append({
                "bbox": {"x": int(x), "y": int(y), "width": int(width), "height": int(height)},
                "texts": texts,
                "text_count": len(texts),
                "combined_text": " ".join(texts),
                "has_price": False,
                "has_name": True,
            })

        product_regions.sort(key=lambda r: (r["bbox"]["y"], r["bbox"]["x"]))
        return product_regions

    def _get_cluster_bbox(self, cluster: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get bounding box encompassing all boxes in cluster."""
        min_x = min(b["x"] for b in cluster)
        min_y = min(b["y"] for b in cluster)
        max_x = max(b["x"] + b["width"] for b in cluster)
        max_y = max(b["y"] + b["height"] for b in cluster)

        return {
            "x": min_x,
            "y": min_y,
            "width": max_x - min_x,
            "height": max_y - min_y,
        }

    def _is_close_to_cluster(
        self,
        box: Dict[str, Any],
        cluster_bbox: Dict[str, int],
    ) -> bool:
        """Check if a box is close enough to join a cluster."""
        # Expand cluster bbox by min_cluster_gap
        expanded = {
            "x": cluster_bbox["x"] - self.min_cluster_gap,
            "y": cluster_bbox["y"] - self.min_cluster_gap,
            "width": cluster_bbox["width"] + 2 * self.min_cluster_gap,
            "height": cluster_bbox["height"] + 2 * self.min_cluster_gap,
        }

        # Check if box overlaps with expanded cluster
        box_right = box["x"] + box["width"]
        box_bottom = box["y"] + box["height"]
        cluster_right = expanded["x"] + expanded["width"]
        cluster_bottom = expanded["y"] + expanded["height"]

        return not (
            box["x"] > cluster_right or
            box_right < expanded["x"] or
            box["y"] > cluster_bottom or
            box_bottom < expanded["y"]
        )

    def detect_product_regions(
        self,
        image: Union[str, Path, bytes, np.ndarray],
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
        use_visual_detection: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Detect product regions in an image.

        Main entry point that combines text detection, visual boundary detection,
        and clustering for accurate product card extraction.

        OPTIMIZATION: Now creates fresh PaddleOCR instances to avoid state corruption.
        Large images are automatically resized for faster processing.

        Args:
            image: Image to process
            image_width: Image width (auto-detected if not provided)
            image_height: Image height (auto-detected if not provided)
            use_visual_detection: Whether to use visual boundary detection

        Returns:
            List of product regions with bounding boxes
        """
        import concurrent.futures

        # Get image dimensions if not provided
        if image_width is None or image_height is None:
            if isinstance(image, (str, Path)):
                with Image.open(image) as img:
                    image_width, image_height = img.size
            elif isinstance(image, bytes):
                with Image.open(BytesIO(image)) as img:
                    image_width, image_height = img.size
            elif isinstance(image, np.ndarray):
                image_height, image_width = image.shape[:2]

        logger.info(f"[OCR REGIONS] Starting detection on image {image_width}x{image_height}...")
        logger.info(f"[OCR REGIONS] Image type: {type(image)}, visual detection: {use_visual_detection and VISUAL_DETECTION_AVAILABLE}")

        # Step 1: Visual detection FIRST (fast, reliable, doesn't have corruption issues)
        visual_regions = []
        if use_visual_detection and VISUAL_DETECTION_AVAILABLE:
            try:
                logger.info("[OCR REGIONS] Running visual boundary detection...")
                visual_detector = VisualBoundaryDetector()
                visual_regions = visual_detector.detect_product_regions(
                    image, image_width, image_height
                )
                logger.info(f"[OCR REGIONS] Visual detection found {len(visual_regions)} regions")
            except Exception as e:
                logger.warning(f"[OCR REGIONS] Visual boundary detection failed: {e}")

        # Step 2: OCR detection with timeout
        # NOTE: detect_text_boxes now creates a FRESH PaddleOCR instance to avoid corruption
        # and automatically resizes large images
        text_boxes = []
        try:
            logger.info("[OCR REGIONS] Running PaddleOCR text detection (90s timeout)...")

            # Use ThreadPoolExecutor with timeout to prevent OCR from blocking forever
            # Increased to 90s because we now create fresh instances each time
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.detect_text_boxes, image)
                try:
                    text_boxes = future.result(timeout=90)  # 90 second timeout
                    logger.info(f"[OCR REGIONS] OCR detection complete: {len(text_boxes)} text boxes found")
                except concurrent.futures.TimeoutError:
                    logger.warning("[OCR REGIONS] OCR detection TIMEOUT after 90s - using visual regions only")
                    text_boxes = []
        except Exception as e:
            logger.warning(f"[OCR REGIONS] OCR detection failed: {type(e).__name__}: {e}")

        if not text_boxes:
            # If no text detected but visual regions found, return those
            if visual_regions:
                logger.info(f"[OCR REGIONS] No OCR text, returning {len(visual_regions)} visual-only regions")
                return [
                    {
                        "bbox": r["bbox"],
                        "texts": [],
                        "text_count": 0,
                        "combined_text": "",
                        "has_price": False,
                        "has_name": False,
                        "source": "visual",
                    }
                    for r in visual_regions
                ]
            logger.warning("[OCR REGIONS] No text boxes and no visual regions - returning empty")
            return []

        # Step 3: Combine visual regions with OCR text using hybrid approach
        if visual_regions and len(visual_regions) >= 2:
            regions = self._hybrid_clustering(
                text_boxes, visual_regions, image_width, image_height
            )

            # FALLBACK: If hybrid clustering produced too many empty-text regions,
            # the layout assumptions were likely wrong for this leaflet.
            # Fall back to OCR-only clustering which always produces text-bearing regions.
            if regions:
                text_regions = [r for r in regions if r.get("combined_text", "").strip()]
                text_ratio = len(text_regions) / len(regions)
                if text_ratio < 0.5:
                    logger.warning(
                        f"[OCR REGIONS] Hybrid clustering produced only {len(text_regions)}/{len(regions)} "
                        f"text-bearing regions ({text_ratio:.0%}). Layout assumptions likely wrong. "
                        f"Falling back to OCR-only clustering."
                    )
                    ocr_only_regions = self.cluster_text_boxes(text_boxes, image_width, image_height)
                    if ocr_only_regions and len(ocr_only_regions) >= len(text_regions):
                        regions = ocr_only_regions
                        logger.info(f"[OCR REGIONS] OCR-only fallback produced {len(regions)} text-bearing regions")
                    else:
                        logger.info(f"[OCR REGIONS] OCR-only fallback produced fewer regions, keeping hybrid results")
        else:
            # Fall back to grid-aware clustering based on OCR text only
            regions = self.cluster_text_boxes(text_boxes, image_width, image_height)

        # FALLBACK: If clustering produced 0 results, use individual text boxes as regions
        # This ensures text-based matching can still work
        if not regions and text_boxes:
            logger.info(f"[OCR REGIONS] Clustering produced 0 regions, using {len(text_boxes)} text boxes as fallback regions")
            regions = []
            for box in text_boxes:
                text = box.get("text", "")
                box_type = self._classify_text_box(box)
                regions.append({
                    "bbox": {
                        "x": int(box["x"]),
                        "y": int(box["y"]),
                        "width": int(box["width"]),
                        "height": int(box["height"]),
                    },
                    "texts": [text],
                    "text_count": 1,
                    "combined_text": text,
                    "has_price": box_type == "price",
                    "has_name": box_type == "name",
                    "source": "ocr_text_box",
                })

        logger.info(f"[OCR REGIONS] Returning {len(regions)} regions")
        return regions

    def _hybrid_clustering(
        self,
        text_boxes: List[Dict[str, Any]],
        visual_regions: List[Dict[str, Any]],
        image_width: int,
        image_height: int,
    ) -> List[Dict[str, Any]]:
        """
        Combine visual regions with OCR text boxes for better clustering.

        IMPROVED STRATEGY for complete product cards:
        1. Estimate expected product card size from page dimensions
        2. Merge nearby small visual regions into product-card-sized regions
        3. Filter out oversized regions (> 20% of image)
        4. Assign text boxes to merged regions
        5. Expand regions to fully contain their text

        A complete product card should include: product image, name, price, etc.
        Typical size: 250-800px wide, 300-1200px tall (at 300 DPI)

        Args:
            text_boxes: OCR detected text boxes
            visual_regions: Visually detected regions
            image_width: Image width
            image_height: Image height

        Returns:
            List of product regions (complete product cards)
        """
        logger.info(f"[HYBRID] Starting hybrid clustering: {len(text_boxes)} text boxes, {len(visual_regions)} visual regions")

        image_area = image_width * image_height

        # Step 1: Infer layout from visual regions (data-driven, not hardcoded)
        estimated_cols, estimated_rows, expected_card_width, expected_card_height = \
            self._infer_layout_from_regions(visual_regions, image_width, image_height)

        # Minimum size for a complete product card (must contain image + text)
        min_card_width = max(200, int(expected_card_width * 0.35))
        min_card_height = max(250, int(expected_card_height * 0.35))

        # Maximum size derived from detected layout (not hardcoded)
        # Allow up to 2x expected card size to handle layout variation
        max_card_area = expected_card_width * expected_card_height * 2.5
        max_region_area = min(image_area * 0.40, max_card_area)
        max_region_width = min(image_width * 0.90, expected_card_width * 2.0)
        max_region_height = min(image_height * 0.60, expected_card_height * 2.0)

        logger.info(f"[HYBRID] Expected card size: ~{int(expected_card_width)}x{int(expected_card_height)}, min: {min_card_width}x{min_card_height}")

        # Step 2: Classify and merge small visual regions
        small_regions = []  # Regions smaller than minimum product card size
        valid_regions = []  # Product-card-sized regions
        oversized_regions = []  # Regions larger than max

        for i, vr in enumerate(visual_regions):
            bbox = vr["bbox"]
            area = bbox["width"] * bbox["height"]

            is_oversized = (
                area > max_region_area or
                bbox["width"] > max_region_width or
                bbox["height"] > max_region_height
            )

            is_too_small = (
                bbox["width"] < min_card_width or
                bbox["height"] < min_card_height
            )

            if is_oversized:
                oversized_regions.append((i, vr))
            elif is_too_small:
                small_regions.append((i, vr))
            else:
                valid_regions.append((i, vr))

        logger.info(f"[HYBRID] Regions: {len(valid_regions)} valid, {len(small_regions)} small (need merge), {len(oversized_regions)} oversized")

        # Step 3: Merge nearby small regions into product-card-sized regions
        # This creates complete product cards from fragmented visual regions
        merged_small = self._merge_nearby_regions(
            [vr for _, vr in small_regions],
            merge_distance=50,  # Pixels apart to consider merging
            min_result_width=min_card_width,
            min_result_height=min_card_height,
        )

        # Add successfully merged regions to valid_regions
        # Check both min AND max size to prevent oversized merged regions
        for merged in merged_small:
            bbox = merged["bbox"]
            merged_area = bbox["width"] * bbox["height"]
            is_valid_size = (
                bbox["width"] >= min_card_width and
                bbox["height"] >= min_card_height and
                bbox["width"] <= max_region_width and
                bbox["height"] <= max_region_height and
                merged_area <= max_region_area
            )
            if is_valid_size:
                valid_regions.append((len(visual_regions) + len(valid_regions), merged))
                logger.debug(f"[HYBRID] Merged region: {bbox['width']}x{bbox['height']}")
            elif bbox["width"] >= min_card_width and bbox["height"] >= min_card_height:
                logger.debug(f"[HYBRID] Merged region too large: {bbox['width']}x{bbox['height']}, skipping")

        logger.info(f"[HYBRID] After merging: {len(valid_regions)} valid regions")

        # Step 4: Assign text boxes to valid regions
        region_assignments = {}  # region index -> list of text boxes
        unassigned_boxes = []

        for text_box in text_boxes:
            text_bbox = {
                "x": text_box["x"],
                "y": text_box["y"],
                "width": text_box["width"],
                "height": text_box["height"],
            }

            best_region_idx = None
            best_overlap = 0

            for idx, (_, vr) in enumerate(valid_regions):
                overlap = self._bbox_overlap(text_bbox, vr["bbox"])
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_region_idx = idx

            if best_region_idx is not None and best_overlap > 0.1:
                if best_region_idx not in region_assignments:
                    region_assignments[best_region_idx] = []
                region_assignments[best_region_idx].append(text_box)
            else:
                unassigned_boxes.append(text_box)

        logger.info(f"[HYBRID] Assigned text to {len(region_assignments)} regions, {len(unassigned_boxes)} unassigned")

        # Step 5: Build product regions, expanding bbox to include nearby text
        # IMPORTANT: Cap expansion to max_region_width/max_region_height to prevent
        # oversized regions on large images where distant text boxes get assigned
        product_regions = []

        for idx, boxes in region_assignments.items():
            _, vr = valid_regions[idx]
            visual_bbox = vr["bbox"]

            # Classify all text boxes first (needed for combined_text regardless of bbox)
            for box in boxes:
                box["_type"] = self._classify_text_box(box)

            # Start with visual region bbox
            x_min = visual_bbox["x"]
            y_min = visual_bbox["y"]
            x_max = visual_bbox["x"] + visual_bbox["width"]
            y_max = visual_bbox["y"] + visual_bbox["height"]

            # Only expand for text boxes whose center is within a reasonable
            # distance of the visual region (max_region_width/height acts as cap)
            vr_cx = visual_bbox["x"] + visual_bbox["width"] / 2
            vr_cy = visual_bbox["y"] + visual_bbox["height"] / 2
            expand_radius_x = max_region_width / 2
            expand_radius_y = max_region_height / 2

            for box in boxes:
                box_cx = box["x"] + box["width"] / 2
                box_cy = box["y"] + box["height"] / 2
                # Only expand bbox for text boxes close to the visual region center
                if (abs(box_cx - vr_cx) <= expand_radius_x and
                        abs(box_cy - vr_cy) <= expand_radius_y):
                    x_min = min(x_min, box["x"])
                    y_min = min(y_min, box["y"])
                    x_max = max(x_max, box["x"] + box["width"])
                    y_max = max(y_max, box["y"] + box["height"])

            # Add padding
            padding = 10
            x_min = max(0, x_min - padding)
            y_min = max(0, y_min - padding)
            x_max = min(image_width, x_max + padding)
            y_max = min(image_height, y_max + padding)

            width = x_max - x_min
            height = y_max - y_min

            # Final safety clamp: if expanded region still exceeds max size,
            # clamp to max dimensions centered on the visual region
            if width > max_region_width or height > max_region_height:
                logger.warning(
                    f"[HYBRID] Region expanded to {int(width)}x{int(height)} "
                    f"(max {int(max_region_width)}x{int(max_region_height)}), clamping"
                )
                if width > max_region_width:
                    excess = width - max_region_width
                    x_min += excess / 2
                    x_max -= excess / 2
                    width = max_region_width
                if height > max_region_height:
                    excess = height - max_region_height
                    y_min += excess / 2
                    y_max -= excess / 2
                    height = max_region_height

            texts = [b["text"] for b in boxes]
            types = [b.get("_type", "other") for b in boxes]

            product_regions.append({
                "bbox": {
                    "x": int(x_min),
                    "y": int(y_min),
                    "width": int(width),
                    "height": int(height),
                },
                "texts": texts,
                "text_count": len(texts),
                "combined_text": " ".join(texts),
                "has_price": "price" in types,
                "has_name": "name" in types,
                "source": "hybrid",
            })

        # Step 6: Add valid visual regions without text (might be image-only products)
        used_indices = set(region_assignments.keys())
        for idx, (_, vr) in enumerate(valid_regions):
            if idx in used_indices:
                continue

            bbox = vr["bbox"]
            # Only include if it's a reasonable product card size
            if bbox["width"] >= min_card_width and bbox["height"] >= min_card_height:
                product_regions.append({
                    "bbox": bbox.copy(),
                    "texts": [],
                    "text_count": 0,
                    "combined_text": "",
                    "has_price": False,
                    "has_name": False,
                    "source": "visual_only",
                })

        # Step 7: Use grid-based clustering for unassigned text
        if unassigned_boxes:
            logger.info(f"[HYBRID] Grid clustering for {len(unassigned_boxes)} unassigned text boxes")
            grid_regions = self._grid_cluster_text_boxes(
                unassigned_boxes, image_width, image_height,
                min_region_width=min_card_width,
                min_region_height=min_card_height,
            )
            for region in grid_regions:
                region["source"] = "grid_fallback"
                product_regions.append(region)
            logger.info(f"[HYBRID] Grid clustering created {len(grid_regions)} regions")

        # Step 8: Remove overlapping regions
        product_regions = self._deduplicate_regions(product_regions, overlap_threshold=0.5)

        # Sort by position (reading order)
        product_regions.sort(key=lambda r: (r["bbox"]["y"] // 100, r["bbox"]["x"]))

        logger.info(f"[HYBRID] Final: {len(product_regions)} product card regions")
        return product_regions

    def _merge_nearby_regions(
        self,
        regions: List[Dict[str, Any]],
        merge_distance: int = 50,
        min_result_width: int = 200,
        min_result_height: int = 250,
    ) -> List[Dict[str, Any]]:
        """
        Merge nearby small regions into larger product-card-sized regions.

        This is critical for creating complete product cards from fragmented
        visual regions (e.g., separate regions for image, text, price).
        """
        if not regions:
            return []

        # Sort regions by position (top-left to bottom-right)
        sorted_regions = sorted(regions, key=lambda r: (r["bbox"]["y"], r["bbox"]["x"]))

        merged = []
        used = set()

        for i, region1 in enumerate(sorted_regions):
            if i in used:
                continue

            bbox1 = region1["bbox"].copy()

            # Try to merge with nearby regions
            for j, region2 in enumerate(sorted_regions):
                if i == j or j in used:
                    continue

                bbox2 = region2["bbox"]

                # Check if regions are close enough to merge
                # (horizontally or vertically adjacent)
                h_gap = max(0, max(bbox1["x"], bbox2["x"]) -
                           min(bbox1["x"] + bbox1["width"], bbox2["x"] + bbox2["width"]))
                v_gap = max(0, max(bbox1["y"], bbox2["y"]) -
                           min(bbox1["y"] + bbox1["height"], bbox2["y"] + bbox2["height"]))

                if h_gap <= merge_distance and v_gap <= merge_distance:
                    # Merge bboxes
                    new_x = min(bbox1["x"], bbox2["x"])
                    new_y = min(bbox1["y"], bbox2["y"])
                    new_x2 = max(bbox1["x"] + bbox1["width"], bbox2["x"] + bbox2["width"])
                    new_y2 = max(bbox1["y"] + bbox1["height"], bbox2["y"] + bbox2["height"])

                    bbox1 = {
                        "x": new_x,
                        "y": new_y,
                        "width": new_x2 - new_x,
                        "height": new_y2 - new_y,
                    }
                    used.add(j)

            used.add(i)
            merged.append({
                "bbox": bbox1,
                "confidence": region1.get("confidence", 0.5),
            })

        return merged

    def _grid_cluster_text_boxes(
        self,
        text_boxes: List[Dict[str, Any]],
        image_width: int,
        image_height: int,
        min_region_width: int = 200,
        min_region_height: int = 250,
    ) -> List[Dict[str, Any]]:
        """
        Cluster text boxes into product-card-sized grid cells.

        Unlike the basic cluster_text_boxes, this ensures each resulting
        region meets minimum product card dimensions.
        """
        if not text_boxes:
            return []

        # Use a grid that creates reasonable product card sizes
        # Aim for cells that are at least min_region_width x min_region_height
        cols = max(1, image_width // min_region_width)
        rows = max(1, image_height // min_region_height)

        cell_width = image_width / cols
        cell_height = image_height / rows

        # Assign text boxes to grid cells
        cell_assignments = {}  # (row, col) -> [text_boxes]

        for box in text_boxes:
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2

            col = min(cols - 1, int(cx / cell_width))
            row = min(rows - 1, int(cy / cell_height))

            key = (row, col)
            if key not in cell_assignments:
                cell_assignments[key] = []
            cell_assignments[key].append(box)

        # Build regions from non-empty cells
        regions = []
        for (row, col), boxes in cell_assignments.items():
            if not boxes:
                continue

            # Calculate bounding box that encompasses all text + padding
            x_min = min(b["x"] for b in boxes)
            y_min = min(b["y"] for b in boxes)
            x_max = max(b["x"] + b["width"] for b in boxes)
            y_max = max(b["y"] + b["height"] for b in boxes)

            # Expand to at least minimum product card size
            current_width = x_max - x_min
            current_height = y_max - y_min

            if current_width < min_region_width:
                expand = (min_region_width - current_width) / 2
                x_min = max(0, x_min - expand)
                x_max = min(image_width, x_max + expand)

            if current_height < min_region_height:
                expand = (min_region_height - current_height) / 2
                y_min = max(0, y_min - expand)
                y_max = min(image_height, y_max + expand)

            # Add padding
            padding = 15
            x_min = max(0, x_min - padding)
            y_min = max(0, y_min - padding)
            x_max = min(image_width, x_max + padding)
            y_max = min(image_height, y_max + padding)

            # Classify text boxes
            for box in boxes:
                box["_type"] = self._classify_text_box(box)

            texts = [b["text"] for b in boxes]
            types = [b.get("_type", "other") for b in boxes]

            regions.append({
                "bbox": {
                    "x": int(x_min),
                    "y": int(y_min),
                    "width": int(x_max - x_min),
                    "height": int(y_max - y_min),
                },
                "texts": texts,
                "text_count": len(texts),
                "combined_text": " ".join(texts),
                "has_price": "price" in types,
                "has_name": "name" in types,
            })

        return regions

    def _deduplicate_regions(
        self,
        regions: List[Dict[str, Any]],
        overlap_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate/overlapping regions.

        Priority: hybrid > visual_only > grid_fallback
        """
        if len(regions) <= 1:
            return regions

        # Sort by source priority (hybrid first, then visual_only, then grid_fallback)
        source_priority = {"hybrid": 0, "visual_only": 1, "grid_fallback": 2, "ocr_unassigned": 3}
        sorted_regions = sorted(regions, key=lambda r: source_priority.get(r.get("source", ""), 4))

        kept_regions = []
        for region in sorted_regions:
            is_duplicate = False

            for kept in kept_regions:
                # Calculate IoU
                overlap = self._calculate_iou(region["bbox"], kept["bbox"])
                if overlap > overlap_threshold:
                    is_duplicate = True
                    logger.debug(f"[DEDUP] Removing {region.get('source')} region (IoU={overlap:.2f} with {kept.get('source')})")
                    break

            if not is_duplicate:
                kept_regions.append(region)

        logger.info(f"[DEDUP] Kept {len(kept_regions)}/{len(regions)} regions after deduplication")
        return kept_regions

    def _calculate_iou(self, bbox1: Dict, bbox2: Dict) -> float:
        """Calculate Intersection over Union of two bounding boxes."""
        x1 = max(bbox1["x"], bbox2["x"])
        y1 = max(bbox1["y"], bbox2["y"])
        x2 = min(bbox1["x"] + bbox1["width"], bbox2["x"] + bbox2["width"])
        y2 = min(bbox1["y"] + bbox1["height"], bbox2["y"] + bbox2["height"])

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        area1 = bbox1["width"] * bbox1["height"]
        area2 = bbox2["width"] * bbox2["height"]
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def _bbox_overlap(self, bbox1: Dict, bbox2: Dict) -> float:
        """Calculate overlap ratio of bbox1 within bbox2."""
        x1 = max(bbox1["x"], bbox2["x"])
        y1 = max(bbox1["y"], bbox2["y"])
        x2 = min(bbox1["x"] + bbox1["width"], bbox2["x"] + bbox2["width"])
        y2 = min(bbox1["y"] + bbox1["height"], bbox2["y"] + bbox2["height"])

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        bbox1_area = bbox1["width"] * bbox1["height"]

        return intersection / bbox1_area if bbox1_area > 0 else 0.0

    def match_products_to_regions(
        self,
        products: List[Dict[str, Any]],
        regions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Match VLM-extracted products to detected regions.

        Uses text similarity when regions have text (OCR-based),
        or positional matching when regions have no text (visual-based).

        Args:
            products: List of products from VLM extraction
            regions: List of detected regions (OCR or visual)

        Returns:
            Products with updated bounding boxes from detected regions
        """
        logger.info(f"[MATCH] match_products_to_regions called: {len(products)} products, {len(regions)} regions")
        if not regions:
            logger.warning("[MATCH] No regions provided, returning products with VLM estimates")
            return products

        # Check if regions have text (OCR) or not (visual-only)
        regions_with_text = [r for r in regions if r.get("combined_text", "").strip()]
        regions_have_text = len(regions_with_text) > 0

        logger.info(f"[MATCH] Regions with text: {len(regions_with_text)}/{len(regions)}, using {'TEXT' if regions_have_text else 'POSITION'} matching")

        # Log sample regions for debugging
        for i, region in enumerate(regions[:3]):
            text_preview = region.get("combined_text", "")[:60].replace("\n", " ")
            logger.info(f"[MATCH] Sample region {i}: text='{text_preview}...', bbox={region.get('bbox')}")

        if regions_have_text:
            matched = self._match_by_text_similarity(products, regions)

            # Spatial fallback: for products that text matching couldn't match,
            # try matching against unused regions by spatial proximity
            unmatched = [p for p in matched if p.get("bbox_source") == "vlm_estimated"]
            if unmatched:
                # Collect region indices already used by text matching
                used_indices = set()
                for p in matched:
                    idx = p.pop("_matched_region_idx", None)
                    if idx is not None:
                        used_indices.add(idx)

                remaining_regions = [r for j, r in enumerate(regions) if j not in used_indices]
                if remaining_regions:
                    logger.info(
                        f"[MATCH] Spatial fallback: {len(unmatched)} unmatched products, "
                        f"{len(remaining_regions)} unused regions"
                    )
                    self._match_by_position(unmatched, remaining_regions)
                    spatial_matched = sum(1 for p in unmatched if p.get("bbox_source") != "vlm_estimated")
                    logger.info(f"[MATCH] Spatial fallback matched {spatial_matched} additional products")
            else:
                # Clean up internal tracking field
                for p in matched:
                    p.pop("_matched_region_idx", None)

            return matched
        else:
            return self._match_by_position(products, regions)

    def _match_by_text_similarity(
        self,
        products: List[Dict[str, Any]],
        regions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Match products to regions using text similarity with multiple strategies.

        Matching strategies (in order of confidence):
        1. Product code matching (if code found in region, very high confidence)
        2. Price matching (prices are very specific, high confidence)
        3. Exact word overlap (name/brand words found in region)
        4. Substring matching (for partial product names)
        5. Quantity/size matching (bonus for matching quantity/units)

        Score weights:
        - Product code match: +0.6 (product codes are unique identifiers)
        - Price match: +0.4 (prices are very specific)
        - Text similarity: 0.0-0.8 (word overlap or substring)
        - Quantity match: +0.1 (additional confirmation)

        Minimum threshold: 0.35 (to avoid wrong matches)
        """
        import re as re_module

        matched_products = []
        used_regions = set()

        # Minimum threshold for accepting a match (increased from 0.25 to reduce wrong matches)
        MATCH_THRESHOLD = 0.35

        logger.info(f"[TEXT-MATCH] Starting text similarity matching: {len(products)} products, {len(regions)} regions")

        for product in products:
            product_name = product.get("product_name", "").lower()
            brand = product.get("brand", "").lower() if product.get("brand") else ""
            discounted_price = product.get("discounted_price")
            regular_price = product.get("regular_price")
            product_code = product.get("product_code", "").lower() if product.get("product_code") else ""
            quantity = product.get("quantity")
            units = product.get("units", "").lower() if product.get("units") else ""
            size = product.get("size", "").lower() if product.get("size") else ""

            search_text = f"{brand} {product_name}".strip()

            best_match = None
            best_score = 0
            best_match_reason = ""

            for i, region in enumerate(regions):
                if i in used_regions:
                    continue

                region_text = region.get("combined_text", "").lower()
                score = 0.0
                match_reasons = []

                # ==== Strategy 1: Product Code Matching (HIGHEST PRIORITY) ====
                # Product codes/SKUs are unique identifiers
                if product_code and len(product_code) >= 3:
                    # Normalize product code (remove spaces, dashes)
                    normalized_code = re_module.sub(r'[\s\-]', '', product_code)
                    normalized_region = re_module.sub(r'[\s\-]', '', region_text)

                    if normalized_code in normalized_region:
                        score += 0.6
                        match_reasons.append("code")

                # ==== Strategy 2: Price Matching (HIGH PRIORITY) ====
                # Prices are very specific - finding exact price is strong signal
                price_to_check = discounted_price or regular_price
                if price_to_check:
                    try:
                        price_float = float(price_to_check)
                        # Check multiple formats: "12.99", "12,99", "1299"
                        price_formats = [
                            str(price_to_check),
                            str(price_to_check).replace(".", ","),
                            str(price_to_check).replace(".", ""),
                            f"{price_float:.2f}",
                            f"{price_float:.2f}".replace(".", ","),
                        ]

                        for pf in price_formats:
                            if pf in region_text:
                                score += 0.4
                                match_reasons.append("price")
                                break
                    except (ValueError, TypeError):
                        pass

                # ==== Strategy 3: Word Overlap Scoring ====
                search_words = set(w for w in search_text.split() if len(w) > 2)
                region_words = set(w for w in region_text.split() if len(w) > 2)

                word_overlap = 0
                if search_words:
                    overlap_count = len(search_words & region_words)
                    word_overlap = overlap_count / len(search_words)
                    if word_overlap > 0:
                        match_reasons.append(f"words({overlap_count}/{len(search_words)})")

                # ==== Strategy 4: Substring Matching ====
                substring_score = 0
                if len(product_name) > 3:
                    # Check if significant parts of product name appear in region
                    name_parts = [p for p in product_name.split() if len(p) > 3]
                    matches = sum(1 for part in name_parts if part in region_text)
                    if name_parts:
                        substring_score = matches / len(name_parts)
                        if substring_score > 0 and f"words" not in str(match_reasons):
                            match_reasons.append(f"substr({matches}/{len(name_parts)})")

                # Add text similarity score (use best of word overlap or substring)
                text_score = max(word_overlap, substring_score) * 0.8
                score += text_score

                # ==== Strategy 5: Quantity/Size Matching (BONUS) ====
                if quantity and units:
                    qty_str = f"{quantity}{units}"
                    qty_str_space = f"{quantity} {units}"
                    if qty_str.lower() in region_text or qty_str_space.lower() in region_text:
                        score += 0.1
                        match_reasons.append("qty")
                elif size:
                    if size in region_text:
                        score += 0.1
                        match_reasons.append("size")

                # ==== Update Best Match ====
                if score > best_score:
                    best_score = score
                    best_match = (i, region)
                    best_match_reason = "+".join(match_reasons) if match_reasons else "none"

            # If good match found, use OCR bounding box
            if best_match and best_score >= MATCH_THRESHOLD:
                idx, region = best_match
                used_regions.add(idx)
                product["bounding_box"] = region["bbox"]
                product["bbox_source"] = "ocr_text_match"
                product["bbox_confidence"] = best_score
                product["_matched_region_idx"] = idx
                logger.info(f"[TEXT-MATCH] MATCHED '{search_text[:40]}' -> region {idx} ({best_match_reason}, score={best_score:.2f})")
            else:
                product["bbox_source"] = "vlm_estimated"
                logger.info(f"[TEXT-MATCH] NO MATCH for '{search_text[:40]}' (best_score={best_score:.2f} < {MATCH_THRESHOLD})")

            matched_products.append(product)

        matched_count = sum(1 for p in matched_products if p.get("bbox_source") == "ocr_text_match")
        logger.info(f"[TEXT-MATCH] Text matching complete: {matched_count}/{len(products)} products matched to OCR regions")

        return matched_products

    def _infer_layout_from_regions(
        self,
        visual_regions: List[Dict[str, Any]],
        image_width: int,
        image_height: int,
    ) -> tuple:
        """
        Infer grid layout (columns, rows) from visual region positions.

        Instead of hardcoding 3 cols / 4 rows, analyze the actual regions
        to detect the layout structure by clustering region center coordinates.

        Returns:
            Tuple of (estimated_cols, estimated_rows, expected_card_width, expected_card_height)
        """
        if not visual_regions or len(visual_regions) < 2:
            # Not enough regions to infer - use conservative defaults
            return 3, 4, image_width / 3, image_height / 4

        # Collect region centers and dimensions
        centers_x = []
        centers_y = []
        widths = []
        heights = []

        for vr in visual_regions:
            bbox = vr["bbox"]
            cx = bbox["x"] + bbox["width"] / 2
            cy = bbox["y"] + bbox["height"] / 2
            centers_x.append(cx)
            centers_y.append(cy)
            widths.append(bbox["width"])
            heights.append(bbox["height"])

        # Detect columns by clustering X-centers (gap > 15% of width = new column)
        estimated_cols = self._count_clusters(sorted(centers_x), image_width * 0.15)
        # Detect rows by clustering Y-centers (gap > 10% of height = new row)
        estimated_rows = self._count_clusters(sorted(centers_y), image_height * 0.10)

        # Clamp to reasonable values
        estimated_cols = max(1, min(6, estimated_cols))
        estimated_rows = max(1, min(8, estimated_rows))

        # Use median region size as expected card size (more robust than mean)
        median_width = float(np.median(widths))
        median_height = float(np.median(heights))

        # Cross-validate with grid-derived sizes and use the larger
        # to avoid filtering out valid regions
        grid_card_width = image_width / estimated_cols
        grid_card_height = image_height / estimated_rows

        expected_card_width = max(median_width, grid_card_width * 0.6)
        expected_card_height = max(median_height, grid_card_height * 0.6)

        logger.info(
            f"[LAYOUT] Inferred layout: {estimated_cols} cols x {estimated_rows} rows, "
            f"expected card ~{int(expected_card_width)}x{int(expected_card_height)} "
            f"(median region: {int(median_width)}x{int(median_height)}, "
            f"from {len(visual_regions)} visual regions)"
        )

        return estimated_cols, estimated_rows, expected_card_width, expected_card_height

    def _count_clusters(self, sorted_values: List[float], min_gap: float) -> int:
        """
        Count clusters in sorted values by detecting gaps.

        Values separated by more than min_gap are considered different clusters.
        """
        if not sorted_values:
            return 1

        clusters = 1
        for i in range(1, len(sorted_values)):
            if sorted_values[i] - sorted_values[i - 1] > min_gap:
                clusters += 1

        return clusters

    def _match_by_position(
        self,
        products: List[Dict[str, Any]],
        regions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Match products to regions using spatial proximity.

        When text matching isn't available, use two strategies:
        1. IoU matching: if products have VLM-estimated bounding boxes, find the
           region with the highest spatial overlap (for grid-path extraction).
        2. Reading-order matching: for products without VLM bboxes, match to
           remaining regions in reading order (top-to-bottom, left-to-right).

        Unlike the previous approach, this does NOT filter regions by hardcoded
        size expectations. All regions are candidates.
        """
        if not regions:
            logger.info("[POS-MATCH] No regions to match")
            return products

        used_regions = set()

        # Detect reading-order row grouping from actual region positions
        all_y = [r["bbox"]["y"] for r in regions]
        row_gap = max(50, (max(all_y) - min(all_y)) / max(1, len(set(all_y)) - 1) * 0.4) if len(all_y) > 1 else 300

        def reading_order_key(region):
            bbox = region["bbox"]
            row = int(bbox["y"] / row_gap)
            return (row, bbox["x"])

        # Track which products we match in this call
        matched_in_this_call = set()

        # Pass 1: IoU matching for products that have VLM bounding boxes
        iou_matched = 0
        for i, product in enumerate(products):
            vlm_bbox = product.get("bounding_box")
            if vlm_bbox is None:
                continue

            best_region_idx = None
            best_score = 0

            for j, region in enumerate(regions):
                if j in used_regions:
                    continue

                iou = self._calculate_iou(vlm_bbox, region["bbox"])

                # Also check if VLM bbox center falls inside this region
                vlm_cx = vlm_bbox["x"] + vlm_bbox["width"] / 2
                vlm_cy = vlm_bbox["y"] + vlm_bbox["height"] / 2
                r = region["bbox"]
                center_in_region = (
                    r["x"] <= vlm_cx <= r["x"] + r["width"]
                    and r["y"] <= vlm_cy <= r["y"] + r["height"]
                )

                score = iou + (0.3 if center_in_region else 0)

                if score > best_score:
                    best_score = score
                    best_region_idx = j

            if best_region_idx is not None and best_score > 0.05:
                used_regions.add(best_region_idx)
                product["bounding_box"] = regions[best_region_idx]["bbox"]
                product["bbox_source"] = "visual_iou_match"
                product["bbox_confidence"] = min(0.85, best_score)
                matched_in_this_call.add(i)
                iou_matched += 1
                logger.debug(
                    f"[POS-MATCH] IoU matched '{product.get('product_name', '')[:30]}' "
                    f"-> region {best_region_idx} (score={best_score:.2f})"
                )

        if iou_matched > 0:
            logger.info(f"[POS-MATCH] IoU pass: {iou_matched} products matched")

        # Pass 2: Reading-order matching for products not matched in Pass 1
        remaining_regions = sorted(
            [(j, r) for j, r in enumerate(regions) if j not in used_regions],
            key=lambda jr: reading_order_key(jr[1])
        )

        remaining_idx = 0
        order_matched = 0
        for i, product in enumerate(products):
            # Skip products already matched in Pass 1 of THIS call
            if i in matched_in_this_call:
                continue

            # Assign next available region in reading order
            if remaining_idx < len(remaining_regions):
                j, region = remaining_regions[remaining_idx]
                product["bounding_box"] = region["bbox"]
                product["bbox_source"] = "visual_position_match"
                product["bbox_confidence"] = 0.5
                used_regions.add(j)
                remaining_idx += 1
                order_matched += 1
            else:
                if product.get("bbox_source") != "vlm_estimated":
                    product["bbox_source"] = "no_match"

        matched_count = iou_matched + order_matched
        logger.info(f"[POS-MATCH] Position matching complete: {matched_count}/{len(products)} matched "
                     f"(IoU: {iou_matched}, reading-order: {order_matched})")

        return products


# Singleton instance
_detector: Optional[PaddleOCRDetector] = None


def get_paddle_ocr_detector() -> PaddleOCRDetector:
    """Get or create the PaddleOCR detector singleton."""
    global _detector
    if _detector is None:
        _detector = PaddleOCRDetector()
    return _detector


# Check if PaddleOCR is available
def is_paddle_ocr_available() -> bool:
    """Check if PaddleOCR is installed and available."""
    try:
        from paddleocr import PaddleOCR
        return True
    except ImportError:
        return False
