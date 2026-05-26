"""
Card Region Annotator.

Draws numbered colored boxes on a page image so the VLM can see
and reference detected product card regions by number.

Each region gets:
- A thick colored border (cycling through a distinct palette)
- A prominent number label in the top-left corner with contrasting background
- A semi-transparent fill so product content remains visible
"""

import logging
from io import BytesIO
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

# Allow large images (300 DPI leaflet pages can exceed default limit)
Image.MAX_IMAGE_PIXELS = 200_000_000

logger = logging.getLogger(__name__)

# Distinct colors that are easy to see on varied backgrounds.
# Each entry is (R, G, B).
REGION_COLORS: List[Tuple[int, int, int]] = [
    (220, 50, 50),    # Red
    (50, 80, 220),    # Blue
    (30, 170, 50),    # Green
    (220, 180, 30),   # Yellow
    (150, 50, 200),   # Purple
    (240, 130, 30),   # Orange
    (30, 190, 200),   # Cyan
    (200, 50, 150),   # Magenta
    (100, 180, 100),  # Light green
    (180, 100, 60),   # Brown
    (60, 60, 180),    # Dark blue
    (200, 100, 200),  # Pink
]

# Border width in pixels
BORDER_WIDTH = 4

# Label font size (approximate — PIL default font is bitmap)
LABEL_PADDING = 4

# Semi-transparent fill alpha (0 = invisible, 255 = opaque)
FILL_ALPHA = 30


def annotate_page_with_regions(
    image_data: bytes,
    regions: List[Dict],
) -> bytes:
    """
    Draw numbered region boxes on the page image.

    Args:
        image_data: Original page image as bytes (JPEG or PNG).
        regions: List of region dicts with keys: id, x, y, width, height.

    Returns:
        Annotated image as JPEG bytes.
    """
    try:
        img = Image.open(BytesIO(image_data)).convert("RGBA")
    except Exception as e:
        logger.error(f"[CARD-ANNOTATE] Failed to open image: {e}")
        return image_data  # Return original if we can't annotate

    # Create a transparent overlay for semi-transparent fills
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Draw on the main image for borders and labels
    draw = ImageDraw.Draw(img)

    # Try to get a larger font for labels; fall back to default
    font = _get_label_font()

    for region in regions:
        region_id = region["id"]
        x = region["x"]
        y = region["y"]
        w = region["width"]
        h = region["height"]

        color = REGION_COLORS[(region_id - 1) % len(REGION_COLORS)]
        fill_color = color + (FILL_ALPHA,)

        # Draw semi-transparent fill on overlay
        overlay_draw.rectangle(
            [x, y, x + w, y + h],
            fill=fill_color,
        )

        # Draw thick border on main image
        for i in range(BORDER_WIDTH):
            draw.rectangle(
                [x + i, y + i, x + w - i, y + h - i],
                outline=color + (255,),
            )

        # Draw number label with contrasting background
        label = str(region_id)
        _draw_label(draw, label, x, y, color, font)

    # Composite overlay onto main image
    img = Image.alpha_composite(img, overlay)

    # Convert to RGB (JPEG doesn't support alpha)
    img_rgb = img.convert("RGB")

    # Save as JPEG
    buffer = BytesIO()
    img_rgb.save(buffer, format="JPEG", quality=85)
    result_bytes = buffer.getvalue()

    img.close()
    img_rgb.close()
    overlay.close()

    logger.info(
        f"[CARD-ANNOTATE] Annotated image with {len(regions)} numbered regions "
        f"({len(result_bytes) // 1024}KB)"
    )

    return result_bytes


def _get_label_font():
    """Try to load a TrueType font for labels; fall back to default."""
    try:
        # Try common system font paths
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for font_path in font_candidates:
            try:
                return ImageFont.truetype(font_path, size=24)
            except (OSError, IOError):
                continue

        # If no system font found, try PIL's built-in
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def _draw_label(
    draw: ImageDraw.Draw,
    label: str,
    x: int,
    y: int,
    color: Tuple[int, int, int],
    font,
):
    """Draw a numbered label with a contrasting background rectangle."""
    # Measure text size
    try:
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception:
        # Fallback for very old Pillow versions
        text_w, text_h = 16, 16

    # Background rectangle (slightly larger than text)
    pad = LABEL_PADDING
    bg_x1 = x + BORDER_WIDTH
    bg_y1 = y + BORDER_WIDTH
    bg_x2 = bg_x1 + text_w + 2 * pad
    bg_y2 = bg_y1 + text_h + 2 * pad

    # Draw background (solid color for contrast)
    draw.rectangle(
        [bg_x1, bg_y1, bg_x2, bg_y2],
        fill=color + (230,),
    )

    # Draw text in white (contrasts with all palette colors)
    text_x = bg_x1 + pad
    text_y = bg_y1 + pad

    draw.text(
        (text_x, text_y),
        label,
        fill=(255, 255, 255, 255),
        font=font,
    )
