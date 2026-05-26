"""
WebSocket API for Real-Time Progress Updates.

This module provides WebSocket endpoints for real-time progress
tracking of PDF processing and product extraction tasks.

All WebSocket endpoints require JWT authentication via a ``token``
query parameter. Ownership of the requested resource is verified
before the connection is accepted.

Example Usage:
    // In frontend
    const ws = new WebSocket(
        'ws://localhost:8000/api/v1/ws/progress/LEAF_001?token=eyJ...'
    );
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(`Progress: ${data.progress * 100}%`);
    };
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.api.deps import get_current_user, get_current_user_ws
from app.config import settings
from app.core.websocket import ws_manager
from app.models.leaflet import Leaflet
from app.models.organization_user import OrganizationUser
from app.models.user import User
from app.utils.database import get_async_session_factory, get_db

logger = logging.getLogger(__name__)
router = APIRouter()


async def _verify_leaflet_access(
    db: AsyncSession,
    leaflet_id: str,
    user: User,
) -> Optional[Leaflet]:
    """
    Verify that a user has access to a leaflet.

    Checks direct ownership (user_id matches) or membership in the
    leaflet's organization.

    Args:
        db: Async database session.
        leaflet_id: Human-readable leaflet ID (e.g., LEAF_2025_001234).
        user: Authenticated user to check access for.

    Returns:
        The Leaflet instance if access is granted, None otherwise.
    """
    result = await db.execute(
        select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
    )
    leaflet = result.scalar_one_or_none()
    if not leaflet:
        return None

    # Direct ownership check
    if leaflet.user_id == user.id:
        return leaflet

    # Organization membership check
    org_check = await db.execute(
        select(OrganizationUser).where(
            OrganizationUser.organization_id == leaflet.organization_id,
            OrganizationUser.user_id == user.id,
            OrganizationUser.is_active == True,
        )
    )
    if org_check.scalar_one_or_none() is not None:
        return leaflet

    return None


@router.websocket("/progress/{leaflet_id}")
async def websocket_progress(
    websocket: WebSocket,
    leaflet_id: str,
    token: str = Query(None, description="JWT access token"),
):
    """
    WebSocket endpoint for real-time progress updates on a single leaflet.

    Authenticates the user via JWT token query parameter, verifies the
    user has access to the leaflet (ownership or organization membership),
    then subscribes to Redis pub/sub for progress events.

    Args:
        websocket: WebSocket connection.
        leaflet_id: Leaflet ID to subscribe to.
        token: JWT access token from query parameter.
    """
    # Auth check BEFORE accepting the connection
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    user_id_str: Optional[str] = None

    try:
        session_factory = get_async_session_factory()
        async with session_factory() as db:
            user = await get_current_user_ws(token, db)
            user_id_str = str(user.id)

            # Verify user has access to this leaflet
            leaflet = await _verify_leaflet_access(db, leaflet_id, user)
            if not leaflet:
                await websocket.close(code=1008, reason="Leaflet not found or access denied")
                return
    except Exception as e:
        logger.warning(f"WebSocket auth failed for {leaflet_id}: {e}")
        try:
            await websocket.close(code=1008, reason="Authentication failed")
        except Exception:
            pass
        return

    # Auth succeeded; proceed with the connection
    redis_client = None
    pubsub = None
    channel = f"leaflet_progress:{leaflet_id}"

    try:
        accepted = await ws_manager.connect(
            websocket, leaflet_id, user_id=user_id_str
        )
        if not accepted:
            return

        redis_client = aioredis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        # Send latest progress if available
        latest = await redis_client.get(f"leaflet_progress:latest:{leaflet_id}")
        if latest:
            await websocket.send_text(latest)

        # Listen for messages from Redis
        async def listen_redis():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        await websocket.send_text(message["data"])
                    except Exception as e:
                        logger.warning(f"Failed to send WebSocket message: {e}")
                        break

        # Handle incoming WebSocket messages (ping/pong)
        async def listen_websocket():
            try:
                while True:
                    data = await websocket.receive_text()
                    if data == "ping":
                        await websocket.send_text("pong")
            except WebSocketDisconnect:
                pass

        # Run both listeners concurrently
        await asyncio.gather(
            listen_redis(),
            listen_websocket(),
            return_exceptions=True,
        )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {leaflet_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {leaflet_id}: {e}")
    finally:
        await ws_manager.disconnect(websocket, leaflet_id, user_id=user_id_str)
        if pubsub:
            try:
                await pubsub.unsubscribe(channel)
            except Exception as e:
                logger.warning(f"Failed to unsubscribe from {channel}: {e}")
        if redis_client:
            try:
                await redis_client.close()
            except Exception as e:
                logger.warning(f"Failed to close Redis connection: {e}")


@router.websocket("/progress")
async def websocket_all_progress(
    websocket: WebSocket,
    leaflet_ids: str = Query(None, description="Comma-separated leaflet IDs"),
    token: str = Query(None, description="JWT access token"),
):
    """
    WebSocket endpoint for progress on multiple leaflets.

    Authenticates the user and verifies access to ALL requested leaflets
    before accepting the connection. If any leaflet is inaccessible,
    the connection is rejected.

    Args:
        websocket: WebSocket connection.
        leaflet_ids: Comma-separated list of leaflet IDs.
        token: JWT access token from query parameter.
    """
    # Auth check BEFORE accepting the connection
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    user_id_str: Optional[str] = None

    try:
        session_factory = get_async_session_factory()
        async with session_factory() as db:
            user = await get_current_user_ws(token, db)
            user_id_str = str(user.id)

            if not leaflet_ids:
                await websocket.close(code=1008, reason="No leaflet_ids provided")
                return

            ids = [lid.strip() for lid in leaflet_ids.split(",") if lid.strip()]
            if not ids:
                await websocket.close(code=1008, reason="No valid leaflet_ids provided")
                return

            # Verify access to ALL requested leaflets
            for lid in ids:
                leaflet = await _verify_leaflet_access(db, lid, user)
                if not leaflet:
                    await websocket.close(
                        code=1008,
                        reason=f"Leaflet not found or access denied: {lid}",
                    )
                    return
    except Exception as e:
        logger.warning(f"WebSocket auth failed for multi-leaflet: {e}")
        try:
            await websocket.close(code=1008, reason="Authentication failed")
        except Exception:
            pass
        return

    # Auth succeeded; proceed with the connection
    redis_client = None
    pubsub = None
    channels = [f"leaflet_progress:{lid}" for lid in ids]
    # Use a synthetic group key for the connection manager
    group_key = f"multi:{','.join(ids[:5])}"

    try:
        await websocket.accept()

        redis_client = aioredis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(*channels)

        # Send latest progress for each leaflet
        for lid in ids:
            latest = await redis_client.get(f"leaflet_progress:latest:{lid}")
            if latest:
                await websocket.send_text(latest)

        # Listen for messages from Redis
        async def listen_redis():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        await websocket.send_text(message["data"])
                    except Exception:
                        break

        # Handle incoming WebSocket messages (ping/pong)
        async def listen_websocket():
            try:
                while True:
                    data = await websocket.receive_text()
                    if data == "ping":
                        await websocket.send_text("pong")
            except WebSocketDisconnect:
                pass

        await asyncio.gather(
            listen_redis(),
            listen_websocket(),
            return_exceptions=True,
        )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected (multi-leaflet)")
    except Exception as e:
        logger.error(f"WebSocket error (multi-leaflet): {e}")
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(*channels)
            except Exception as e:
                logger.warning(f"Failed to unsubscribe from channels: {e}")
        if redis_client:
            try:
                await redis_client.close()
            except Exception as e:
                logger.warning(f"Failed to close Redis connection: {e}")


@router.websocket("/notifications/{user_id}")
async def websocket_notifications(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(None, description="JWT access token"),
):
    """
    WebSocket endpoint for real-time notification updates.

    Authenticates the user and verifies that the authenticated user
    matches the requested user_id. This prevents users from subscribing
    to another user's notification channel.

    Args:
        websocket: WebSocket connection.
        user_id: User ID to subscribe to notifications for.
        token: JWT access token from query parameter.
    """
    # Auth check BEFORE accepting the connection
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    authenticated_user_id: Optional[str] = None

    try:
        session_factory = get_async_session_factory()
        async with session_factory() as db:
            user = await get_current_user_ws(token, db)
            authenticated_user_id = str(user.id)

            # Verify the authenticated user matches the requested user_id
            if authenticated_user_id != user_id:
                await websocket.close(code=1008, reason="Access denied")
                return
    except Exception as e:
        logger.warning(f"WebSocket auth failed for notifications user {user_id}: {e}")
        try:
            await websocket.close(code=1008, reason="Authentication failed")
        except Exception:
            pass
        return

    # Auth succeeded; proceed with the connection
    redis_client = None
    pubsub = None
    user_channel = f"notifications:user:{user_id}"
    global_channel = "notifications:global"

    try:
        await websocket.accept()

        redis_client = aioredis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(user_channel, global_channel)

        logger.info(f"WebSocket connected for notifications: user={user_id}")

        # Listen for messages from Redis
        async def listen_redis():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        await websocket.send_text(message["data"])
                    except Exception as e:
                        logger.warning(f"Failed to send notification WebSocket message: {e}")
                        break

        # Handle incoming WebSocket messages (ping/pong)
        async def listen_websocket():
            try:
                while True:
                    data = await websocket.receive_text()
                    if data == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
            except WebSocketDisconnect:
                pass

        await asyncio.gather(
            listen_redis(),
            listen_websocket(),
            return_exceptions=True,
        )

    except WebSocketDisconnect:
        logger.info(f"Notification WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"Notification WebSocket error for user {user_id}: {e}")
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(user_channel, global_channel)
            except Exception as e:
                logger.warning(f"Failed to unsubscribe from notification channels: {e}")
        if redis_client:
            try:
                await redis_client.close()
            except Exception as e:
                logger.warning(f"Failed to close Redis connection: {e}")


@router.get("/progress/{leaflet_id}/latest")
async def get_latest_progress(
    leaflet_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get the latest progress for a leaflet.

    This is useful for initial page load before WebSocket connects.
    Requires authentication and verifies the user has access to the
    requested leaflet.

    Args:
        leaflet_id: Leaflet ID.
        current_user: Authenticated user from JWT token.
        db: Async database session.

    Returns:
        Latest progress event or status message.
    """
    # Verify user has access to this leaflet
    leaflet = await _verify_leaflet_access(db, leaflet_id, current_user)
    if not leaflet:
        return {
            "leaflet_id": leaflet_id,
            "error": "Leaflet not found or access denied",
        }

    redis_client = None
    try:
        redis_client = aioredis.from_url(settings.redis_url)
        latest = await redis_client.get(f"leaflet_progress:latest:{leaflet_id}")

        if latest:
            return json.loads(latest)

        return {
            "leaflet_id": leaflet_id,
            "event_type": "unknown",
            "progress": -1,
            "message": "No progress data available",
        }
    except Exception as e:
        logger.error(f"Failed to get latest progress: {e}")
        return {
            "leaflet_id": leaflet_id,
            "error": str(e),
        }
    finally:
        if redis_client:
            try:
                await redis_client.close()
            except Exception:
                pass
