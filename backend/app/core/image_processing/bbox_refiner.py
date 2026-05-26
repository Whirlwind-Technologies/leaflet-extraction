"""
Bounding Box Refinement Module.

Uses computer vision techniques to refine VLM-generated bounding boxes
by detecting actual product card boundaries in the image.

This module helps correct inaccurate bounding boxes from VLM by:
1. Detecting edges and contours in the region around the VLM's estimate
2. Finding rectangular shapes that likely represent product cards
3. Adjusting the bounding box to match the detected boundaries

Example Usage:
    from app.core.image_processing.bbox_refiner import BoundingBoxRefiner
    
    refiner = BoundingBoxRefiner()
    refined_bbox = refiner.refine_bounding_box(
        page_image,
        initial_bbox,
        expansion_ratio=0.2
    )
"""

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import List, Optional, Tuple, Union

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Try to import OpenCV, but make it optional
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV not available. Bounding box refinement will be limited.")


@dataclass
class BoundingBox:
    """Simple bounding box representation."""
    x: int
    y: int
    width: int
    height: int
    
    @property
    def x2(self) -> int:
        return self.x + self.width
    
    @property
    def y2(self) -> int:
        return self.y + self.height
    
    @property
    def area(self) -> int:
        return self.width * self.height
    
    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}
    
    @classmethod
    def from_dict(cls, d: dict) -> "BoundingBox":
        return cls(x=d["x"], y=d["y"], width=d["width"], height=d["height"])


@dataclass
class RefinementResult:
    """Result of bounding box refinement."""
    original_bbox: BoundingBox
    refined_bbox: BoundingBox
    confidence: float
    method: str
    was_refined: bool
    notes: str = ""


