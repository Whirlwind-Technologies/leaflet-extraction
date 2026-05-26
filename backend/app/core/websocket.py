"""
WebSocket Manager Module.

Provides real-time progress updates for long-running tasks
like PDF processing and product extraction.

Example Usage:
    from app.core.websocket import ws_manager
    
    # In a task
    await ws_manager.broadcast_progress(
        leaflet_id="LEAF_001",
        progress=0.5,
        message="Extracting page 3 of 6"
    )
    
    # In an endpoint
    @router.websocket("/ws/progress/{leaflet_id}")
    async def websocket_endpoint(websocket: WebSocket, leaflet_id: str):
        await ws_manager.connect(websocket, leaflet_id)
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

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


@dataclass
class ProgressEvent:
    """Represents a progress update event."""
    
    leaflet_id: str
    event_type: ProgressEventType
    progress: float  # 0.0 to 1.0
    message: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps({
            "leaflet_id": self.leaflet_id,
            "event_type": self.event_type.value,
            "progress": self.progress,
            "message": self.message,
            "timestamp": self.timestamp,
            "data": self.data,
        })


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.

    NOTE: This is used ONLY by the FastAPI application process, not Celery workers.
    Celery tasks publish to Redis via ProgressPublisher. The WebSocket endpoints
    in websocket.py listen to Redis pub/sub and forward messages to connected clients.

    Supports:
    - Multiple connections per leaflet
    - Per-user connection limits to prevent resource exhaustion
    - Broadcasting to specific leaflets
    - Connection health monitoring
    - Automatic cleanup
    """

    def __init__(self):
        """Initialize the connection manager."""
        # Map of leaflet_id -> set of WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        # Event history for late joiners (last N events per leaflet)
        self._event_history: Dict[str, List[ProgressEvent]] = {}
        self._max_history = 20
        # Per-user connection tracking for rate limiting
        self._user_connections: Dict[str, int] = {}
        self._max_connections_per_user: int = 10
    
    async def connect(
        self,
        websocket: WebSocket,
        leaflet_id: str,
        user_id: Optional[str] = None,
        send_history: bool = True,
    ) -> bool:
        """
        Accept a WebSocket connection and register it.

        Enforces per-user connection limits to prevent resource exhaustion.
        If the user has too many open connections, the WebSocket is closed
        before being accepted.

        Args:
            websocket: The WebSocket connection.
            leaflet_id: The leaflet to subscribe to.
            user_id: Optional user ID for per-user connection tracking.
            send_history: Whether to send recent event history.

        Returns:
            True if the connection was accepted, False if rejected due
            to per-user connection limit.
        """
        # Check per-user connection limit before accepting
        if user_id and self._user_connections.get(user_id, 0) >= self._max_connections_per_user:
            logger.warning(
                f"WebSocket connection rejected for user {user_id}: "
                f"limit of {self._max_connections_per_user} connections exceeded"
            )
            await websocket.close(code=1008, reason="Too many connections")
            return False

        await websocket.accept()

        async with self._lock:
            if leaflet_id not in self._connections:
                self._connections[leaflet_id] = set()
            self._connections[leaflet_id].add(websocket)

            if user_id:
                self._user_connections[user_id] = self._user_connections.get(user_id, 0) + 1

        logger.info(
            f"WebSocket connected for leaflet {leaflet_id}. "
            f"Total connections: {len(self._connections.get(leaflet_id, set()))}"
        )

        # Send recent history
        if send_history and leaflet_id in self._event_history:
            for event in self._event_history[leaflet_id][-10:]:
                try:
                    await websocket.send_text(event.to_json())
                except Exception:
                    pass

        return True
    
    async def disconnect(
        self,
        websocket: WebSocket,
        leaflet_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Remove a WebSocket connection and decrement user tracking.

        Args:
            websocket: The WebSocket to remove.
            leaflet_id: The leaflet it was subscribed to.
            user_id: Optional user ID for per-user connection tracking.
        """
        async with self._lock:
            if leaflet_id in self._connections:
                self._connections[leaflet_id].discard(websocket)
                if not self._connections[leaflet_id]:
                    del self._connections[leaflet_id]

            if user_id and user_id in self._user_connections:
                self._user_connections[user_id] = max(
                    0, self._user_connections[user_id] - 1
                )
                if self._user_connections[user_id] == 0:
                    del self._user_connections[user_id]

        logger.info(f"WebSocket disconnected for leaflet {leaflet_id}")
    
    async def broadcast(
        self,
        leaflet_id: str,
        event: ProgressEvent,
    ) -> int:
        """
        Broadcast an event to all connections for a leaflet.
        
        Args:
            leaflet_id: The leaflet to broadcast to
            event: The event to broadcast
            
        Returns:
            Number of successful sends
        """
        # Store in history
        async with self._lock:
            if leaflet_id not in self._event_history:
                self._event_history[leaflet_id] = []
            self._event_history[leaflet_id].append(event)
            # Trim history
            if len(self._event_history[leaflet_id]) > self._max_history:
                self._event_history[leaflet_id] = self._event_history[leaflet_id][-self._max_history:]
        
        connections = self._connections.get(leaflet_id, set()).copy()
        
        if not connections:
            return 0
        
        message = event.to_json()
        successful = 0
        dead_connections = []
        
        for websocket in connections:
            try:
                await websocket.send_text(message)
                successful += 1
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                dead_connections.append(websocket)
        
        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for ws in dead_connections:
                    self._connections.get(leaflet_id, set()).discard(ws)
        
        return successful
    
    async def broadcast_progress(
        self,
        leaflet_id: str,
        progress: float,
        message: str,
        event_type: ProgressEventType = ProgressEventType.PROGRESS_UPDATE,
        data: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Convenience method to broadcast a progress update.
        
        Args:
            leaflet_id: The leaflet ID
            progress: Progress value (0.0 to 1.0)
            message: Human-readable message
            event_type: Type of event
            data: Additional data
            
        Returns:
            Number of successful sends
        """
        event = ProgressEvent(
            leaflet_id=leaflet_id,
            event_type=event_type,
            progress=progress,
            message=message,
            data=data or {},
        )
        return await self.broadcast(leaflet_id, event)
    
    async def broadcast_page_complete(
        self,
        leaflet_id: str,
        page_number: int,
        total_pages: int,
        products_found: int,
    ) -> int:
        """
        Broadcast a page completion event.
        
        Args:
            leaflet_id: The leaflet ID
            page_number: Completed page number
            total_pages: Total pages
            products_found: Products found on this page
            
        Returns:
            Number of successful sends
        """
        progress = page_number / total_pages
        return await self.broadcast_progress(
            leaflet_id=leaflet_id,
            progress=0.35 + (progress * 0.45),  # Map to extraction phase
            message=f"Extracted {products_found} products from page {page_number}/{total_pages}",
            event_type=ProgressEventType.PAGE_COMPLETE,
            data={
                "page_number": page_number,
                "total_pages": total_pages,
                "products_found": products_found,
            },
        )
    
    async def broadcast_error(
        self,
        leaflet_id: str,
        error: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Broadcast an error event.
        
        Args:
            leaflet_id: The leaflet ID
            error: Error message
            details: Error details
            
        Returns:
            Number of successful sends
        """
        return await self.broadcast_progress(
            leaflet_id=leaflet_id,
            progress=-1,  # Indicate error
            message=error,
            event_type=ProgressEventType.ERROR,
            data={"error": error, **(details or {})},
        )
    
    async def broadcast_complete(
        self,
        leaflet_id: str,
        summary: Dict[str, Any],
    ) -> int:
        """
        Broadcast a completion event.
        
        Args:
            leaflet_id: The leaflet ID
            summary: Completion summary
            
        Returns:
            Number of successful sends
        """
        return await self.broadcast_progress(
            leaflet_id=leaflet_id,
            progress=1.0,
            message="Processing complete",
            event_type=ProgressEventType.COMPLETE,
            data=summary,
        )
    
    def get_connection_count(self, leaflet_id: str) -> int:
        """Get number of active connections for a leaflet."""
        return len(self._connections.get(leaflet_id, set()))
    
    def get_all_leaflet_ids(self) -> List[str]:
        """Get all leaflet IDs with active connections."""
        return list(self._connections.keys())
    
    async def cleanup(self, leaflet_id: str) -> None:
        """
        Clean up all connections and history for a leaflet.
        
        Call this after processing is complete.
        
        Args:
            leaflet_id: The leaflet to clean up
        """
        async with self._lock:
            if leaflet_id in self._connections:
                # Close all connections
                for ws in list(self._connections[leaflet_id]):
                    try:
                        await ws.close()
                    except Exception:
                        pass
                del self._connections[leaflet_id]
            
            if leaflet_id in self._event_history:
                del self._event_history[leaflet_id]
        
        logger.info(f"Cleaned up WebSocket resources for leaflet {leaflet_id}")


# Singleton instance
ws_manager = ConnectionManager()


def get_ws_manager() -> ConnectionManager:
    """Get the WebSocket manager singleton."""
    return ws_manager