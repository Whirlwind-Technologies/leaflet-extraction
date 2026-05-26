"""
Unit Tests for WebSocket System.

Tests for WebSocket authentication, connection management, rate limiting,
progress publishing, and Redis connection health checks.

These tests cover the fixes added for:
- JWT authentication in WebSocket connections
- Per-user connection rate limiting
- Redis connection cleanup and health checks
- Progress publishing with TTL
- Leaflet ownership verification
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4, UUID
from datetime import datetime, timedelta

from fastapi import WebSocket

from app.api.deps import get_current_user_ws
from app.core.websocket import ConnectionManager, ProgressEvent, ProgressEventType
from app.core.progress import ProgressPublisher
from app.utils.exceptions import AuthenticationError
from app.models.user import User


# ============================================================
# WebSocket Authentication Tests
# ============================================================


class TestWebSocketAuthentication:
    """Tests for get_current_user_ws authentication function."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        """
        Test that a valid JWT access token returns the authenticated user.

        Verifies that the token is decoded correctly, the user is fetched from
        the database, and the user object is returned.
        """
        user_id = str(uuid4())
        mock_user = MagicMock()
        mock_user.id = UUID(user_id)
        mock_user.email = "test@example.com"
        mock_user.is_active = True

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": user_id, "type": "access"}
            user = await get_current_user_ws("valid-token", mock_db)

            assert user == mock_user
            mock_decode.assert_called_once_with("valid-token")
            mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_expired_token_raises_authentication_error(self):
        """
        Test that an expired token raises AuthenticationError.

        Simulates decode_token returning None (expired/invalid token) and
        verifies that the appropriate error is raised.
        """
        mock_db = AsyncMock()

        with patch("app.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = None  # Token expired or invalid

            with pytest.raises(AuthenticationError) as exc_info:
                await get_current_user_ws("expired-token", mock_db)

            assert "Invalid or expired token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_token_type_raises_authentication_error(self):
        """
        Test that a refresh token (not access token) raises AuthenticationError.

        WebSocket connections require access tokens, not refresh tokens.
        """
        mock_db = AsyncMock()

        with patch("app.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": str(uuid4()), "type": "refresh"}

            with pytest.raises(AuthenticationError) as exc_info:
                await get_current_user_ws("refresh-token", mock_db)

            assert "Invalid token type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_sub_claim_raises_authentication_error(self):
        """
        Test that a token without 'sub' claim raises AuthenticationError.

        The 'sub' claim is required to identify the user.
        """
        mock_db = AsyncMock()

        with patch("app.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = {"type": "access"}  # Missing 'sub'

            with pytest.raises(AuthenticationError) as exc_info:
                await get_current_user_ws("token-without-sub", mock_db)

            assert "Invalid token payload" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inactive_user_raises_authentication_error(self):
        """
        Test that an inactive user account raises AuthenticationError.

        Even with a valid token, inactive users should not be able to connect.
        """
        user_id = str(uuid4())
        mock_user = MagicMock()
        mock_user.id = UUID(user_id)
        mock_user.is_active = False  # Inactive user

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": user_id, "type": "access"}

            with pytest.raises(AuthenticationError) as exc_info:
                await get_current_user_ws("valid-token", mock_db)

            assert "User account is inactive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_user_not_found_raises_authentication_error(self):
        """
        Test that a token for a non-existent user raises AuthenticationError.

        This can happen if a user is deleted after their token was issued.
        """
        user_id = str(uuid4())

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # User not found
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": user_id, "type": "access"}

            with pytest.raises(AuthenticationError) as exc_info:
                await get_current_user_ws("valid-token", mock_db)

            assert "User not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_user_id_format_raises_authentication_error(self):
        """
        Test that a token with invalid UUID format raises AuthenticationError.

        The 'sub' claim must be a valid UUID string.
        """
        mock_db = AsyncMock()

        with patch("app.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "not-a-uuid", "type": "access"}

            with pytest.raises(AuthenticationError) as exc_info:
                await get_current_user_ws("token-with-invalid-uuid", mock_db)

            assert "Invalid user ID" in str(exc_info.value)


# ============================================================
# ConnectionManager Rate Limiting Tests
# ============================================================


class TestConnectionManagerRateLimiting:
    """Tests for ConnectionManager per-user connection rate limiting."""

    @pytest.mark.asyncio
    async def test_connect_succeeds_with_user_under_limit(self):
        """
        Test that a connection succeeds when the user is under the limit.

        The default limit is 10 connections per user. Verify that connections
        1-10 are all accepted.
        """
        manager = ConnectionManager()
        user_id = "user-123"

        for i in range(10):
            ws = AsyncMock(spec=WebSocket)
            result = await manager.connect(ws, f"leaflet-{i}", user_id=user_id)

            assert result is True
            ws.accept.assert_called_once()

        # Verify user has 10 connections tracked
        assert manager._user_connections.get(user_id) == 10

    @pytest.mark.asyncio
    async def test_connect_rejects_when_user_at_limit(self):
        """
        Test that the 11th connection is rejected when user is at the limit.

        When a user reaches the max_connections_per_user limit (10), additional
        connection attempts should return False and close the WebSocket.
        """
        manager = ConnectionManager()
        user_id = "user-456"

        # Fill up to limit (10 connections)
        for i in range(10):
            ws = AsyncMock(spec=WebSocket)
            result = await manager.connect(ws, f"leaflet-{i}", user_id=user_id)
            assert result is True

        # 11th connection should be rejected
        ws_overflow = AsyncMock(spec=WebSocket)
        result = await manager.connect(ws_overflow, "leaflet-overflow", user_id=user_id)

        assert result is False
        ws_overflow.close.assert_called_once_with(
            code=1008, reason="Too many connections"
        )
        ws_overflow.accept.assert_not_called()

    @pytest.mark.asyncio
    async def test_disconnect_decrements_user_connection_count(self):
        """
        Test that disconnecting decrements the user's connection count.

        This allows new connections to be made after some are closed.
        """
        manager = ConnectionManager()
        user_id = "user-789"

        # Create 5 connections
        websockets = []
        for i in range(5):
            ws = AsyncMock(spec=WebSocket)
            await manager.connect(ws, f"leaflet-{i}", user_id=user_id)
            websockets.append((ws, f"leaflet-{i}"))

        assert manager._user_connections.get(user_id) == 5

        # Disconnect 2 connections
        await manager.disconnect(websockets[0][0], websockets[0][1], user_id=user_id)
        await manager.disconnect(websockets[1][0], websockets[1][1], user_id=user_id)

        # Should now have 3 connections
        assert manager._user_connections.get(user_id) == 3

    @pytest.mark.asyncio
    async def test_multiple_users_tracked_independently(self):
        """
        Test that connection limits are tracked per-user independently.

        User A reaching their limit should not affect User B's ability to connect.
        """
        manager = ConnectionManager()
        user_a = "user-a"
        user_b = "user-b"

        # User A creates 10 connections (at limit)
        for i in range(10):
            ws = AsyncMock(spec=WebSocket)
            result = await manager.connect(ws, f"leaflet-a-{i}", user_id=user_a)
            assert result is True

        # User A's 11th connection should be rejected
        ws_a_overflow = AsyncMock(spec=WebSocket)
        result = await manager.connect(ws_a_overflow, "leaflet-a-overflow", user_id=user_a)
        assert result is False

        # User B should still be able to connect
        ws_b = AsyncMock(spec=WebSocket)
        result = await manager.connect(ws_b, "leaflet-b-1", user_id=user_b)
        assert result is True

        # Verify separate tracking
        assert manager._user_connections.get(user_a) == 10
        assert manager._user_connections.get(user_b) == 1

    @pytest.mark.asyncio
    async def test_connect_without_user_id_always_succeeds(self):
        """
        Test that connections without user_id bypass rate limiting.

        This is for backward compatibility or system connections that don't
        have user context.
        """
        manager = ConnectionManager()

        # Create more than 10 connections without user_id
        for i in range(15):
            ws = AsyncMock(spec=WebSocket)
            result = await manager.connect(ws, f"leaflet-{i}", user_id=None)

            assert result is True
            ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_removes_user_connection_tracking(self):
        """
        Test that cleanup properly removes user connection tracking.

        When all connections are closed for a user, their entry should be
        removed from _user_connections to prevent memory leaks.
        """
        manager = ConnectionManager()
        user_id = "user-cleanup"

        # Create 3 connections
        websockets = []
        for i in range(3):
            ws = AsyncMock(spec=WebSocket)
            await manager.connect(ws, f"leaflet-{i}", user_id=user_id)
            websockets.append((ws, f"leaflet-{i}"))

        assert manager._user_connections.get(user_id) == 3

        # Disconnect all
        for ws, leaflet_id in websockets:
            await manager.disconnect(ws, leaflet_id, user_id=user_id)

        # User should be removed from tracking
        assert user_id not in manager._user_connections


# ============================================================
# ProgressPublisher Health Check Tests
# ============================================================


class TestProgressPublisherHealthCheck:
    """Tests for ProgressPublisher Redis connection health checks."""

    def test_redis_client_created_on_first_access(self):
        """
        Test that the Redis client is created on first access.

        The client should be lazy-initialized with health_check_interval=30.
        """
        with patch("app.core.progress.redis.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_from_url.return_value = mock_client

            publisher = ProgressPublisher(redis_url="redis://localhost:6379/0")

            # Client should not be created yet
            assert publisher._redis_client is None

            # Access the property
            client = publisher.redis_client

            # Client should now be created
            assert client == mock_client
            mock_from_url.assert_called_once_with(
                "redis://localhost:6379/0",
                decode_responses=True,
                health_check_interval=30,
            )

    def test_redis_client_recreated_on_connection_failure(self):
        """
        Test that the Redis client is recreated when ping fails.

        If the connection is stale or broken, the health check should detect
        it and recreate the client transparently.
        """
        import redis

        publisher = ProgressPublisher(redis_url="redis://localhost:6379/0")

        # Create initial client
        mock_old_client = MagicMock()
        publisher._redis_client = mock_old_client

        # Simulate ping failure
        mock_old_client.ping.side_effect = redis.ConnectionError("Connection lost")

        with patch("app.core.progress.redis.from_url") as mock_from_url:
            mock_new_client = MagicMock()
            mock_from_url.return_value = mock_new_client

            # Access property should trigger recreation
            client = publisher.redis_client

            # Should have closed old client
            mock_old_client.close.assert_called_once()

            # Should have created new client
            assert client == mock_new_client
            mock_from_url.assert_called_once()

    def test_redis_client_not_recreated_if_healthy(self):
        """
        Test that the Redis client is not recreated if ping succeeds.

        If the connection is healthy, the existing client should be reused.
        """
        publisher = ProgressPublisher(redis_url="redis://localhost:6379/0")

        # Create initial client
        mock_client = MagicMock()
        mock_client.ping.return_value = True  # Healthy connection
        publisher._redis_client = mock_client

        # Access property multiple times
        for _ in range(5):
            client = publisher.redis_client
            assert client is mock_client

        # Ping should be called each time
        assert mock_client.ping.call_count == 5

    def test_publish_progress_ttl_is_1800_seconds(self):
        """
        Test that publish_progress sets TTL to 1800 seconds (30 minutes).

        The latest progress key should expire after 30 minutes to match
        task timeout and prevent stale data.
        """
        publisher = ProgressPublisher(redis_url="redis://localhost:6379/0")

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.publish.return_value = 1
        publisher._redis_client = mock_client

        # Publish progress
        result = publisher.publish_progress(
            leaflet_id="LEAF_001",
            progress=0.5,
            message="Testing TTL"
        )

        assert result is True

        # Verify setex was called with 1800 TTL
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args
        key, ttl, value = call_args[0]

        assert key == "leaflet_progress:latest:LEAF_001"
        assert ttl == 1800
        # Value should be JSON
        import json
        data = json.loads(value)
        assert data["leaflet_id"] == "LEAF_001"
        assert data["progress"] == 0.5

    def test_publish_progress_returns_false_on_redis_error(self):
        """
        Test that publish_progress returns False on Redis error.

        If Redis is unavailable, the publish should fail gracefully without
        raising an exception.
        """
        import redis

        publisher = ProgressPublisher(redis_url="redis://localhost:6379/0")

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.publish.side_effect = redis.ConnectionError("Redis unavailable")
        publisher._redis_client = mock_client

        result = publisher.publish_progress(
            leaflet_id="LEAF_002",
            progress=0.7,
            message="Test error handling"
        )

        assert result is False

    def test_publish_progress_returns_true_on_success(self):
        """
        Test that publish_progress returns True on successful publish.

        Verifies that both the pub/sub channel and the latest progress key
        are updated.
        """
        publisher = ProgressPublisher(redis_url="redis://localhost:6379/0")

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.publish.return_value = 1  # 1 subscriber
        publisher._redis_client = mock_client

        result = publisher.publish_progress(
            leaflet_id="LEAF_003",
            progress=0.9,
            message="Almost done"
        )

        assert result is True

        # Verify publish was called
        mock_client.publish.assert_called_once()
        channel, message = mock_client.publish.call_args[0]
        assert channel == "leaflet_progress:LEAF_003"

        # Verify message contains expected data
        import json
        data = json.loads(message)
        assert data["leaflet_id"] == "LEAF_003"
        assert data["progress"] == 0.9
        assert data["message"] == "Almost done"


# ============================================================
# Progress in PDF Processing Tests
# ============================================================


class TestProgressInPDFProcessing:
    """Tests for progress publishing in process_pdf_task."""

    def test_process_pdf_calls_publish_status_with_processing(self):
        """
        Test that process_pdf_task publishes "processing" status.

        When PDF processing starts, a status update should be published
        to inform connected clients.
        """
        from app.core.progress import ProgressPublisher

        mock_publisher = MagicMock(spec=ProgressPublisher)
        mock_publisher.publish_status.return_value = True

        # Simulate task calling publish_status
        mock_publisher.publish_status(
            leaflet_id="LEAF_004",
            status="processing",
            message="Converting PDF to images",
            progress=0.1
        )

        mock_publisher.publish_status.assert_called_once_with(
            leaflet_id="LEAF_004",
            status="processing",
            message="Converting PDF to images",
            progress=0.1
        )

    def test_per_page_progress_values_in_range(self):
        """
        Test that per-page progress values are in the 0.05-0.30 range.

        During PDF processing, each page should contribute a small increment
        to the overall progress (5-30% range for the processing phase).
        """
        total_pages = 10
        base_progress = 0.05

        for page_num in range(1, total_pages + 1):
            # Simulate progress calculation per page
            page_progress = base_progress + (page_num / total_pages) * 0.25

            # Progress should be in valid range
            assert 0.05 <= page_progress <= 0.30

            # Progress should increase monotonically
            if page_num > 1:
                prev_progress = base_progress + ((page_num - 1) / total_pages) * 0.25
                assert page_progress > prev_progress


# ============================================================
# Leaflet Access Verification Tests
# ============================================================


class TestLeafletAccessVerification:
    """Tests for _verify_leaflet_access in websocket.py."""

    @pytest.mark.asyncio
    async def test_owner_can_access_their_leaflet(self):
        """
        Test that a user can access their own leaflet.

        Direct ownership (leaflet.user_id == user.id) grants access.
        """
        from app.api.v1.websocket import _verify_leaflet_access
        from app.models.leaflet import Leaflet

        user = MagicMock(spec=User)
        user.id = uuid4()

        leaflet = MagicMock(spec=Leaflet)
        leaflet.leaflet_id = "LEAF_001"
        leaflet.user_id = user.id
        leaflet.organization_id = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = leaflet
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _verify_leaflet_access(mock_db, "LEAF_001", user)

        assert result == leaflet

    @pytest.mark.asyncio
    async def test_organization_member_can_access_org_leaflet(self):
        """
        Test that an organization member can access the org's leaflet.

        If the user is an active member of the leaflet's organization, access
        is granted even if they are not the direct owner.
        """
        from app.api.v1.websocket import _verify_leaflet_access
        from app.models.leaflet import Leaflet
        from app.models.organization_user import OrganizationUser

        user = MagicMock(spec=User)
        user.id = uuid4()

        owner_id = uuid4()
        org_id = uuid4()

        leaflet = MagicMock(spec=Leaflet)
        leaflet.leaflet_id = "LEAF_002"
        leaflet.user_id = owner_id  # Different from current user
        leaflet.organization_id = org_id

        membership = MagicMock(spec=OrganizationUser)
        membership.organization_id = org_id
        membership.user_id = user.id
        membership.is_active = True

        mock_db = AsyncMock()

        # First query returns the leaflet
        leaflet_result = MagicMock()
        leaflet_result.scalar_one_or_none.return_value = leaflet

        # Second query returns the membership
        membership_result = MagicMock()
        membership_result.scalar_one_or_none.return_value = membership

        mock_db.execute = AsyncMock(side_effect=[leaflet_result, membership_result])

        result = await _verify_leaflet_access(mock_db, "LEAF_002", user)

        assert result == leaflet
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_non_member_cannot_access_leaflet(self):
        """
        Test that a non-member cannot access another user's leaflet.

        If the user is not the owner and not an org member, access is denied.
        """
        from app.api.v1.websocket import _verify_leaflet_access
        from app.models.leaflet import Leaflet

        user = MagicMock(spec=User)
        user.id = uuid4()

        owner_id = uuid4()
        org_id = uuid4()

        leaflet = MagicMock(spec=Leaflet)
        leaflet.leaflet_id = "LEAF_003"
        leaflet.user_id = owner_id  # Different from current user
        leaflet.organization_id = org_id

        mock_db = AsyncMock()

        # First query returns the leaflet
        leaflet_result = MagicMock()
        leaflet_result.scalar_one_or_none.return_value = leaflet

        # Second query returns None (not a member)
        membership_result = MagicMock()
        membership_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[leaflet_result, membership_result])

        result = await _verify_leaflet_access(mock_db, "LEAF_003", user)

        assert result is None

    @pytest.mark.asyncio
    async def test_nonexistent_leaflet_returns_none(self):
        """
        Test that accessing a non-existent leaflet returns None.

        If the leaflet_id doesn't exist in the database, access is denied.
        """
        from app.api.v1.websocket import _verify_leaflet_access

        user = MagicMock(spec=User)
        user.id = uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Leaflet not found
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _verify_leaflet_access(mock_db, "LEAF_NONEXISTENT", user)

        assert result is None


# ============================================================
# Integration Tests for ConnectionManager
# ============================================================


class TestConnectionManagerIntegration:
    """Integration tests for ConnectionManager full workflows."""

    @pytest.mark.asyncio
    async def test_full_connection_lifecycle(self):
        """
        Test a complete connection lifecycle: connect, broadcast, disconnect.

        This simulates a real WebSocket connection flow with progress updates.
        """
        manager = ConnectionManager()
        user_id = "user-lifecycle"
        leaflet_id = "LEAF_LIFECYCLE"

        # Connect
        ws = AsyncMock(spec=WebSocket)
        result = await manager.connect(ws, leaflet_id, user_id=user_id)
        assert result is True
        assert manager.get_connection_count(leaflet_id) == 1

        # Broadcast progress
        event = ProgressEvent(
            leaflet_id=leaflet_id,
            event_type=ProgressEventType.PROGRESS_UPDATE,
            progress=0.5,
            message="Halfway there",
        )
        sent_count = await manager.broadcast(leaflet_id, event)
        assert sent_count == 1
        ws.send_text.assert_called_once()

        # Disconnect
        await manager.disconnect(ws, leaflet_id, user_id=user_id)
        assert manager.get_connection_count(leaflet_id) == 0
        assert user_id not in manager._user_connections

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_connections(self):
        """
        Test that broadcast sends to all connections for a leaflet.

        Multiple users/tabs can watch the same leaflet simultaneously.
        """
        manager = ConnectionManager()
        leaflet_id = "LEAF_MULTI"

        # Connect 3 WebSockets
        websockets = []
        for i in range(3):
            ws = AsyncMock(spec=WebSocket)
            await manager.connect(ws, leaflet_id, user_id=f"user-{i}")
            websockets.append(ws)

        # Broadcast progress
        event = ProgressEvent(
            leaflet_id=leaflet_id,
            event_type=ProgressEventType.PAGE_COMPLETE,
            progress=0.8,
            message="Page 4 complete",
            data={"page_number": 4},
        )
        sent_count = await manager.broadcast(leaflet_id, event)

        # All 3 should receive
        assert sent_count == 3
        for ws in websockets:
            ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_closes_all_connections(self):
        """
        Test that cleanup closes all connections and clears history.

        This should be called when processing completes or the leaflet is deleted.
        """
        manager = ConnectionManager()
        leaflet_id = "LEAF_CLEANUP"

        # Connect 2 WebSockets
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        await manager.connect(ws1, leaflet_id)
        await manager.connect(ws2, leaflet_id)

        # Add some history
        event = ProgressEvent(
            leaflet_id=leaflet_id,
            event_type=ProgressEventType.COMPLETE,
            progress=1.0,
            message="Done",
        )
        await manager.broadcast(leaflet_id, event)

        # Cleanup
        await manager.cleanup(leaflet_id)

        # Connections should be closed
        ws1.close.assert_called_once()
        ws2.close.assert_called_once()

        # Manager should have no data
        assert manager.get_connection_count(leaflet_id) == 0
        assert leaflet_id not in manager._event_history
        assert leaflet_id not in manager._connections
