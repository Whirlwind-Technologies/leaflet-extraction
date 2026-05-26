"""
Bounding Box Visualizer Module.

This module draws bounding boxes on images for visual verification
in the two-pass extraction process.

Example Usage:
    from app.core.image_processing.bbox_visualizer import BBoxVisualizer

    visualizer = BBoxVisualizer()
    annotated_image = visualizer.draw_bboxes(
        image_path="/path/to/page.png",
        products=[{"bounding_box": {"x": 50, "y": 100, "width": 300, "height": 400}, ...}]
    )
"""

import io
import base64
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Color palette for bounding boxes (matching prompt_builder.py)
BBOX_COLORS = [
    (255, 0, 0),      # RED
    (0, 0, 255),      # BLUE
    (0, 255, 0),      # GREEN
    (255, 255, 0),    # YELLOW
    (128, 0, 128),    # PURPLE
    (255, 165, 0),    # ORANGE
    (0, 255, 255),    # CYAN
    (255, 0, 255),    # MAGENTA
]

COLOR_NAMES = ["RED", "BLUE", "GREEN", "YELLOW", "PURPLE", "ORANGE", "CYAN", "MAGENTA"]


class BBoxVisualizer:
    """
    Draws bounding boxes on images for visual verification.

    Creates annotated images with colored rectangles showing
    detected product locations, used for Pass 2 verification.

    Attributes:
        line_width: Width of bounding box lines
        font_size: Size of label text
        show_labels: Whether to show product labels
    """

    def __init__(
        self,
        line_width: int = 4,
        font_size: int = 24,
        show_labels: bool = True,
    ):
        """
        Initialize the visualizer.

        Args:
            line_width: Width of bounding box lines in pixels
            font_size: Size of label text
            show_labels: Whether to show product index labels
        """
        self.line_width = line_width
        self.font_size = font_size
        self.show_labels = show_labels
        self._font = None

    def _get_font(self) -> ImageFont.FreeTypeFont:
        """Get or create the font for labels."""
        if self._font is None:
            try:
                # Try to use a system font
                self._font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", self.font_size)
            except (IOError, OSError):
                try:
                    self._font = ImageFont.truetype("arial.ttf", self.font_size)
                except (IOError, OSError):
                    # Fall back to default font
                    self._font = ImageFont.load_default()
        return self._font

    def draw_bboxes(
        self,
        image: Union[str, Path, Image.Image, bytes],
        products: List[Dict[str, Any]],
        output_format: str = "pil",
    ) -> Union[Image.Image, bytes, str]:
        """
        Draw bounding boxes on an image.

        Args:
            image: Input image (path, PIL Image, or bytes)
            products: List of products with bounding_box field
            output_format: Output format - "pil", "bytes", or "base64"

        Returns:
            Annotated image in requested format
        """
        # Load image
        if isinstance(image, (str, Path)):
            img = Image.open(image)
        elif isinstance(image, bytes):
            img = Image.open(io.BytesIO(image))
        elif isinstance(image, Image.Image):
            img = image.copy()
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Create drawing context
        draw = ImageDraw.Draw(img)
        font = self._get_font()

        # Draw each bounding box
        for i, product in enumerate(products):
            bbox = product.get("bounding_box")
            if not bbox:
                continue

            # Get coordinates
            x = bbox.get("x", 0)
            y = bbox.get("y", 0)
            width = bbox.get("width", 0)
            height = bbox.get("height", 0)

            # Skip invalid boxes
            if width <= 0 or height <= 0:
                continue

            # Get color for this product
            color = BBOX_COLORS[i % len(BBOX_COLORS)]
            color_name = COLOR_NAMES[i % len(COLOR_NAMES)]

            # Draw rectangle
            for offset in range(self.line_width):
                draw.rectangle(
                    [x + offset, y + offset, x + width - offset, y + height - offset],
                    outline=color
                )

            # Draw label if enabled
            if self.show_labels:
                label = f"{i + 1}"
                # Draw label background
                label_bbox = draw.textbbox((0, 0), label, font=font)
                label_width = label_bbox[2] - label_bbox[0]
                label_height = label_bbox[3] - label_bbox[1]
                padding = 4

                # Position label at top-left of bounding box
                label_x = x
                label_y = max(0, y - label_height - padding * 2)

                # Draw background rectangle
                draw.rectangle(
                    [label_x, label_y, label_x + label_width + padding * 2, label_y + label_height + padding * 2],
                    fill=color
                )

                # Draw text
                draw.text(
                    (label_x + padding, label_y + padding),
                    label,
                    fill=(255, 255, 255),
                    font=font
                )

        # Return in requested format
        if output_format == "pil":
            return img
        elif output_format == "bytes":
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()
        elif output_format == "base64":
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def draw_bboxes_with_corrections(
        self,
        image: Union[str, Path, Image.Image, bytes],
        original_products: List[Dict[str, Any]],
        corrections: List[Dict[str, Any]],
        output_format: str = "pil",
    ) -> Union[Image.Image, bytes, str]:
        """
        Draw both original and corrected bounding boxes.

        Original boxes shown in dashed lines, corrections in solid.
        Useful for visualizing verification results.

        Args:
            image: Input image
            original_products: Original extracted products
            corrections: Verification corrections
            output_format: Output format

        Returns:
            Annotated image showing original and corrected boxes
        """
        # Load image
        if isinstance(image, (str, Path)):
            img = Image.open(image)
        elif isinstance(image, bytes):
            img = Image.open(io.BytesIO(image))
        elif isinstance(image, Image.Image):
            img = image.copy()
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        if img.mode != "RGB":
            img = img.convert("RGB")

        draw = ImageDraw.Draw(img)

        # Build correction lookup
        correction_map = {}
        for corr in corrections:
            idx = corr.get("product_index", 0) - 1  # Convert to 0-indexed
            if 0 <= idx < len(original_products):
                correction_map[idx] = corr

        # Draw original boxes (semi-transparent/dashed style)
        for i, product in enumerate(original_products):
            bbox = product.get("bounding_box")
            if not bbox:
                continue

            x = bbox.get("x", 0)
            y = bbox.get("y", 0)
            width = bbox.get("width", 0)
            height = bbox.get("height", 0)

            if width <= 0 or height <= 0:
                continue

            color = BBOX_COLORS[i % len(BBOX_COLORS)]

            # Draw dashed rectangle for original
            self._draw_dashed_rectangle(draw, x, y, width, height, color)

            # If there's a correction, draw the corrected box solid
            if i in correction_map:
                corr = correction_map[i]
                corrected_bbox = corr.get("corrected_bbox")
                if corrected_bbox and not corr.get("is_correct", True):
                    cx = corrected_bbox.get("x", 0)
                    cy = corrected_bbox.get("y", 0)
                    cw = corrected_bbox.get("width", 0)
                    ch = corrected_bbox.get("height", 0)

                    # Draw solid corrected box
                    for offset in range(self.line_width):
                        draw.rectangle(
                            [cx + offset, cy + offset, cx + cw - offset, cy + ch - offset],
                            outline=color
                        )

        # Return in requested format
        if output_format == "pil":
            return img
        elif output_format == "bytes":
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()
        elif output_format == "base64":
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _draw_dashed_rectangle(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        width: int,
        height: int,
        color: Tuple[int, int, int],
        dash_length: int = 10,
        gap_length: int = 5,
    ):
        """Draw a dashed rectangle."""
        # Top edge
        self._draw_dashed_line(draw, x, y, x + width, y, color, dash_length, gap_length)
        # Bottom edge
        self._draw_dashed_line(draw, x, y + height, x + width, y + height, color, dash_length, gap_length)
        # Left edge
        self._draw_dashed_line(draw, x, y, x, y + height, color, dash_length, gap_length)
        # Right edge
        self._draw_dashed_line(draw, x + width, y, x + width, y + height, color, dash_length, gap_length)

    def _draw_dashed_line(
        self,
        draw: ImageDraw.Draw,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: Tuple[int, int, int],
        dash_length: int = 10,
        gap_length: int = 5,
    ):
        """Draw a dashed line."""
        import math

        total_length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if total_length == 0:
            return

        dx = (x2 - x1) / total_length
        dy = (y2 - y1) / total_length

        current = 0
        drawing = True

        while current < total_length:
            if drawing:
                end = min(current + dash_length, total_length)
                draw.line(
                    [
                        x1 + dx * current,
                        y1 + dy * current,
                        x1 + dx * end,
                        y1 + dy * end,
                    ],
                    fill=color,
                    width=self.line_width
                )
                current = end
            else:
                current += gap_length
            drawing = not drawing


# Singleton instance
_visualizer: Optional[BBoxVisualizer] = None


def get_bbox_visualizer() -> BBoxVisualizer:
    """Get or create the bounding box visualizer singleton."""
    global _visualizer
    if _visualizer is None:
        _visualizer = BBoxVisualizer()
    return _visualizer
