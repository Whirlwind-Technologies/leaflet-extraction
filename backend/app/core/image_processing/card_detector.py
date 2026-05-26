"""
Card Region Detector.

Detects product card regions on a leaflet page image using a cascade:
1. Try projection-profile grid detection with quality validation.
2. Fallback: divide page into an equal grid.

Returns numbered regions in reading order (left-to-right, top-to-bottom)
ready for annotation and VLM matching.
"""

import logging
from io import BytesIO
from typing import Dict, List, Optional

from PIL import Image

# Allow large images (300 DPI leaflet pages can exceed default limit)
Image.MAX_IMAGE_PIXELS = 200_000_000

logger = logging.getLogger(__name__)

# Maximum ratio between largest and smallest cell dimension.
# If exceeded, the projection profile grid is considered unreliable
# (common with colorful leaflet backgrounds that create false dividers).
MAX_CELL_SIZE_RATIO = 2.5


def detect_card_regions(
    image_data: bytes,
    fallback_cols: int = 3,
    fallback_rows: int = 5,
) -> List[Dict]:
    """
    Detect product card regions on a page image.

    Strategy:
    1. Try projection profiles with increasing grid hints (2x3 → 2x4 → 3x4 → 4x5).
       Smaller grids are tried first so each cell is more likely to contain a
       whole product — cells that are too small split products across regions,
       causing the VLM to mix up prices between adjacent products.
    2. Final fallback: equal grid division (fallback_cols x fallback_rows).
       The default 3x5 produces 15 regions to better handle dense leaflets.
       For typical grocery leaflets with 8-15 products per page, this ensures
       most products get their own bounding box rather than sharing one.

    Args:
        image_data: Image as bytes (JPEG or PNG).
        fallback_cols: Number of columns for equal-grid fallback.
        fallback_rows: Number of rows for equal-grid fallback.

    Returns:
        List of region dicts, each with:
        {"id": int, "x": int, "y": int, "width": int, "height": int}
        Numbered 1..N in reading order.
    """
    try:
        img = Image.open(BytesIO(image_data))
        img_w, img_h = img.size
        img.close()
    except Exception as e:
        logger.error(f"[CARD-DETECT] Failed to open image: {e}")
        return _equal_grid(800, 1200, fallback_cols, fallback_rows)

    # Try projection profiles starting with grids appropriate for dense leaflets.
    # Most grocery leaflets have 8-15 products per page arranged in 2-3 columns
    # and 4-5 rows. We start with 3x4 (12 regions) as the minimum to ensure
    # each product gets its own bounding box. Smaller grids like 2x3 caused
    # multiple products to share the same region/image.
    grid_hints = [(3, 4), (3, 5), (4, 5), (4, 6)]
    for cols, rows in grid_hints:
        regions = _try_projection_profiles(image_data, img_w, img_h, num_cols=cols, num_rows=rows)
        if regions:
            logger.info(
                f"[CARD-DETECT] Projection profiles ({cols}x{rows}) detected {len(regions)} regions"
            )
            return regions

    # --- Fallback: equal grid (3x5 = 15 regions by default for dense leaflets) ---
    logger.info(
        f"[CARD-DETECT] Projection profiles failed all quality checks, using equal grid "
        f"{fallback_cols}x{fallback_rows}"
    )
    return _equal_grid(img_w, img_h, fallback_cols, fallback_rows)


def _try_projection_profiles(
    image_data: bytes,
    img_w: int,
    img_h: int,
    num_cols: int,
    num_rows: int,
) -> Optional[List[Dict]]:
    """
    Attempt grid detection via projection profiles with quality validation.

    Returns list of numbered region dicts or None if detection fails
    or the detected grid is too uneven.
    """
    try:
        from app.core.image_processing.page_grid_detector import detect_page_grid

        grid = detect_page_grid(
            image_data,
            num_cols_hint=num_cols,
            num_rows_hint=num_rows,
        )

        if grid is None:
            return None

        cells = grid["cells"]  # list of (x, y, w, h) tuples

        # Filter out degenerate cells (too small to be a product card)
        min_w = max(100, img_w // 20)
        min_h = max(120, img_h // 20)
        valid_cells = [
            (x, y, w, h) for (x, y, w, h) in cells
            if w >= min_w and h >= min_h
        ]

        if len(valid_cells) < 2:
            logger.info(
                f"[CARD-DETECT] Projection profiles ({num_cols}x{num_rows}): "
                f"too few valid cells ({len(valid_cells)})"
            )
            return None

        # --- Quality check: reject wildly uneven grids ---
        widths = [w for (_, _, w, _) in valid_cells]
        heights = [h for (_, _, _, h) in valid_cells]

        width_ratio = max(widths) / max(1, min(widths))
        height_ratio = max(heights) / max(1, min(heights))

        if width_ratio > MAX_CELL_SIZE_RATIO or height_ratio > MAX_CELL_SIZE_RATIO:
            logger.info(
                f"[CARD-DETECT] Projection profiles ({num_cols}x{num_rows}) rejected: "
                f"uneven grid (width ratio={width_ratio:.1f}, height ratio={height_ratio:.1f}, "
                f"max allowed={MAX_CELL_SIZE_RATIO}). "
                f"Widths: {sorted(set(widths))}, Heights: {sorted(set(heights))}"
            )
            return None

        logger.info(
            f"[CARD-DETECT] Projection profiles ({num_cols}x{num_rows}) quality OK: "
            f"width ratio={width_ratio:.1f}, height ratio={height_ratio:.1f}"
        )

        # Convert to numbered region dicts (already in reading order from grid detector)
        regions = []
        for idx, (x, y, w, h) in enumerate(valid_cells):
            regions.append({
                "id": idx + 1,
                "x": x,
                "y": y,
                "width": w,
                "height": h,
            })

        return regions

    except Exception as e:
        logger.warning(f"[CARD-DETECT] Projection profile attempt failed: {e}")
        return None


def _equal_grid(
    img_w: int,
    img_h: int,
    cols: int,
    rows: int,
    margin: int = 5,
) -> List[Dict]:
    """
    Divide the image into an equal grid with small margins between cells.

    Args:
        img_w: Image width in pixels.
        img_h: Image height in pixels.
        cols: Number of columns.
        rows: Number of rows.
        margin: Pixel margin between cells.

    Returns:
        List of numbered region dicts.
    """
    cell_w = img_w // cols
    cell_h = img_h // rows

    regions = []
    region_id = 1

    for r in range(rows):
        for c in range(cols):
            x = c * cell_w + margin
            y = r * cell_h + margin
            w = cell_w - 2 * margin
            h = cell_h - 2 * margin

            # Clamp to image bounds
            w = min(w, img_w - x)
            h = min(h, img_h - y)

            if w > 0 and h > 0:
                regions.append({
                    "id": region_id,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                })
                region_id += 1

    logger.info(
        f"[CARD-DETECT] Equal grid: {cols}x{rows} = {len(regions)} regions "
        f"(cell size: {cell_w}x{cell_h})"
    )

    return regions
