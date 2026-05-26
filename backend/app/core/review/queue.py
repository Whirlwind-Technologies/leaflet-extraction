"""
Review Queue Module.

Manages the review queue for products requiring human review.
Supports priority-based ordering and batch operations.

Example Usage:
    from app.core.review.queue import ReviewQueue
    
    queue = ReviewQueue(redis_client)
    queue.add_product(product_id, leaflet_id, priority=75)
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class QueuePriority(IntEnum):
    """
    Priority levels for review queue.
    
    Lower values = lower priority.
    """
    LOW = 25
    NORMAL = 50
    HIGH = 75
    URGENT = 90
    CRITICAL = 100


@dataclass
class QueueItem:
    """
    Item in the review queue.
    
    Attributes:
        product_id: Product identifier
        leaflet_id: Parent leaflet identifier
        priority: Priority score (0-100)
        review_path: Assigned review path
        flagged_fields: Fields needing attention
        created_at: When added to queue
        assigned_to: Reviewer user ID (if assigned)
        estimated_time: Estimated review time (seconds)
        metadata: Additional metadata
    """
    product_id: str
    leaflet_id: str
    priority: int = 50
    review_path: str = "detailed_review"
    flagged_fields: List[str] = None
    created_at: str = None
    assigned_to: Optional[str] = None
    estimated_time: int = 30
    metadata: Dict = None
    
    def __post_init__(self):
        if self.flagged_fields is None:
            self.flagged_fields = []
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "QueueItem":
        """Create from dictionary."""
        return cls(**data)


class ReviewQueue:
    """
    Manages review queue operations.
    
    Uses Redis sorted sets for priority-based queuing.
    Supports multi-tenant queues (by leaflet or global).
    
    Attributes:
        redis_client: Redis client instance
        queue_prefix: Prefix for Redis keys
        default_ttl: Default TTL for queue items
        
    Example:
        >>> queue = ReviewQueue(redis_client)
        >>> queue.add_product("prod_001", "LEAF_001", priority=75)
        >>> next_items = queue.get_next_items(count=5)
    """
    
    # Redis key prefixes
    KEY_PREFIX = "review_queue"
    ITEM_PREFIX = "review_item"
    
    def __init__(
        self,
        redis_client: Any,
        queue_prefix: str = "default",
        default_ttl: int = 86400 * 7,  # 7 days
    ):
        """
        Initialize the review queue.
        
        Args:
            redis_client: Redis client
            queue_prefix: Queue namespace prefix
            default_ttl: Default TTL for items
        """
        self.redis = redis_client
        self.queue_prefix = queue_prefix
        self.default_ttl = default_ttl
    
    def _queue_key(self, leaflet_id: Optional[str] = None) -> str:
        """Generate Redis key for queue."""
        if leaflet_id:
            return f"{self.KEY_PREFIX}:{self.queue_prefix}:leaflet:{leaflet_id}"
        return f"{self.KEY_PREFIX}:{self.queue_prefix}:global"
    
    def _item_key(self, product_id: str) -> str:
        """Generate Redis key for queue item."""
        return f"{self.ITEM_PREFIX}:{self.queue_prefix}:{product_id}"
    
    def add_product(
        self,
        product_id: str,
        leaflet_id: str,
        priority: int = QueuePriority.NORMAL,
        review_path: str = "detailed_review",
        flagged_fields: Optional[List[str]] = None,
        estimated_time: int = 30,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Add a product to the review queue.
        
        Args:
            product_id: Product identifier
            leaflet_id: Leaflet identifier
            priority: Priority score (0-100)
            review_path: Review path type
            flagged_fields: Fields needing review
            estimated_time: Estimated review time
            metadata: Additional metadata
            
        Returns:
            True if added successfully
        """
        try:
            item = QueueItem(
                product_id=product_id,
                leaflet_id=leaflet_id,
                priority=priority,
                review_path=review_path,
                flagged_fields=flagged_fields or [],
                estimated_time=estimated_time,
                metadata=metadata or {},
            )
            
            # Store item data
            item_key = self._item_key(product_id)
            self.redis.setex(
                item_key,
                self.default_ttl,
                json.dumps(item.to_dict()),
            )
            
            # Add to sorted sets (global and leaflet-specific)
            # Using negative priority so highest priority = lowest score
            score = 100 - priority
            
            # Global queue
            self.redis.zadd(self._queue_key(), {product_id: score})
            
            # Leaflet-specific queue
            self.redis.zadd(self._queue_key(leaflet_id), {product_id: score})
            
            logger.debug(f"Added {product_id} to queue with priority {priority}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add {product_id} to queue: {e}")
            return False
    
    def add_batch(
        self,
        items: List[Dict],
    ) -> int:
        """
        Add multiple products to the queue.
        
        Args:
            items: List of item dictionaries with at least
                   'product_id', 'leaflet_id', 'priority'
                   
        Returns:
            Number of items added
        """
        added = 0
        
        for item in items:
            success = self.add_product(
                product_id=item["product_id"],
                leaflet_id=item["leaflet_id"],
                priority=item.get("priority", QueuePriority.NORMAL),
                review_path=item.get("review_path", "detailed_review"),
                flagged_fields=item.get("flagged_fields"),
                estimated_time=item.get("estimated_time", 30),
                metadata=item.get("metadata"),
            )
            if success:
                added += 1
        
        return added
    
    def get_next_items(
        self,
        count: int = 10,
        leaflet_id: Optional[str] = None,
    ) -> List[QueueItem]:
        """
        Get next items from queue by priority.
        
        Args:
            count: Number of items to retrieve
            leaflet_id: Filter by leaflet (optional)
            
        Returns:
            List of QueueItems ordered by priority
        """
        try:
            queue_key = self._queue_key(leaflet_id)
            
            # Get highest priority items (lowest scores)
            product_ids = self.redis.zrange(queue_key, 0, count - 1)
            
            if not product_ids:
                return []
            
            # Fetch item details
            items = []
            for pid in product_ids:
                if isinstance(pid, bytes):
                    pid = pid.decode()
                    
                item_key = self._item_key(pid)
                item_data = self.redis.get(item_key)
                
                if item_data:
                    if isinstance(item_data, bytes):
                        item_data = item_data.decode()
                    items.append(QueueItem.from_dict(json.loads(item_data)))
            
            return items
            
        except Exception as e:
            logger.error(f"Failed to get queue items: {e}")
            return []
    
    def get_item(self, product_id: str) -> Optional[QueueItem]:
        """Get a specific queue item."""
        try:
            item_key = self._item_key(product_id)
            item_data = self.redis.get(item_key)
            
            if item_data:
                if isinstance(item_data, bytes):
                    item_data = item_data.decode()
                return QueueItem.from_dict(json.loads(item_data))
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get item {product_id}: {e}")
            return None
    
    def remove_product(
        self,
        product_id: str,
        leaflet_id: Optional[str] = None,
    ) -> bool:
        """
        Remove a product from the queue.
        
        Args:
            product_id: Product to remove
            leaflet_id: Leaflet ID for queue cleanup
            
        Returns:
            True if removed
        """
        try:
            # Remove from global queue
            self.redis.zrem(self._queue_key(), product_id)
            
            # Remove from leaflet queue if known
            if leaflet_id:
                self.redis.zrem(self._queue_key(leaflet_id), product_id)
            
            # Remove item data
            self.redis.delete(self._item_key(product_id))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove {product_id}: {e}")
            return False
    
    def assign_item(
        self,
        product_id: str,
        reviewer_id: str,
    ) -> bool:
        """
        Assign an item to a reviewer.
        
        Args:
            product_id: Product to assign
            reviewer_id: Reviewer user ID
            
        Returns:
            True if assigned
        """
        try:
            item = self.get_item(product_id)
            if not item:
                return False
            
            item.assigned_to = reviewer_id
            
            # Update item data
            item_key = self._item_key(product_id)
            self.redis.setex(
                item_key,
                self.default_ttl,
                json.dumps(item.to_dict()),
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to assign {product_id}: {e}")
            return False
    
    def update_priority(
        self,
        product_id: str,
        new_priority: int,
        leaflet_id: Optional[str] = None,
    ) -> bool:
        """
        Update the priority of a queued item.
        
        Args:
            product_id: Product to update
            new_priority: New priority (0-100)
            leaflet_id: Leaflet ID for queue update
            
        Returns:
            True if updated
        """
        try:
            # Update sorted set score
            score = 100 - new_priority
            self.redis.zadd(self._queue_key(), {product_id: score})
            
            if leaflet_id:
                self.redis.zadd(self._queue_key(leaflet_id), {product_id: score})
            
            # Update item data
            item = self.get_item(product_id)
            if item:
                item.priority = new_priority
                self.redis.setex(
                    self._item_key(product_id),
                    self.default_ttl,
                    json.dumps(item.to_dict()),
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update priority for {product_id}: {e}")
            return False
    
    def get_queue_stats(
        self,
        leaflet_id: Optional[str] = None,
    ) -> Dict:
        """
        Get queue statistics.
        
        Args:
            leaflet_id: Filter by leaflet
            
        Returns:
            Dict with queue stats
        """
        try:
            queue_key = self._queue_key(leaflet_id)
            
            total = self.redis.zcard(queue_key)
            
            # Get priority distribution
            priority_ranges = {
                "critical": (0, 10),   # Score 0-10 = Priority 90-100
                "urgent": (10, 25),    # Score 10-25 = Priority 75-90
                "high": (25, 50),      # Score 25-50 = Priority 50-75
                "normal": (50, 75),    # Score 50-75 = Priority 25-50
                "low": (75, 100),      # Score 75-100 = Priority 0-25
            }
            
            distribution = {}
            for name, (min_score, max_score) in priority_ranges.items():
                count = self.redis.zcount(queue_key, min_score, max_score)
                distribution[name] = count
            
            return {
                "total_items": total,
                "priority_distribution": distribution,
                "queue_key": queue_key,
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {"total_items": 0, "priority_distribution": {}}
    
    def clear_queue(
        self,
        leaflet_id: Optional[str] = None,
    ) -> int:
        """
        Clear all items from a queue.
        
        Args:
            leaflet_id: Leaflet to clear (or global)
            
        Returns:
            Number of items cleared
        """
        try:
            queue_key = self._queue_key(leaflet_id)
            
            # Get all items first
            product_ids = self.redis.zrange(queue_key, 0, -1)
            count = len(product_ids)
            
            # Delete item data
            for pid in product_ids:
                if isinstance(pid, bytes):
                    pid = pid.decode()
                self.redis.delete(self._item_key(pid))
            
            # Clear the sorted set
            self.redis.delete(queue_key)
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            return 0


class InMemoryReviewQueue:
    """
    In-memory implementation of ReviewQueue for testing.
    
    Not suitable for production use - no persistence.
    """
    
    def __init__(self):
        self.items: Dict[str, QueueItem] = {}
        self.queues: Dict[str, List[str]] = {"global": []}
    
    def add_product(
        self,
        product_id: str,
        leaflet_id: str,
        priority: int = 50,
        **kwargs,
    ) -> bool:
        item = QueueItem(
            product_id=product_id,
            leaflet_id=leaflet_id,
            priority=priority,
            **kwargs,
        )
        self.items[product_id] = item
        
        # Add to queues
        if "global" not in self.queues:
            self.queues["global"] = []
        self.queues["global"].append(product_id)
        
        leaflet_key = f"leaflet:{leaflet_id}"
        if leaflet_key not in self.queues:
            self.queues[leaflet_key] = []
        self.queues[leaflet_key].append(product_id)
        
        # Sort by priority
        self._sort_queue("global")
        self._sort_queue(leaflet_key)
        
        return True
    
    def _sort_queue(self, queue_key: str):
        """Sort queue by priority (highest first)."""
        if queue_key in self.queues:
            self.queues[queue_key].sort(
                key=lambda pid: self.items.get(pid, QueueItem(pid, "")).priority,
                reverse=True,
            )
    
    def get_next_items(
        self,
        count: int = 10,
        leaflet_id: Optional[str] = None,
    ) -> List[QueueItem]:
        queue_key = f"leaflet:{leaflet_id}" if leaflet_id else "global"
        product_ids = self.queues.get(queue_key, [])[:count]
        return [self.items[pid] for pid in product_ids if pid in self.items]
    
    def remove_product(self, product_id: str, leaflet_id: Optional[str] = None) -> bool:
        if product_id in self.items:
            del self.items[product_id]
        
        for queue in self.queues.values():
            if product_id in queue:
                queue.remove(product_id)
        
        return True
    
    def get_queue_stats(self, leaflet_id: Optional[str] = None) -> Dict:
        queue_key = f"leaflet:{leaflet_id}" if leaflet_id else "global"
        return {"total_items": len(self.queues.get(queue_key, []))}