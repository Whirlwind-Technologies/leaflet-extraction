"""
Grid Overlay Module for Bounding Box Detection.

This module overlays a numbered grid on images to help VLMs
identify product locations using grid cells instead of pixel coordinates.

VLMs are better at saying "cells B2, C2, B3, C3" than "x=243, y=187".
"""

import io
import base64
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class GridOverlay:
    """
    Overlays a labeled grid on images for spatial reference.

    Creates a grid with labeled rows (1,2,3...) and columns (A,B,C...)
    to help VLMs identify product locations more accurately.
    """

    def __init__(
        self,
        columns: int = 4,
        rows: int = 6,
        line_color: Tuple[int, int, int] = (255, 0, 0),
        line_width: int = 2,
        label_size: int = 28,
        label_color: Tuple[int, int, int] = (255, 0, 0),
    ):
        """
        Initialize the grid overlay.

        Args:
            columns: Number of columns (A, B, C, D...)
            rows: Number of rows (1, 2, 3, 4...)
            line_color: RGB color for grid lines
            line_width: Width of grid lines in pixels
            label_size: Font size for cell labels
            label_color: RGB color for labels
        """
        self.columns = columns
        self.rows = rows
        self.line_color = line_color
        self.line_width = line_width
        self.label_size = label_size
        self.label_color = label_color
        self._font = None

    def _get_font(self) -> ImageFont.FreeTypeFont:
        """Get or create the font for labels."""
        if self._font is None:
            try:
                self._font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", self.label_size)
            except (IOError, OSError):
                try:
                    self._font = ImageFont.truetype("arial.ttf", self.label_size)
                except (IOError, OSError):
                    self._font = ImageFont.load_default()
        return self._font

    def _get_column_label(self, col: int) -> str:
        """Convert column index to letter (0=A, 1=B, 2=C, etc.)."""
        return chr(ord('A') + col)

    def _get_cell_label(self, row: int, col: int) -> str:
        """Get cell label like 'A1', 'B2', etc."""
        return f"{self._get_column_label(col)}{row + 1}"

    def draw_grid(
        self,
        image: Union[str, Path, Image.Image, bytes],
        output_format: str = "pil",
    ) -> Tuple[Union[Image.Image, bytes, str], Dict[str, Dict[str, int]]]:
        """
        Draw a labeled grid on the image.

        Args:
            image: Input image (path, PIL Image, or bytes)
            output_format: Output format - "pil", "bytes", or "base64"

        Returns:
            Tuple of (annotated image, cell_map)
            cell_map maps cell labels to pixel coordinates:
            {"A1": {"x": 0, "y": 0, "width": 620, "height": 560}, ...}
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

        width, height = img.size
        cell_width = width // self.columns
        cell_height = height // self.rows

        draw = ImageDraw.Draw(img)
        font = self._get_font()

        # Build cell map
        cell_map = {}

        # Draw vertical lines and column labels
        for col in range(self.columns + 1):
            x = col * cell_width
            if x >= width:
                x = width - 1
            draw.line([(x, 0), (x, height)], fill=self.line_color, width=self.line_width)

        # Draw horizontal lines
        for row in range(self.rows + 1):
            y = row * cell_height
            if y >= height:
                y = height - 1
            draw.line([(0, y), (width, y)], fill=self.line_color, width=self.line_width)

        # Draw cell labels and build cell map
        for row in range(self.rows):
            for col in range(self.columns):
                cell_label = self._get_cell_label(row, col)

                # Calculate cell coordinates
                x = col * cell_width
                y = row * cell_height
                w = cell_width
                h = cell_height

                # Adjust last column/row to reach edge
                if col == self.columns - 1:
                    w = width - x
                if row == self.rows - 1:
                    h = height - y

                cell_map[cell_label] = {
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                }

                # Draw label in cell center
                label_bbox = draw.textbbox((0, 0), cell_label, font=font)
                label_width = label_bbox[2] - label_bbox[0]
                label_height = label_bbox[3] - label_bbox[1]

                label_x = x + (w - label_width) // 2
                label_y = y + (h - label_height) // 2

                # Draw background for label
                padding = 4
                draw.rectangle(
                    [label_x - padding, label_y - padding,
                     label_x + label_width + padding, label_y + label_height + padding],
                    fill=(255, 255, 255, 200)
                )

                # Draw label text
                draw.text((label_x, label_y), cell_label, fill=self.label_color, font=font)

        # Return in requested format
        if output_format == "pil":
            return img, cell_map
        elif output_format == "bytes":
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue(), cell_map
        elif output_format == "base64":
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8"), cell_map
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def cells_to_bbox(
        self,
        cells: List[str],
        cell_map: Dict[str, Dict[str, int]],
        padding: int = 10,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
    ) -> Optional[Dict[str, int]]:
        """
        Convert a list of cell labels to a bounding box.

        Args:
            cells: List of cell labels like ["A1", "A2", "B1", "B2"]
            cell_map: Cell map from draw_grid()
            padding: Padding to add around the combined box
            image_width: Image width to clamp bounding box (optional)
            image_height: Image height to clamp bounding box (optional)

        Returns:
            Bounding box dict {"x": ..., "y": ..., "width": ..., "height": ...}
            or None if no valid cells
        """
        if not cells:
            return None

        # Find min/max coordinates from all cells
        min_x = float('inf')
        min_y = float('inf')
        max_x = 0
        max_y = 0

        valid_cells = 0
        for cell in cells:
            cell = cell.strip().upper()
            if cell in cell_map:
                cell_info = cell_map[cell]
                min_x = min(min_x, cell_info["x"])
                min_y = min(min_y, cell_info["y"])
                max_x = max(max_x, cell_info["x"] + cell_info["width"])
                max_y = max(max_y, cell_info["y"] + cell_info["height"])
                valid_cells += 1

        if valid_cells == 0:
            return None

        # Apply padding (clamped to 0)
        min_x = max(0, min_x - padding)
        min_y = max(0, min_y - padding)
        max_x = max_x + padding
        max_y = max_y + padding

        # Clamp to image dimensions if provided
        if image_width is not None:
            max_x = min(max_x, image_width)
        if image_height is not None:
            max_y = min(max_y, image_height)

        # Calculate width and height
        width = int(max_x - min_x)
        height = int(max_y - min_y)

        # Ensure minimum size
        width = max(width, 50)
        height = max(height, 50)

        return {
            "x": int(min_x),
            "y": int(min_y),
            "width": width,
            "height": height,
        }

    def get_grid_description(self) -> str:
        """
        Get a text description of the grid for prompts.

        Returns:
            Description string explaining the grid layout
        """
        col_labels = [self._get_column_label(i) for i in range(self.columns)]
        row_labels = [str(i + 1) for i in range(self.rows)]

        return f"""The image has a {self.columns}x{self.rows} grid overlay:
- Columns: {', '.join(col_labels)} (left to right)
- Rows: {', '.join(row_labels)} (top to bottom)
- Cell labels: {col_labels[0]}{row_labels[0]} (top-left) to {col_labels[-1]}{row_labels[-1]} (bottom-right)
- Example: A product in the top-left area would be in cells A1, A2, B1, B2"""


# Singleton instance
_grid_overlay: Optional[GridOverlay] = None


def get_grid_overlay(columns: int = 4, rows: int = 6) -> GridOverlay:
    """Get or create the grid overlay singleton."""
    global _grid_overlay
    if _grid_overlay is None or _grid_overlay.columns != columns or _grid_overlay.rows != rows:
        _grid_overlay = GridOverlay(columns=columns, rows=rows)
    return _grid_overlay
