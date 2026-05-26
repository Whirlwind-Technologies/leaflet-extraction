"""
OCR-Based Bounding Box Detection Module.

This module uses OCR (EasyOCR) to locate product text on page images
and build bounding boxes around the detected regions.

The approach:
1. Run OCR on the entire page image to get all text with coordinates
2. For each product extracted by VLM, search for its text in OCR results
3. Build a bounding box that encompasses all found text regions for that product
4. Use position_hint as fallback for grid-based estimation if OCR fails

Example Usage:
    from app.core.image_processing.ocr_bbox_detector import OCRBoundingBoxDetector

    detector = OCRBoundingBoxDetector()
    products_with_boxes = await detector.detect_bounding_boxes(
        image_path="/path/to/page.png",
        products=extracted_products
    )
"""

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image

from app.core.extraction.schemas import BoundingBox, ExtractedProduct

logger = logging.getLogger(__name__)


# Lazy load EasyOCR to avoid import overhead
_ocr_reader = None


def get_ocr_reader():
    """Get or create the EasyOCR reader singleton (lazy loading)."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            # Support Slovenian, Croatian, Serbian, English, German, Italian
            _ocr_reader = easyocr.Reader(
                ['sl', 'hr', 'rs_cyrillic', 'en', 'de', 'it'],
                gpu=False,  # Use CPU for stability in production
                verbose=False
            )
            logger.info("EasyOCR reader initialized successfully")
        except ImportError:
            logger.error("EasyOCR not installed. Install with: pip install easyocr")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            raise
    return _ocr_reader


@dataclass
class OCRResult:
    """A single OCR detection result."""
    text: str
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    confidence: float

    @property
    def x(self) -> int:
        return self.bbox[0]

    @property
    def y(self) -> int:
        return self.bbox[1]

    @property
    def width(self) -> int:
        return self.bbox[2]

    @property
    def height(self) -> int:
        return self.bbox[3]

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


class OCRBoundingBoxDetector:
    """
    Detects bounding boxes for products using OCR text localization.

    This class uses EasyOCR to find text on the page and then matches
    product data (name, brand, prices) to build accurate bounding boxes.
    """

    def __init__(
        self,
        min_text_confidence: float = 0.3,
        text_match_threshold: float = 0.6,
        padding_percent: float = 0.02,  # 2% padding around detected region
        min_bbox_width: int = 100,
        min_bbox_height: int = 100,
    ):
        """
        Initialize the OCR bounding box detector.

        Args:
            min_text_confidence: Minimum OCR confidence to consider a text region
            text_match_threshold: Minimum similarity for text matching (0-1)
            padding_percent: Padding around detected region as percentage of image
            min_bbox_width: Minimum bounding box width in pixels
            min_bbox_height: Minimum bounding box height in pixels
        """
        self.min_text_confidence = min_text_confidence
        self.text_match_threshold = text_match_threshold
        self.padding_percent = padding_percent
        self.min_bbox_width = min_bbox_width
        self.min_bbox_height = min_bbox_height

        self._ocr_cache: dict = {}  # Cache OCR results by image path

    def _convert_easyocr_bbox(self, bbox_points: list) -> Tuple[int, int, int, int]:
        """
        Convert EasyOCR bbox format to (x, y, width, height).

        EasyOCR returns bounding boxes as [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
        """
        points = np.array(bbox_points)
        x_min = int(np.min(points[:, 0]))
        y_min = int(np.min(points[:, 1]))
        x_max = int(np.max(points[:, 0]))
        y_max = int(np.max(points[:, 1]))
        return (x_min, y_min, x_max - x_min, y_max - y_min)

    def _run_ocr(self, image_path: Union[str, Path]) -> List[OCRResult]:
        """
        Run OCR on an image and return all detected text regions.

        Args:
            image_path: Path to the image file

        Returns:
            List of OCRResult objects with text and coordinates
        """
        image_path = str(image_path)

        # Check cache first
        if image_path in self._ocr_cache:
            logger.debug(f"Using cached OCR results for {image_path}")
            return self._ocr_cache[image_path]

        logger.info(f"Running OCR on {image_path}")

        try:
            reader = get_ocr_reader()

            # Read image
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Failed to read image: {image_path}")
                return []

            # Run OCR - returns list of (bbox, text, confidence)
            results = reader.readtext(img, paragraph=False)

            ocr_results = []
            for bbox_points, text, confidence in results:
                if confidence >= self.min_text_confidence and text.strip():
                    bbox = self._convert_easyocr_bbox(bbox_points)
                    ocr_results.append(OCRResult(
                        text=text.strip(),
                        bbox=bbox,
                        confidence=confidence
                    ))

            logger.info(f"OCR found {len(ocr_results)} text regions")

            # Cache the results
            self._ocr_cache[image_path] = ocr_results
            return ocr_results

        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
            return []

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        # Lowercase, remove extra whitespace, remove special chars
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s€$£.,]', '', text)
        return text

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0-1)."""
        if not text1 or not text2:
            return 0.0
        t1 = self._normalize_text(text1)
        t2 = self._normalize_text(text2)
        return SequenceMatcher(None, t1, t2).ratio()

    def _find_text_regions(
        self,
        search_text: str,
        ocr_results: List[OCRResult],
        used_regions: set = None
    ) -> List[OCRResult]:
        """
        Find OCR regions that match the search text.

        Args:
            search_text: Text to search for
            ocr_results: List of OCR results to search in
            used_regions: Set of already used region indices to skip

        Returns:
            List of matching OCR results
        """
        if not search_text:
            return []

        if used_regions is None:
            used_regions = set()

        matches = []
        search_normalized = self._normalize_text(search_text)

        # Split search text into words for partial matching
        search_words = set(search_normalized.split())

        for i, ocr in enumerate(ocr_results):
            if i in used_regions:
                continue

            ocr_normalized = self._normalize_text(ocr.text)

            # Check for exact or partial match
            similarity = self._text_similarity(search_text, ocr.text)

            if similarity >= self.text_match_threshold:
                matches.append(ocr)
                continue

            # Check if OCR text contains significant words from search
            ocr_words = set(ocr_normalized.split())
            common_words = search_words & ocr_words
            if len(common_words) >= 1 and len(common_words) / len(search_words) > 0.3:
                matches.append(ocr)
                continue

            # Check if search text is contained in OCR text or vice versa
            if len(search_normalized) > 3 and search_normalized in ocr_normalized:
                matches.append(ocr)
            elif len(ocr_normalized) > 3 and ocr_normalized in search_normalized:
                matches.append(ocr)

        return matches

    def _find_price_regions(
        self,
        price: Optional[float],
        currency: Optional[str],
        ocr_results: List[OCRResult],
        used_regions: set = None
    ) -> List[OCRResult]:
        """Find OCR regions containing a price value."""
        if price is None:
            return []

        if used_regions is None:
            used_regions = set()

        matches = []

        # Create price patterns to search for
        price_str = f"{price:.2f}".replace('.', ',')  # European format
        price_str_dot = f"{price:.2f}"  # Dot format
        price_int = str(int(price)) if price == int(price) else None

        for i, ocr in enumerate(ocr_results):
            if i in used_regions:
                continue

            text = ocr.text

            # Check for price patterns
            if price_str in text or price_str_dot in text:
                matches.append(ocr)
            elif price_int and price_int in text:
                # Check if it's really a price (has currency symbol or similar context)
                if any(c in text for c in ['€', '$', '£', 'EUR', 'cena', 'price']):
                    matches.append(ocr)

        return matches

    def _build_bounding_box(
        self,
        regions: List[OCRResult],
        image_width: int,
        image_height: int
    ) -> Optional[BoundingBox]:
        """
        Build a bounding box that encompasses all given OCR regions.

        Args:
            regions: List of OCR regions to encompass
            image_width: Width of the source image
            image_height: Height of the source image

        Returns:
            BoundingBox or None if regions is empty
        """
        if not regions:
            return None

        # Find the bounding rectangle of all regions
        x_min = min(r.x for r in regions)
        y_min = min(r.y for r in regions)
        x_max = max(r.right for r in regions)
        y_max = max(r.bottom for r in regions)

        # Add padding
        pad_x = int(image_width * self.padding_percent)
        pad_y = int(image_height * self.padding_percent)

        x_min = max(0, x_min - pad_x)
        y_min = max(0, y_min - pad_y)
        x_max = min(image_width, x_max + pad_x)
        y_max = min(image_height, y_max + pad_y)

        width = x_max - x_min
        height = y_max - y_min

        # Ensure minimum size
        if width < self.min_bbox_width:
            extra = (self.min_bbox_width - width) // 2
            x_min = max(0, x_min - extra)
            width = self.min_bbox_width
            if x_min + width > image_width:
                x_min = image_width - width

        if height < self.min_bbox_height:
            extra = (self.min_bbox_height - height) // 2
            y_min = max(0, y_min - extra)
            height = self.min_bbox_height
            if y_min + height > image_height:
                y_min = image_height - height

        return BoundingBox(
            x=max(0, x_min),
            y=max(0, y_min),
            width=width,
            height=height
        )

    def _estimate_bbox_from_position_hint(
        self,
        position_hint: Optional[str],
        product_index: int,
        total_products: int,
        image_width: int,
        image_height: int
    ) -> BoundingBox:
        """
        Estimate bounding box from position hint when OCR fails.

        This is a fallback that creates a reasonable estimate based on
        the position hint and typical leaflet layouts.
        """
        # Default: divide page into a grid
        # Typical leaflet has 2-4 columns, 3-5 rows
        cols = 3
        rows = max(3, (total_products + cols - 1) // cols)

        cell_width = image_width // cols
        cell_height = image_height // rows

        # Parse position hint
        col = 0
        row = 0

        if position_hint:
            hint_lower = position_hint.lower()

            # Column detection
            if 'left' in hint_lower:
                col = 0
            elif 'center' in hint_lower or 'middle' in hint_lower:
                col = cols // 2
            elif 'right' in hint_lower:
                col = cols - 1

            # Row detection
            if 'top' in hint_lower:
                row = 0
            elif 'bottom' in hint_lower:
                row = rows - 1
            elif 'middle' in hint_lower:
                row = rows // 2

            # Check for "second", "third", etc.
            if 'second' in hint_lower:
                if 'row' in hint_lower:
                    row = 1
                else:
                    col = 1
            elif 'third' in hint_lower:
                if 'row' in hint_lower:
                    row = 2
                else:
                    col = 2
        else:
            # No hint - use index to estimate position
            row = product_index // cols
            col = product_index % cols

        x = col * cell_width
        y = row * cell_height

        # Add some padding
        pad = 20

        return BoundingBox(
            x=max(0, x + pad),
            y=max(0, y + pad),
            width=max(self.min_bbox_width, cell_width - 2 * pad),
            height=max(self.min_bbox_height, cell_height - 2 * pad)
        )

    def detect_bounding_box_for_product(
        self,
        product: ExtractedProduct,
        ocr_results: List[OCRResult],
        image_width: int,
        image_height: int,
        product_index: int = 0,
        total_products: int = 1,
        used_regions: set = None
    ) -> Tuple[BoundingBox, List[int]]:
        """
        Detect bounding box for a single product using OCR results.

        Args:
            product: The extracted product to find
            ocr_results: OCR results from the page
            image_width: Width of the page image
            image_height: Height of the page image
            product_index: Index of this product (for fallback estimation)
            total_products: Total number of products (for fallback estimation)
            used_regions: Set of already used region indices

        Returns:
            Tuple of (BoundingBox, list of used region indices)
        """
        if used_regions is None:
            used_regions = set()

        found_regions = []
        new_used_indices = []

        # Search for product name (most important)
        name_regions = self._find_text_regions(
            product.product_name,
            ocr_results,
            used_regions
        )
        if name_regions:
            found_regions.extend(name_regions)
            for r in name_regions:
                idx = ocr_results.index(r)
                if idx not in used_regions:
                    new_used_indices.append(idx)

        # Search for brand
        if product.brand:
            brand_regions = self._find_text_regions(
                product.brand,
                ocr_results,
                used_regions
            )
            if brand_regions:
                found_regions.extend(brand_regions)
                for r in brand_regions:
                    idx = ocr_results.index(r)
                    if idx not in used_regions:
                        new_used_indices.append(idx)

        # Search for prices
        price_regions = self._find_price_regions(
            product.discounted_price,
            product.currency,
            ocr_results,
            used_regions
        )
        if price_regions:
            found_regions.extend(price_regions)
            for r in price_regions:
                idx = ocr_results.index(r)
                if idx not in used_regions:
                    new_used_indices.append(idx)

        if product.regular_price:
            regular_price_regions = self._find_price_regions(
                product.regular_price,
                product.currency,
                ocr_results,
                used_regions
            )
            if regular_price_regions:
                found_regions.extend(regular_price_regions)
                for r in regular_price_regions:
                    idx = ocr_results.index(r)
                    if idx not in used_regions:
                        new_used_indices.append(idx)

        # Build bounding box from found regions
        if found_regions:
            # Remove duplicate regions
            unique_regions = list({id(r): r for r in found_regions}.values())
            bbox = self._build_bounding_box(unique_regions, image_width, image_height)
            if bbox:
                logger.debug(
                    f"Found bbox for '{product.product_name[:30]}...' from {len(unique_regions)} OCR regions"
                )
                return bbox, new_used_indices

        # Fallback: estimate from position hint
        logger.warning(
            f"OCR couldn't find text for '{product.product_name[:30]}...', "
            f"using position hint fallback"
        )
        bbox = self._estimate_bbox_from_position_hint(
            product.position_hint,
            product_index,
            total_products,
            image_width,
            image_height
        )
        return bbox, []

    async def detect_bounding_boxes(
        self,
        image_path: Union[str, Path],
        products: List[ExtractedProduct]
    ) -> List[ExtractedProduct]:
        """
        Detect bounding boxes for all products on a page.

        Args:
            image_path: Path to the page image
            products: List of products extracted by VLM (without bounding boxes)

        Returns:
            List of products with bounding boxes filled in
        """
        if not products:
            return products

        # Get image dimensions
        image_path = Path(image_path)
        try:
            with Image.open(image_path) as img:
                image_width, image_height = img.size
        except Exception as e:
            logger.error(f"Failed to get image dimensions: {e}")
            # Use default dimensions as fallback
            image_width, image_height = 2480, 3508

        # Run OCR on the page
        ocr_results = self._run_ocr(image_path)

        if not ocr_results:
            logger.warning(f"No OCR results for {image_path}, using position hints only")

        # Track which OCR regions have been used
        used_regions: set = set()

        # Process each product
        updated_products = []
        for i, product in enumerate(products):
            bbox, used_indices = self.detect_bounding_box_for_product(
                product=product,
                ocr_results=ocr_results,
                image_width=image_width,
                image_height=image_height,
                product_index=i,
                total_products=len(products),
                used_regions=used_regions
            )

            # Mark regions as used
            used_regions.update(used_indices)

            # Create new product with bounding box
            product_dict = product.model_dump()
            product_dict['bounding_box'] = bbox.model_dump()
            updated_products.append(ExtractedProduct(**product_dict))

        logger.info(
            f"Detected bounding boxes for {len(updated_products)} products "
            f"using {len(used_regions)} OCR regions"
        )

        return updated_products

    def clear_cache(self):
        """Clear the OCR results cache."""
        self._ocr_cache.clear()


# Singleton instance
_bbox_detector: Optional[OCRBoundingBoxDetector] = None


def get_bbox_detector() -> OCRBoundingBoxDetector:
    """Get or create the bounding box detector singleton."""
    global _bbox_detector
    if _bbox_detector is None:
        _bbox_detector = OCRBoundingBoxDetector()
    return _bbox_detector
