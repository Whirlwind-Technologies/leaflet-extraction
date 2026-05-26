"""
Visual Boundary Detector.

Uses color segmentation and edge detection to find product card boundaries
in leaflet images. Works for both regular grids and irregular layouts.

This complements OCR-based detection by providing visual cues about
where product cards begin and end.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from io import BytesIO

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Try to import OpenCV
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available - visual boundary detection disabled")


class VisualBoundaryDetector:
    """
    Detects product card boundaries using visual analysis.

    Uses color segmentation, edge detection, and whitespace analysis
    to find distinct regions in leaflet images.
    """

    def __init__(
        self,
        min_region_area: int = 8000,  # Minimum pixels for a valid region
        color_threshold: int = 25,  # Color difference threshold for segmentation
        merge_distance: int = 15,  # Max gap to merge similar regions
        min_aspect_ratio: float = 0.3,  # Minimum width/height ratio
        max_aspect_ratio: float = 3.5,  # Maximum width/height ratio
    ):
        self.min_region_area = min_region_area
        self.color_threshold = color_threshold
        self.merge_distance = merge_distance
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio

    def detect_product_regions(
        self,
        image: Any,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detect product regions using visual analysis.

        Args:
            image: Image as PIL Image, numpy array, bytes, or path
            image_width: Image width (auto-detected if not provided)
            image_height: Image height (auto-detected if not provided)

        Returns:
            List of regions with bounding boxes
        """
        if not CV2_AVAILABLE:
            logger.warning("OpenCV not available, returning empty regions")
            return []

        # Convert image to numpy array
        img_array = self._to_numpy(image)
        if img_array is None:
            return []

        if image_width is None:
            image_width = img_array.shape[1]
        if image_height is None:
            image_height = img_array.shape[0]

        # Step 1: Color-based segmentation
        color_regions = self._segment_by_color(img_array)

        # Step 2: Edge-based refinement
        edges = self._detect_edges(img_array)

        # Step 3: Combine color regions with edge information
        refined_regions = self._refine_regions_with_edges(color_regions, edges, img_array)

        # Step 4: Detect whitespace gaps to split merged regions
        refined_regions = self._split_by_whitespace(refined_regions, img_array)

        # Step 5: Detect discount badges to anchor product regions
        badge_regions = self._detect_discount_badges(img_array)
        if badge_regions:
            refined_regions = self._merge_badge_regions(refined_regions, badge_regions)

        # Step 6: Filter and format results
        product_regions = []
        for i, region in enumerate(refined_regions):
            bbox = region["bbox"]

            # Skip regions that are too small
            area = bbox["width"] * bbox["height"]
            if area < self.min_region_area:
                continue

            # Skip regions that span the entire image (likely background)
            if bbox["width"] > image_width * 0.9 and bbox["height"] > image_height * 0.9:
                continue

            # Validate aspect ratio
            aspect_ratio = bbox["width"] / bbox["height"] if bbox["height"] > 0 else 0
            if aspect_ratio < self.min_aspect_ratio or aspect_ratio > self.max_aspect_ratio:
                # Try to fix by splitting
                continue

            product_regions.append({
                "bbox": bbox,
                "dominant_color": region.get("color", (255, 255, 255)),
                "confidence": region.get("confidence", 0.5),
                "region_id": i,
            })

        logger.info(f"Visual detection found {len(product_regions)} regions")
        return product_regions

    def _to_numpy(self, image: Any) -> Optional[np.ndarray]:
        """Convert various image formats to numpy array."""
        try:
            if isinstance(image, np.ndarray):
                return image
            elif isinstance(image, Image.Image):
                return np.array(image)
            elif isinstance(image, bytes):
                pil_image = Image.open(BytesIO(image))
                return np.array(pil_image)
            elif isinstance(image, str):
                pil_image = Image.open(image)
                return np.array(pil_image)
            else:
                logger.error(f"Unsupported image type: {type(image)}")
                return None
        except Exception as e:
            logger.error(f"Failed to convert image: {e}")
            return None

    def _segment_by_color(self, img: np.ndarray) -> List[Dict[str, Any]]:
        """
        Segment image into regions based on color similarity.

        Uses k-means clustering to find dominant colors,
        then creates masks for each color region.
        """
        # Convert to RGB if needed
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

        # Resize for faster processing
        scale = min(1.0, 800 / max(img.shape[:2]))
        if scale < 1.0:
            small = cv2.resize(img, None, fx=scale, fy=scale)
        else:
            small = img
            scale = 1.0

        # Apply bilateral filter to reduce noise while preserving edges
        filtered = cv2.bilateralFilter(small, 9, 75, 75)

        # Reshape for k-means
        pixels = filtered.reshape(-1, 3).astype(np.float32)

        # K-means clustering to find dominant colors
        n_colors = min(12, max(4, img.shape[0] * img.shape[1] // 100000))
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
        _, labels, centers = cv2.kmeans(
            pixels, n_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
        )

        # Create mask for each color cluster
        labels = labels.reshape(small.shape[:2])
        regions = []

        for i, center in enumerate(centers):
            mask = (labels == i).astype(np.uint8) * 255

            # Find contours in the mask
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.min_region_area * (scale ** 2):
                    continue

                x, y, w, h = cv2.boundingRect(contour)

                # Scale back to original size
                regions.append({
                    "bbox": {
                        "x": int(x / scale),
                        "y": int(y / scale),
                        "width": int(w / scale),
                        "height": int(h / scale),
                    },
                    "color": tuple(int(c) for c in center),
                    "area": area / (scale ** 2),
                    "confidence": 0.6,
                })

        return regions

    def _detect_edges(self, img: np.ndarray) -> np.ndarray:
        """Detect edges using Canny edge detection."""
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img

        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny edge detection
        edges = cv2.Canny(blurred, 50, 150)

        return edges

    def _refine_regions_with_edges(
        self,
        color_regions: List[Dict[str, Any]],
        edges: np.ndarray,
        img: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Refine color regions using edge information.

        Adjusts region boundaries to align with detected edges.
        """
        if not color_regions:
            return []

        # Dilate edges to create boundary zones
        kernel = np.ones((3, 3), np.uint8)
        dilated_edges = cv2.dilate(edges, kernel, iterations=2)

        refined = []
        for region in color_regions:
            bbox = region["bbox"]
            x, y, w, h = bbox["x"], bbox["y"], bbox["width"], bbox["height"]

            # Extract edge region
            edge_roi = dilated_edges[
                max(0, y):min(edges.shape[0], y + h),
                max(0, x):min(edges.shape[1], x + w)
            ]

            if edge_roi.size == 0:
                refined.append(region)
                continue

            # Find strong horizontal and vertical edges
            # These often indicate product card boundaries
            h_edges = np.sum(edge_roi, axis=1)
            v_edges = np.sum(edge_roi, axis=0)

            # Adjust boundaries based on edge strength
            # (This is a simplified version - could be more sophisticated)

            # Look for strong edges near boundaries
            edge_threshold = np.mean(h_edges) * 1.5 if np.mean(h_edges) > 0 else 0

            # Refine top boundary
            for i in range(min(20, len(h_edges))):
                if h_edges[i] > edge_threshold:
                    y = max(0, y + i)
                    h = h - i
                    break

            # Refine bottom boundary
            for i in range(min(20, len(h_edges))):
                if h_edges[-(i+1)] > edge_threshold:
                    h = h - i
                    break

            refined.append({
                "bbox": {"x": x, "y": y, "width": max(1, w), "height": max(1, h)},
                "color": region.get("color"),
                "confidence": region.get("confidence", 0.5) + 0.1,
            })

        # Merge overlapping regions
        refined = self._merge_overlapping_regions(refined)

        return refined

    def _merge_overlapping_regions(
        self,
        regions: List[Dict[str, Any]],
        overlap_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Merge regions that significantly overlap."""
        if len(regions) <= 1:
            return regions

        merged = []
        used = set()

        for i, region1 in enumerate(regions):
            if i in used:
                continue

            bbox1 = region1["bbox"]
            merged_bbox = bbox1.copy()

            for j, region2 in enumerate(regions):
                if i == j or j in used:
                    continue

                bbox2 = region2["bbox"]

                # Calculate overlap
                overlap = self._calculate_overlap(bbox1, bbox2)

                if overlap > overlap_threshold:
                    # Merge bounding boxes
                    merged_bbox = {
                        "x": min(merged_bbox["x"], bbox2["x"]),
                        "y": min(merged_bbox["y"], bbox2["y"]),
                        "width": max(
                            merged_bbox["x"] + merged_bbox["width"],
                            bbox2["x"] + bbox2["width"]
                        ) - min(merged_bbox["x"], bbox2["x"]),
                        "height": max(
                            merged_bbox["y"] + merged_bbox["height"],
                            bbox2["y"] + bbox2["height"]
                        ) - min(merged_bbox["y"], bbox2["y"]),
                    }
                    used.add(j)

            merged.append({
                "bbox": merged_bbox,
                "color": region1.get("color"),
                "confidence": region1.get("confidence", 0.5),
            })
            used.add(i)

        return merged

    def _calculate_overlap(
        self,
        bbox1: Dict[str, int],
        bbox2: Dict[str, int],
    ) -> float:
        """Calculate IoU (Intersection over Union) of two bounding boxes."""
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


    def _split_by_whitespace(
        self,
        regions: List[Dict[str, Any]],
        img: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Split regions that contain whitespace gaps.

        Looks for horizontal or vertical white/light bands within regions
        that indicate product boundaries.
        """
        if not regions:
            return regions

        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img

        split_regions = []

        for region in regions:
            bbox = region["bbox"]
            x, y, w, h = bbox["x"], bbox["y"], bbox["width"], bbox["height"]

            # Skip small regions
            if w < 200 or h < 200:
                split_regions.append(region)
                continue

            # Extract region
            roi = gray[
                max(0, y):min(gray.shape[0], y + h),
                max(0, x):min(gray.shape[1], x + w)
            ]

            if roi.size == 0:
                split_regions.append(region)
                continue

            # Look for vertical whitespace (to split horizontally adjacent products)
            col_means = np.mean(roi, axis=0)
            white_threshold = 240  # Near white

            # Find vertical gaps
            v_gaps = self._find_gaps(col_means, white_threshold, min_gap_width=15)

            if v_gaps and len(v_gaps) <= 3:
                # Split by vertical gaps
                sub_regions = self._split_region_by_gaps(region, v_gaps, axis="vertical")
                split_regions.extend(sub_regions)
            else:
                # Look for horizontal whitespace (to split vertically stacked products)
                row_means = np.mean(roi, axis=1)
                h_gaps = self._find_gaps(row_means, white_threshold, min_gap_width=15)

                if h_gaps and len(h_gaps) <= 3:
                    sub_regions = self._split_region_by_gaps(region, h_gaps, axis="horizontal")
                    split_regions.extend(sub_regions)
                else:
                    split_regions.append(region)

        return split_regions

    def _find_gaps(
        self,
        values: np.ndarray,
        threshold: float,
        min_gap_width: int = 10,
    ) -> List[Tuple[int, int]]:
        """Find continuous gaps where values exceed threshold."""
        gaps = []
        in_gap = False
        gap_start = 0

        for i, val in enumerate(values):
            if val > threshold:
                if not in_gap:
                    in_gap = True
                    gap_start = i
            else:
                if in_gap:
                    if i - gap_start >= min_gap_width:
                        gaps.append((gap_start, i))
                    in_gap = False

        # Handle gap at end
        if in_gap and len(values) - gap_start >= min_gap_width:
            gaps.append((gap_start, len(values)))

        return gaps

    def _split_region_by_gaps(
        self,
        region: Dict[str, Any],
        gaps: List[Tuple[int, int]],
        axis: str,
    ) -> List[Dict[str, Any]]:
        """Split a region by detected gaps."""
        bbox = region["bbox"]
        x, y, w, h = bbox["x"], bbox["y"], bbox["width"], bbox["height"]

        sub_regions = []
        prev_end = 0

        for gap_start, gap_end in gaps:
            if axis == "vertical":
                # Split horizontally
                if gap_start - prev_end > 50:  # Minimum sub-region width
                    sub_regions.append({
                        "bbox": {
                            "x": x + prev_end,
                            "y": y,
                            "width": gap_start - prev_end,
                            "height": h,
                        },
                        "color": region.get("color"),
                        "confidence": region.get("confidence", 0.5),
                    })
                prev_end = gap_end
            else:
                # Split vertically
                if gap_start - prev_end > 50:  # Minimum sub-region height
                    sub_regions.append({
                        "bbox": {
                            "x": x,
                            "y": y + prev_end,
                            "width": w,
                            "height": gap_start - prev_end,
                        },
                        "color": region.get("color"),
                        "confidence": region.get("confidence", 0.5),
                    })
                prev_end = gap_end

        # Add final region
        if axis == "vertical":
            if w - prev_end > 50:
                sub_regions.append({
                    "bbox": {
                        "x": x + prev_end,
                        "y": y,
                        "width": w - prev_end,
                        "height": h,
                    },
                    "color": region.get("color"),
                    "confidence": region.get("confidence", 0.5),
                })
        else:
            if h - prev_end > 50:
                sub_regions.append({
                    "bbox": {
                        "x": x,
                        "y": y + prev_end,
                        "width": w,
                        "height": h - prev_end,
                    },
                    "color": region.get("color"),
                    "confidence": region.get("confidence", 0.5),
                })

        return sub_regions if sub_regions else [region]

    def _detect_discount_badges(self, img: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect discount badges (colored circles/rectangles with percentages).

        These are strong indicators of product locations.
        """
        badges = []

        # Convert to HSV for better color detection
        if len(img.shape) == 2:
            return badges

        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

        # Common badge colors: red, yellow, green, orange
        color_ranges = [
            # Red (wraps around 0)
            ((0, 100, 100), (10, 255, 255)),
            ((160, 100, 100), (180, 255, 255)),
            # Yellow/Orange
            ((15, 100, 100), (35, 255, 255)),
            # Green
            ((35, 100, 100), (85, 255, 255)),
        ]

        for lower, upper in color_ranges:
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))

            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)

                # Badges are typically small-medium sized
                if 500 < area < 50000:
                    x, y, w, h = cv2.boundingRect(contour)

                    # Badges are usually roughly square or circular
                    aspect = w / h if h > 0 else 0
                    if 0.5 < aspect < 2.0:
                        # Check circularity
                        perimeter = cv2.arcLength(contour, True)
                        circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0

                        badges.append({
                            "bbox": {"x": x, "y": y, "width": w, "height": h},
                            "area": area,
                            "circularity": circularity,
                            "is_circular": circularity > 0.6,
                        })

        logger.debug(f"Detected {len(badges)} potential discount badges")
        return badges

    def _merge_badge_regions(
        self,
        regions: List[Dict[str, Any]],
        badges: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Ensure each detected badge is within a region.

        If a badge is not covered by any region, expand the nearest region
        or create a new one.
        """
        for badge in badges:
            badge_bbox = badge["bbox"]
            badge_center = (
                badge_bbox["x"] + badge_bbox["width"] // 2,
                badge_bbox["y"] + badge_bbox["height"] // 2,
            )

            # Check if badge is within any region
            covered = False
            for region in regions:
                r_bbox = region["bbox"]
                if (r_bbox["x"] <= badge_center[0] <= r_bbox["x"] + r_bbox["width"] and
                    r_bbox["y"] <= badge_center[1] <= r_bbox["y"] + r_bbox["height"]):
                    covered = True
                    # Expand region to fully include badge if needed
                    if badge_bbox["x"] < r_bbox["x"]:
                        diff = r_bbox["x"] - badge_bbox["x"]
                        r_bbox["x"] = badge_bbox["x"]
                        r_bbox["width"] += diff
                    if badge_bbox["y"] < r_bbox["y"]:
                        diff = r_bbox["y"] - badge_bbox["y"]
                        r_bbox["y"] = badge_bbox["y"]
                        r_bbox["height"] += diff
                    if badge_bbox["x"] + badge_bbox["width"] > r_bbox["x"] + r_bbox["width"]:
                        r_bbox["width"] = badge_bbox["x"] + badge_bbox["width"] - r_bbox["x"]
                    if badge_bbox["y"] + badge_bbox["height"] > r_bbox["y"] + r_bbox["height"]:
                        r_bbox["height"] = badge_bbox["y"] + badge_bbox["height"] - r_bbox["y"]
                    break

            # If not covered, this might indicate a missed region
            # For now, just log it
            if not covered:
                logger.debug(f"Badge at {badge_center} not covered by any region")

        return regions


def get_visual_boundary_detector() -> Optional[VisualBoundaryDetector]:
    """Get visual boundary detector if OpenCV is available."""
    if CV2_AVAILABLE:
        return VisualBoundaryDetector()
    return None


def is_visual_detection_available() -> bool:
    """Check if visual boundary detection is available."""
    return CV2_AVAILABLE
