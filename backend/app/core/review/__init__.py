"""
Review Module.

Provides review routing, queue management, and auto-approval logic
for extracted products.

Example Usage:
    from app.core.review import (
        ReviewRouter,
        ReviewQueue,
        ReviewDecision,
    )
    
    router = ReviewRouter()
    decision = router.route_product(product, validation_result)
"""

from app.core.review.router import (
    ReviewRouter,
    ReviewDecision,
    ReviewPath,
)
from app.core.review.queue import (
    ReviewQueue,
    QueueItem,
    QueuePriority,
)

__all__ = [
    "ReviewRouter",
    "ReviewDecision",
    "ReviewPath",
    "ReviewQueue",
    "QueueItem",
    "QueuePriority",
]