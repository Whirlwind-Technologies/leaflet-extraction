"""
OCR cache and pre-run helpers for Celery tasks.

Provides Redis-backed caching of PaddleOCR results so that pre-computed
bounding boxes are available to any Celery worker process during the
extraction pipeline.  Previously this was an in-process dict that broke
under multi-process deployments.

Key shape:   ``ocr:<leaflet_id>``  (Redis hash, field = page number)
Field value: JSON-serialized ``list[BoundingBox-as-dict]``
TTL:         1 hour from last write (cleared explicitly on completion)
"""

import json
import logging
from typing import Optional

import redis as _sync_redis

from app.core.extraction.schemas import BoundingBox

logger = logging.getLogger(__name__)

OCR_CACHE_TTL_SECONDS = 60 * 60


# ---------------------------------------------------------------------------
# PaddleOCR availability check
# ---------------------------------------------------------------------------

def _check_paddle_ocr_available() -> bool:
    """Check if PaddleOCR is available (lazy check)."""
    try:
        from app.core.image_processing.paddle_ocr_detector import is_paddle_ocr_available
        return is_paddle_ocr_available()
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Redis client helper
# ---------------------------------------------------------------------------

def _ocr_cache_key(leaflet_id: str) -> str:
    return f"ocr:{leaflet_id}"


def _get_sync_redis() -> Optional["_sync_redis.Redis"]:
    """Build a sync Redis client suitable for Celery workers."""
    from app.config import settings
    try:
        client = _sync_redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        client.ping()
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable for OCR cache: {e}")
        return None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_regions(regions: list) -> str:
    """Turn detector output into JSON we can stash in Redis."""
    payload = []
    for region in regions:
        if hasattr(region, "model_dump"):
            payload.append(region.model_dump())
        elif hasattr(region, "dict"):
            payload.append(region.dict())
        elif isinstance(region, dict):
            payload.append(region)
        else:
            # Best-effort fallback
            payload.append({k: getattr(region, k) for k in ("x", "y", "width", "height")})
    return json.dumps(payload)


def _deserialize_regions(raw: str) -> list:
    """Inverse of _serialize_regions; tolerate unknown shapes."""
    try:
        items = json.loads(raw)
    except (TypeError, ValueError):
        return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            out.append(BoundingBox(**item))
        except Exception:
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# Pre-run OCR
# ---------------------------------------------------------------------------

def _prerun_ocr_on_pages(
    page_images: list,
    page_info: list,
    leaflet_id: str,
) -> dict:
    """
    Pre-run PaddleOCR on all pages in parallel.

    Speeds up extraction by having OCR results ready before VLM calls.
    OCR typically takes 1-2 seconds per page vs 5-10 seconds for VLM.

    Args:
        page_images: List of image bytes (or None for failed downloads)
        page_info: List of page metadata dicts
        leaflet_id: Leaflet ID for cache key

    Returns:
        Dict mapping page_number -> OCR regions list
    """
    if not _check_paddle_ocr_available():
        logger.warning("PaddleOCR not available, skipping pre-OCR")
        return {}

    try:
        from app.core.image_processing.paddle_ocr_detector import get_paddle_ocr_detector
        import concurrent.futures

        ocr_detector = get_paddle_ocr_detector()
        results = {}

        def process_page(page_num: int, image_bytes: bytes, width: int, height: int):
            """Process a single page with OCR."""
            try:
                regions = ocr_detector.detect_product_regions(
                    image_bytes,
                    image_width=width,
                    image_height=height,
                )
                return page_num, regions
            except Exception as e:
                logger.error(
                    f"OCR failed for page {page_num}: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                return page_num, []

        # Sequential — PaddleOCR is not safe to initialise from multiple threads
        # concurrently ("Interface already registered" errors).
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            futures = []
            for i, (img, info) in enumerate(zip(page_images, page_info)):
                if img is not None and info is not None:
                    page_num = info.get("page_number", i + 1)
                    width = info.get("width", 2480)
                    height = info.get("height", 3508)
                    futures.append(
                        executor.submit(process_page, page_num, img, width, height)
                    )

            for future in concurrent.futures.as_completed(futures):
                try:
                    page_num, regions = future.result(timeout=180)  # 3min for large images
                    results[page_num] = regions
                except concurrent.futures.TimeoutError:
                    logger.error("Pre-OCR future timed out after 180s")
                except Exception as e:
                    logger.error(f"Pre-OCR future failed: {type(e).__name__}: {e}", exc_info=True)

        # Cache results in Redis so any worker process can read them later
        redis_client = _get_sync_redis()
        if redis_client is not None:
            try:
                key = _ocr_cache_key(leaflet_id)
                pipe = redis_client.pipeline()
                for page_num, regions in results.items():
                    pipe.hset(key, str(page_num), _serialize_regions(regions))
                pipe.expire(key, OCR_CACHE_TTL_SECONDS)
                pipe.execute()
            except Exception as e:
                logger.warning(f"Failed to persist OCR cache for {leaflet_id}: {e}")

        logger.info(
            f"Pre-OCR complete for {leaflet_id}: "
            f"{len(results)} pages, {sum(len(r) for r in results.values())} total regions"
        )

        return results

    except Exception as e:
        logger.error(f"Pre-OCR failed: {e}", exc_info=True)
        return {}


# ---------------------------------------------------------------------------
# Public cache accessors
# ---------------------------------------------------------------------------

def get_cached_ocr_results(leaflet_id: str, page_number: int) -> Optional[list]:
    """
    Get cached OCR results for a specific page from Redis.

    Args:
        leaflet_id: Leaflet ID
        page_number: Page number (1-indexed)

    Returns:
        List of OCR regions, or None if not cached or Redis unavailable.
    """
    redis_client = _get_sync_redis()
    if redis_client is None:
        return None
    try:
        raw = redis_client.hget(_ocr_cache_key(leaflet_id), str(page_number))
    except Exception as e:
        logger.warning(f"OCR cache read failed for {leaflet_id} p{page_number}: {e}")
        return None
    if raw is None:
        return None
    return _deserialize_regions(raw)


def clear_ocr_cache(leaflet_id: str):
    """Clear cached OCR results for a leaflet."""
    redis_client = _get_sync_redis()
    if redis_client is None:
        return
    try:
        redis_client.delete(_ocr_cache_key(leaflet_id))
    except Exception as e:
        logger.warning(f"OCR cache delete failed for {leaflet_id}: {e}")