class BoundingBoxRefiner:
    """
    Refines VLM-generated bounding boxes using computer vision.
    
    The VLM provides initial estimates of product card locations,
    but these may be inaccurate. This class uses edge detection
    and contour finding to locate the actual boundaries of product
    cards in the image.
    
    Attributes:
        expansion_ratio: How much to expand the search area around VLM's bbox
        min_area_ratio: Minimum area ratio for a valid refined bbox
        max_area_ratio: Maximum area ratio for a valid refined bbox
        
    Example:
        >>> refiner = BoundingBoxRefiner()
        >>> result = refiner.refine_bounding_box(image, bbox)
        >>> if result.was_refined:
        ...     print(f"Refined bbox: {result.refined_bbox}")
    """
    
    def __init__(
        self,
        expansion_ratio: float = 0.3,
        min_area_ratio: float = 0.5,
        max_area_ratio: float = 2.0,
        edge_threshold1: int = 50,
        edge_threshold2: int = 150,
    ):
        """
        Initialize the bounding box refiner.
        
        Args:
            expansion_ratio: Expand search area by this ratio (0.3 = 30%)
            min_area_ratio: Refined bbox must be at least this ratio of original
            max_area_ratio: Refined bbox must be at most this ratio of original
            edge_threshold1: Canny edge detection lower threshold
            edge_threshold2: Canny edge detection upper threshold
        """
        self.expansion_ratio = expansion_ratio
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio
        self.edge_threshold1 = edge_threshold1
        self.edge_threshold2 = edge_threshold2
    
    def refine_bounding_box(
        self,
        image: Union[Image.Image, np.ndarray, bytes],
        bbox: Union[BoundingBox, dict],
        method: str = "auto",
    ) -> RefinementResult:
        """
        Refine a bounding box using computer vision.
        
        Args:
            image: Page image (PIL Image, numpy array, or bytes)
            bbox: Initial bounding box from VLM
            method: Refinement method ("auto", "edge", "color", "contour")
            
        Returns:
            RefinementResult with original and refined bounding boxes
        """
        # Convert bbox if needed
        if isinstance(bbox, dict):
            bbox = BoundingBox.from_dict(bbox)
        
        # Convert image to numpy array
        img_array = self._to_numpy(image)
        if img_array is None:
            return RefinementResult(
                original_bbox=bbox,
                refined_bbox=bbox,
                confidence=0.0,
                method="none",
                was_refined=False,
                notes="Failed to convert image"
            )
        
        # Get image dimensions
        img_height, img_width = img_array.shape[:2]
        
        # Validate and clip initial bbox to image bounds
        bbox = self._clip_bbox(bbox, img_width, img_height)
        
        if not OPENCV_AVAILABLE:
            # Without OpenCV, just return the original bbox with minor adjustments
            return self._basic_refinement(bbox, img_width, img_height)
        
        # Try different refinement methods
        if method == "auto":
            # Try edge detection first, then color-based
            result = self._refine_by_edges(img_array, bbox)
            if not result.was_refined or result.confidence < 0.7:
                color_result = self._refine_by_color(img_array, bbox)
                if color_result.confidence > result.confidence:
                    result = color_result
            return result
        elif method == "edge":
            return self._refine_by_edges(img_array, bbox)
        elif method == "color":
            return self._refine_by_color(img_array, bbox)
        elif method == "contour":
            return self._refine_by_contours(img_array, bbox)
        else:
            return self._basic_refinement(bbox, img_width, img_height)
    
    def refine_batch(
        self,
        image: Union[Image.Image, np.ndarray, bytes],
        bboxes: List[Union[BoundingBox, dict]],
    ) -> List[RefinementResult]:
        """
        Refine multiple bounding boxes on the same image.
        
        More efficient than calling refine_bounding_box multiple times
        as it only converts the image once.
        
        Args:
            image: Page image
            bboxes: List of bounding boxes to refine
            
        Returns:
            List of RefinementResults
        """
        img_array = self._to_numpy(image)
        results = []
        
        for bbox in bboxes:
            if isinstance(bbox, dict):
                bbox = BoundingBox.from_dict(bbox)
            
            if img_array is None:
                results.append(RefinementResult(
                    original_bbox=bbox,
                    refined_bbox=bbox,
                    confidence=0.0,
                    method="none",
                    was_refined=False,
                ))
            else:
                results.append(self.refine_bounding_box(img_array, bbox))
        
        return results
    
    def _to_numpy(self, image: Union[Image.Image, np.ndarray, bytes]) -> Optional[np.ndarray]:
        """Convert image to numpy array."""
        try:
            if isinstance(image, np.ndarray):
                return image
            elif isinstance(image, bytes):
                pil_image = Image.open(BytesIO(image))
                return np.array(pil_image)
            elif isinstance(image, Image.Image):
                return np.array(image)
            else:
                logger.error(f"Unsupported image type: {type(image)}")
                return None
        except Exception as e:
            logger.error(f"Failed to convert image to numpy: {e}")
            return None
    
    def _clip_bbox(self, bbox: BoundingBox, img_width: int, img_height: int) -> BoundingBox:
        """Clip bounding box to image boundaries."""
        x = max(0, min(bbox.x, img_width - 1))
        y = max(0, min(bbox.y, img_height - 1))
        width = min(bbox.width, img_width - x)
        height = min(bbox.height, img_height - y)
        return BoundingBox(x=x, y=y, width=width, height=height)
    
    def _basic_refinement(
        self,
        bbox: BoundingBox,
        img_width: int,
        img_height: int
    ) -> RefinementResult:
        """Basic refinement without OpenCV - just ensures reasonable bounds."""
        # Add a small padding if bbox seems too tight
        padding = 10
        
        new_x = max(0, bbox.x - padding)
        new_y = max(0, bbox.y - padding)
        new_width = min(bbox.width + 2 * padding, img_width - new_x)
        new_height = min(bbox.height + 2 * padding, img_height - new_y)
        
        refined = BoundingBox(x=new_x, y=new_y, width=new_width, height=new_height)
        
        return RefinementResult(
            original_bbox=bbox,
            refined_bbox=refined,
            confidence=0.5,
            method="basic_padding",
            was_refined=True,
            notes="Applied basic padding (OpenCV not available)"
        )
    
    def _refine_by_edges(
        self,
        img_array: np.ndarray,
        bbox: BoundingBox,
    ) -> RefinementResult:
        """Refine bounding box using edge detection."""
        img_height, img_width = img_array.shape[:2]
        
        # Expand search region
        search_bbox = self._expand_bbox(bbox, self.expansion_ratio, img_width, img_height)
        
        # Extract region of interest
        roi = img_array[search_bbox.y:search_bbox.y2, search_bbox.x:search_bbox.x2]
        
        if roi.size == 0:
            return RefinementResult(
                original_bbox=bbox,
                refined_bbox=bbox,
                confidence=0.0,
                method="edge",
                was_refined=False,
                notes="Empty ROI"
            )
        
        # Convert to grayscale
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Detect edges using Canny
        edges = cv2.Canny(blurred, self.edge_threshold1, self.edge_threshold2)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return RefinementResult(
                original_bbox=bbox,
                refined_bbox=bbox,
                confidence=0.3,
                method="edge",
                was_refined=False,
                notes="No contours found"
            )
        
        # Find the best rectangular contour
        best_rect = None
        best_score = 0
        
        for contour in contours:
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # Calculate score based on size and aspect ratio
            area = w * h
            aspect_ratio = w / h if h > 0 else 0
            
            # Prefer rectangles similar in size to original bbox
            size_ratio = area / bbox.area if bbox.area > 0 else 0
            if size_ratio < self.min_area_ratio or size_ratio > self.max_area_ratio:
                continue
            
            # Score based on how rectangular the contour is
            rect_area = w * h
            contour_area = cv2.contourArea(contour)
            rectangularity = contour_area / rect_area if rect_area > 0 else 0
            
            score = rectangularity * min(size_ratio, 1.0 / size_ratio)
            
            if score > best_score:
                best_score = score
                best_rect = (x, y, w, h)
        
        if best_rect is None:
            return RefinementResult(
                original_bbox=bbox,
                refined_bbox=bbox,
                confidence=0.4,
                method="edge",
                was_refined=False,
                notes="No suitable rectangle found"
            )
        
        # Convert ROI coordinates back to image coordinates
        rx, ry, rw, rh = best_rect
        refined = BoundingBox(
            x=search_bbox.x + rx,
            y=search_bbox.y + ry,
            width=rw,
            height=rh
        )
        
        return RefinementResult(
            original_bbox=bbox,
            refined_bbox=refined,
            confidence=min(0.9, best_score + 0.5),
            method="edge",
            was_refined=True,
            notes=f"Found rectangle with score {best_score:.2f}"
        )
    
    def _refine_by_color(
        self,
        img_array: np.ndarray,
        bbox: BoundingBox,
    ) -> RefinementResult:
        """Refine bounding box by detecting color boundaries."""
        img_height, img_width = img_array.shape[:2]
        
        # Expand search region
        search_bbox = self._expand_bbox(bbox, self.expansion_ratio, img_width, img_height)
        
        # Extract region of interest
        roi = img_array[search_bbox.y:search_bbox.y2, search_bbox.x:search_bbox.x2]
        
        if roi.size == 0 or len(roi.shape) < 3:
            return RefinementResult(
                original_bbox=bbox,
                refined_bbox=bbox,
                confidence=0.0,
                method="color",
                was_refined=False,
                notes="Invalid ROI for color analysis"
            )
        
        # Convert to HSV for better color segmentation
        hsv = cv2.cvtColor(roi, cv2.COLOR_RGB2HSV)
        
        # Detect common product card border colors (teal, blue, white)
        # Teal/cyan: H=80-100, S>50, V>50
        # Blue: H=100-130, S>50, V>50
        # White: S<30, V>200
        
        masks = []
        
        # Teal mask
        teal_lower = np.array([80, 50, 50])
        teal_upper = np.array([100, 255, 255])
        masks.append(cv2.inRange(hsv, teal_lower, teal_upper))
        
        # Blue mask
        blue_lower = np.array([100, 50, 50])
        blue_upper = np.array([130, 255, 255])
        masks.append(cv2.inRange(hsv, blue_lower, blue_upper))
        
        # Combine masks
        combined_mask = masks[0]
        for mask in masks[1:]:
            combined_mask = cv2.bitwise_or(combined_mask, mask)
        
        # Find contours in the mask
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return RefinementResult(
                original_bbox=bbox,
                refined_bbox=bbox,
                confidence=0.3,
                method="color",
                was_refined=False,
                notes="No color boundaries found"
            )
        
        # Find the largest contour that's roughly rectangular
        best_rect = None
        best_area = 0
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            
            # Check if it's a reasonable size
            size_ratio = area / bbox.area if bbox.area > 0 else 0
            if size_ratio < self.min_area_ratio or size_ratio > self.max_area_ratio:
                continue
            
            if area > best_area:
                best_area = area
                best_rect = (x, y, w, h)
        
        if best_rect is None:
            return RefinementResult(
                original_bbox=bbox,
                refined_bbox=bbox,
                confidence=0.4,
                method="color",
                was_refined=False,
                notes="No suitable color boundary found"
            )
        
        # Convert ROI coordinates back to image coordinates
        rx, ry, rw, rh = best_rect
        refined = BoundingBox(
            x=search_bbox.x + rx,
            y=search_bbox.y + ry,
            width=rw,
            height=rh
        )
        
        return RefinementResult(
            original_bbox=bbox,
            refined_bbox=refined,
            confidence=0.7,
            method="color",
            was_refined=True,
            notes="Found color boundary"
        )
    
    def _refine_by_contours(
        self,
        img_array: np.ndarray,
        bbox: BoundingBox,
    ) -> RefinementResult:
        """Refine bounding box by finding rectangular contours."""
        # This is similar to edge detection but focuses on finding
        # rectangular shapes specifically
        return self._refine_by_edges(img_array, bbox)
    
    def _expand_bbox(
        self,
        bbox: BoundingBox,
        ratio: float,
        img_width: int,
        img_height: int,
    ) -> BoundingBox:
        """Expand bounding box by a ratio while staying within image bounds."""
        expand_x = int(bbox.width * ratio)
        expand_y = int(bbox.height * ratio)
        
        new_x = max(0, bbox.x - expand_x)
        new_y = max(0, bbox.y - expand_y)
        new_width = min(bbox.width + 2 * expand_x, img_width - new_x)
        new_height = min(bbox.height + 2 * expand_y, img_height - new_y)
        
        return BoundingBox(x=new_x, y=new_y, width=new_width, height=new_height)


def refine_product_bboxes(
    page_image: Union[Image.Image, np.ndarray, bytes],
    products: List[dict],
) -> List[dict]:
    """
    Convenience function to refine bounding boxes for a list of products.
    
    Args:
        page_image: The page image
        products: List of product dicts with 'bounding_box' key
        
    Returns:
        Updated list of products with refined bounding boxes
    """
    refiner = BoundingBoxRefiner()
    
    for product in products:
        if "bounding_box" not in product:
            continue
        
        result = refiner.refine_bounding_box(page_image, product["bounding_box"])
        
        if result.was_refined and result.confidence > 0.6:
            product["bounding_box"] = result.refined_bbox.to_dict()
            product["bbox_refined"] = True
            product["bbox_refinement_confidence"] = result.confidence
            product["bbox_refinement_method"] = result.method
        else:
            product["bbox_refined"] = False
    
    return products