"""
Progress Publisher Module.

Publishes progress updates from Celery tasks to Redis pub/sub,
which can then be consumed by WebSocket handlers.

This provides a bridge between synchronous Celery tasks and
async WebSocket connections.

Example Usage:
    from app.core.progress import progress_publisher
    
    # In a Celery task
    progress_publisher.publish_progress(
        leaflet_id="LEAF_001",
        progress=0.5,
        message="Processing page 3 of 6"
    )
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)


class ProgressEventType(str, Enum):
    """Types of progress events."""
    
    STATUS_CHANGE = "status_change"
    PROGRESS_UPDATE = "progress_update"
    PAGE_COMPLETE = "page_complete"
    PRODUCT_EXTRACTED = "product_extracted"
    VALIDATION_COMPLETE = "validation_complete"
    ERROR = "error"
    COMPLETE = "complete"


class ProgressPublisher:
    """
    Publishes progress updates to Redis pub/sub.
    
    This is used by Celery tasks to publish progress updates
    that can be consumed by WebSocket handlers.
    
    Attributes:
        redis_client: Redis connection
        channel_prefix: Prefix for Redis channels
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        channel_prefix: str = "leaflet_progress:",
    ):
        """
        Initialize the publisher.
        
        Args:
            redis_url: Redis connection URL
            channel_prefix: Prefix for pub/sub channels
        """
        self.redis_url = redis_url or settings.redis_url
        self.channel_prefix = channel_prefix
        self._redis_client: Optional[redis.Redis] = None
    
    @property
    def redis_client(self) -> redis.Redis:
        """Get or create Redis client with connection health check.

        Verifies that the existing connection is still alive using a PING
        command. If the connection is stale or broken, it recreates the
        client transparently.

        Returns:
            A healthy Redis client instance.
        """
        if self._redis_client is None:
            self._redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                health_check_interval=30,
            )
        else:
            # Verify connection is still alive
            try:
                self._redis_client.ping()
            except (redis.ConnectionError, redis.TimeoutError):
                logger.warning("Redis connection stale, recreating...")
                try:
                    self._redis_client.close()
                except Exception:
                    pass
                self._redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    health_check_interval=30,
                )
        return self._redis_client
    
    def _get_channel(self, leaflet_id: str) -> str:
        """Get the Redis channel for a leaflet."""
        return f"{self.channel_prefix}{leaflet_id}"
    
    def publish_progress(
        self,
        leaflet_id: str,
        progress: float,
        message: str,
        event_type: ProgressEventType = ProgressEventType.PROGRESS_UPDATE,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Publish a progress update.
        
        Args:
            leaflet_id: The leaflet ID
            progress: Progress value (0.0 to 1.0)
            message: Human-readable message
            event_type: Type of event
            data: Additional data
            
        Returns:
            True if published successfully
        """
        try:
            event = {
                "leaflet_id": leaflet_id,
                "event_type": event_type.value,
                "progress": progress,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data or {},
            }
            
            channel = self._get_channel(leaflet_id)
            self.redis_client.publish(channel, json.dumps(event))
            
            # Also store in a key for late subscribers
            self.redis_client.setex(
                f"{self.channel_prefix}latest:{leaflet_id}",
                1800,  # 30 minute TTL (matches task timeout)
                json.dumps(event),
            )
            
            logger.debug(f"Published progress for {leaflet_id}: {progress:.0%}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish progress: {e}")
            return False
    
    def publish_page_complete(
        self,
        leaflet_id: str,
        page_number: int,
        total_pages: int,
        products_found: int,
        tokens_used: int = 0,
    ) -> bool:
        """
        Publish a page completion event.
        
        Args:
            leaflet_id: The leaflet ID
            page_number: Completed page number
            total_pages: Total pages
            products_found: Products found on this page
            tokens_used: API tokens used
            
        Returns:
            True if published successfully
        """
        progress = page_number / total_pages
        return self.publish_progress(
            leaflet_id=leaflet_id,
            progress=0.35 + (progress * 0.45),
            message=f"Extracted {products_found} products from page {page_number}/{total_pages}",
            event_type=ProgressEventType.PAGE_COMPLETE,
            data={
                "page_number": page_number,
                "total_pages": total_pages,
                "products_found": products_found,
                "tokens_used": tokens_used,
            },
        )
    
    def publish_extraction_start(
        self,
        leaflet_id: str,
        total_pages: int,
    ) -> bool:
        """
        Publish extraction start event.
        
        Args:
            leaflet_id: The leaflet ID
            total_pages: Total pages to process
            
        Returns:
            True if published successfully
        """
        return self.publish_progress(
            leaflet_id=leaflet_id,
            progress=0.35,
            message=f"Starting extraction for {total_pages} pages",
            event_type=ProgressEventType.STATUS_CHANGE,
            data={
                "status": "extracting",
                "total_pages": total_pages,
            },
        )
    
    def publish_validation_start(
        self,
        leaflet_id: str,
        total_products: int,
    ) -> bool:
        """
        Publish validation start event.
        
        Args:
            leaflet_id: The leaflet ID
            total_products: Total products to validate
            
        Returns:
            True if published successfully
        """
        return self.publish_progress(
            leaflet_id=leaflet_id,
            progress=0.80,
            message=f"Validating {total_products} products",
            event_type=ProgressEventType.STATUS_CHANGE,
            data={
                "status": "validating",
                "total_products": total_products,
            },
        )
    
    def publish_reconciliation(
        self,
        leaflet_id: str,
        merged_count: int,
        duplicate_count: int,
    ) -> bool:
        """
        Publish reconciliation event.
        
        Args:
            leaflet_id: The leaflet ID
            merged_count: Number of merged products
            duplicate_count: Number of duplicates removed
            
        Returns:
            True if published successfully
        """
        return self.publish_progress(
            leaflet_id=leaflet_id,
            progress=0.85,
            message=f"Reconciled products: {merged_count} merged, {duplicate_count} duplicates removed",
            event_type=ProgressEventType.VALIDATION_COMPLETE,
            data={
                "merged_count": merged_count,
                "duplicate_count": duplicate_count,
            },
        )
    
    def publish_status(
        self,
        leaflet_id: str,
        status: str,
        message: str,
        progress: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Publish a status change event.

        Args:
            leaflet_id: The leaflet ID
            status: New status string
            message: Human-readable message
            progress: Optional progress value (0.0 to 1.0)
            data: Additional data

        Returns:
            True if published successfully
        """
        # Default progress based on status
        if progress is None:
            status_progress = {
                "pending": 0.0,
                "processing": 0.1,
                "extracting": 0.35,
                "validating": 0.80,
                "reviewing": 0.90,
                "completed": 1.0,
                "failed": -1,
            }
            progress = status_progress.get(status, 0.5)

        return self.publish_progress(
            leaflet_id=leaflet_id,
            progress=progress,
            message=message,
            event_type=ProgressEventType.STATUS_CHANGE,
            data={"status": status, **(data or {})},
        )

    def publish_error(
        self,
        leaflet_id: str,
        error: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Publish an error event.
        
        Args:
            leaflet_id: The leaflet ID
            error: Error message
            details: Error details
            
        Returns:
            True if published successfully
        """
        return self.publish_progress(
            leaflet_id=leaflet_id,
            progress=-1,
            message=error,
            event_type=ProgressEventType.ERROR,
            data={"error": error, **(details or {})},
        )
    
    def publish_complete(
        self,
        leaflet_id: str,
        summary: Dict[str, Any],
    ) -> bool:
        """
        Publish a completion event.
        
        Args:
            leaflet_id: The leaflet ID
            summary: Completion summary
            
        Returns:
            True if published successfully
        """
        return self.publish_progress(
            leaflet_id=leaflet_id,
            progress=1.0,
            message="Processing complete",
            event_type=ProgressEventType.COMPLETE,
            data=summary,
        )
    
    def get_latest_progress(self, leaflet_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest progress for a leaflet.
        
        Args:
            leaflet_id: The leaflet ID
            
        Returns:
            Latest progress event or None
        """
        try:
            data = self.redis_client.get(f"{self.channel_prefix}latest:{leaflet_id}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get latest progress: {e}")
            return None
    
    def close(self):
        """Close the Redis connection."""
        if self._redis_client:
            self._redis_client.close()
            self._redis_client = None


# Singleton instance
_progress_publisher: Optional[ProgressPublisher] = None


def get_progress_publisher() -> ProgressPublisher:
    """Get the progress publisher singleton."""
    global _progress_publisher
    if _progress_publisher is None:
        _progress_publisher = ProgressPublisher()
    return _progress_publisher


# Convenience alias
progress_publisher = get_progress_publisher()