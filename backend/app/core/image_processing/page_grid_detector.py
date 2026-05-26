"""
Page Grid Detector.

Detects the actual product card grid layout from a page image using
projection profile analysis. This produces accurate bounding boxes
that VLMs cannot provide — VLMs are great at identifying products
but fabricate pixel coordinates.

Algorithm:
1. Convert to grayscale, compute row/column mean brightness profiles.
2. Detect brightness peaks (white/bright bands) = grid dividers.
3. Use VLM-reported column/row counts as hints for expected structure.
4. Return grid cell boundaries (in the coordinate space of the input image).
"""

import logging
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def detect_page_grid(
    image_data: bytes,
    num_cols_hint: int,
    num_rows_hint: int,
) -> Optional[Dict]:
    """
    Detect the product card grid from a page image.

    Uses projection profiles (row-wise and column-wise mean brightness)
    to locate horizontal and vertical dividers between product cards.

    Args:
        image_data: Image as bytes (JPEG or PNG).
        num_cols_hint: Expected column count (from VLM bbox clustering).
        num_rows_hint: Expected row count (from VLM bbox clustering).

    Returns:
        Dict with grid info, or None if detection fails:
        {
            'col_dividers': [int, ...],   # N+1 vertical boundaries
            'row_dividers': [int, ...],   # M+1 horizontal boundaries
            'num_cols': int,
            'num_rows': int,
            'cells': [(x, y, w, h), ...], # cells in reading order
        }
    """
    try:
        img = Image.open(BytesIO(image_data))
        img_w, img_h = img.size

        # Work at a manageable resolution (height ~500px)
        analysis_h = 500
        scale = analysis_h / img_h
        analysis_w = max(1, int(img_w * scale))
        small = img.resize((analysis_w, analysis_h), Image.Resampling.LANCZOS)
        gray = np.array(small.convert("L"), dtype=np.float64)

        # --- Detect horizontal dividers (between rows) ---
        row_profile = np.mean(gray, axis=1)  # mean brightness per row
        raw_h_dividers = _find_dividers(
            row_profile,
            expected_count=num_rows_hint + 1,
            min_spacing_frac=0.5 / max(1, num_rows_hint),
        )

        # --- Detect vertical dividers (between columns) ---
        col_profile = np.mean(gray, axis=0)  # mean brightness per column
        raw_v_dividers = _find_dividers(
            col_profile,
            expected_count=num_cols_hint + 1,
            min_spacing_frac=0.5 / max(1, num_cols_hint),
        )

        if len(raw_h_dividers) < 2 or len(raw_v_dividers) < 2:
            logger.warning(
                f"[GRID-DETECT] Too few dividers: "
                f"{len(raw_h_dividers)} horizontal, {len(raw_v_dividers)} vertical"
            )
            return None

        # Scale back to original image coordinates
        h_dividers = [int(d / scale) for d in raw_h_dividers]
        v_dividers = [int(d / scale) for d in raw_v_dividers]

        # Clamp to image bounds
        h_dividers = [max(0, min(d, img_h)) for d in h_dividers]
        v_dividers = [max(0, min(d, img_w)) for d in v_dividers]

        num_rows = len(h_dividers) - 1
        num_cols = len(v_dividers) - 1

        # Build cells in reading order (top-to-bottom, left-to-right)
        cells = []
        for r in range(num_rows):
            for c in range(num_cols):
                x = v_dividers[c]
                y = h_dividers[r]
                w = v_dividers[c + 1] - v_dividers[c]
                h = h_dividers[r + 1] - h_dividers[r]
                cells.append((x, y, w, h))

        logger.info(
            f"[GRID-DETECT] Detected {num_cols}x{num_rows} grid. "
            f"H-dividers: {h_dividers}. V-dividers: {v_dividers}"
        )

        return {
            "col_dividers": v_dividers,
            "row_dividers": h_dividers,
            "num_cols": num_cols,
            "num_rows": num_rows,
            "cells": cells,
        }

    except Exception as e:
        logger.error(f"[GRID-DETECT] Detection failed: {e}", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_dividers(
    profile: np.ndarray,
    expected_count: int,
    min_spacing_frac: float = 0.10,
) -> List[int]:
    """
    Find *expected_count* divider positions in a 1-D brightness profile.

    Dividers are bright bands (high mean brightness) that separate
    product rows or columns.  We always include position 0 and len-1
    as implicit edge dividers.

    Args:
        profile: 1-D array of mean brightness per row/column.
        expected_count: How many dividers to find (rows+1 or cols+1).
        min_spacing_frac: Minimum gap between dividers as fraction of length.

    Returns:
        Sorted list of divider positions.
    """
    n = len(profile)
    if n < 3 or expected_count < 2:
        return [0, n - 1]

    min_spacing = max(3, int(n * min_spacing_frac))

    # Smooth the profile to suppress noise
    kernel_size = max(3, n // 80)
    kernel = np.ones(kernel_size) / kernel_size
    smoothed = np.convolve(profile, kernel, mode="same")

    # Collect candidate peaks (local maxima of brightness)
    candidates: List[Tuple[int, float]] = []
    window = max(3, min_spacing // 3)

    for i in range(1, n - 1):
        lo = max(0, i - window)
        hi = min(n, i + window + 1)
        if smoothed[i] >= np.max(smoothed[lo:hi]):
            candidates.append((i, float(smoothed[i])))

    # Always include edges
    edges = [(0, float(smoothed[0])), (n - 1, float(smoothed[-1]))]

    # Sort candidates by brightness (brightest = most likely divider)
    candidates.sort(key=lambda c: c[1], reverse=True)

    # Greedily select peaks that respect min_spacing, starting with edges
    selected = [e[0] for e in edges]
    for pos, _brightness in candidates:
        if len(selected) >= expected_count:
            break
        if all(abs(pos - s) >= min_spacing for s in selected):
            selected.append(pos)

    selected.sort()

    # If still short, fill gaps with midpoints
    while len(selected) < expected_count:
        gaps = [(selected[i + 1] - selected[i], i) for i in range(len(selected) - 1)]
        if not gaps:
            break
        gaps.sort(reverse=True)
        gap_size, gap_idx = gaps[0]
        if gap_size < 4:
            break
        mid = selected[gap_idx] + gap_size // 2
        selected.insert(gap_idx + 1, mid)

    # Trim to exactly expected_count
    if len(selected) > expected_count:
        # Keep edges, remove weakest interior peaks
        interior = selected[1:-1]
        # Score each interior peak by its brightness
        scored = [(pos, float(smoothed[pos])) for pos in interior]
        scored.sort(key=lambda s: s[1], reverse=True)
        keep = expected_count - 2  # minus two edges
        kept = sorted([s[0] for s in scored[:keep]])
        selected = [selected[0]] + kept + [selected[-1]]

    return selected
