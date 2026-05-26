"""
Unit Tests for Contact Form API.

Tests for the public contact form endpoint with 5-layer spam protection:
1. Honeypot field detection
2. Time-based validation (too fast / too old)
3. Redis-backed rate limiting (per-email, per-IP, global)
4. reCAPTCHA v3 verification (optional)
5. Content validation (URLs, script tags, duplicates)
"""

import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient


class TestContactFormHoneypot:
    """Tests for honeypot field detection (Layer 1)."""

    @pytest.mark.asyncio
    async def test_honeypot_filled_silent_reject(self, client: AsyncClient):
        """POST with website field filled returns 200 with success message (silent reject)."""
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "Bot User",
                "email": "bot@example.com",
                "message": "This is spam",
                "website": "https://spam.com",  # Honeypot filled
                "timestamp": time.time(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Thank you, we'll be in touch."

    @pytest.mark.asyncio
    async def test_honeypot_empty_passes(self, client: AsyncClient):
        """POST with empty website field passes honeypot check."""
        current_time = time.time() - 10  # 10 seconds ago

        with patch("app.api.v1.contact.get_redis_client") as mock_redis, \
             patch("app.api.v1.contact.send_contact_emails_task") as mock_task:
            # Mock Redis to pass rate limiting
            mock_redis_instance = MagicMock()
            mock_redis_instance.incr = AsyncMock(return_value=1)
            mock_redis_instance.expire = AsyncMock()
            mock_redis_instance.exists = AsyncMock(return_value=False)
            mock_redis_instance.setex = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Mock Celery task
            mock_task.delay = MagicMock()

            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "Real User",
                    "email": "real@example.com",
                    "message": "This is a legitimate message",
                    "website": "",  # Empty honeypot
                    "timestamp": current_time,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Verify task was called (not a silent reject)
        mock_task.delay.assert_called_once()


class TestContactFormTimingValidation:
    """Tests for time-based validation (Layer 2)."""

    @pytest.mark.asyncio
    async def test_submit_too_fast_silent_reject(self, client: AsyncClient):
        """Submit within 3 seconds returns 200 silent reject."""
        current_time = time.time()
        timestamp = current_time - 1  # Submitted 1 second after render

        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "Fast User",
                "email": "fast@example.com",
                "message": "Quick message",
                "website": "",
                "timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Thank you, we'll be in touch."

    @pytest.mark.asyncio
    async def test_submit_too_old_silent_reject(self, client: AsyncClient):
        """Submit with timestamp >2 hours old returns 200 silent reject."""
        current_time = time.time()
        timestamp = current_time - 7300  # 2 hours + 100 seconds ago

        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "Old Form User",
                "email": "old@example.com",
                "message": "Old message",
                "website": "",
                "timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Thank you, we'll be in touch."

    @pytest.mark.asyncio
    async def test_valid_timing_passes(self, client: AsyncClient):
        """Submit with timestamp 10 seconds old passes timing check."""
        current_time = time.time()
        timestamp = current_time - 10  # 10 seconds ago (valid)

        with patch("app.api.v1.contact.get_redis_client") as mock_redis, \
             patch("app.api.v1.contact.send_contact_emails_task") as mock_task:
            # Mock Redis to pass rate limiting
            mock_redis_instance = MagicMock()
            mock_redis_instance.incr = AsyncMock(return_value=1)
            mock_redis_instance.expire = AsyncMock()
            mock_redis_instance.exists = AsyncMock(return_value=False)
            mock_redis_instance.setex = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Mock Celery task
            mock_task.delay = MagicMock()

            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "Valid User",
                    "email": "valid@example.com",
                    "message": "Valid message",
                    "website": "",
                    "timestamp": timestamp,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Verify task was called
        mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_timestamp_silent_reject(self, client: AsyncClient):
        """Submit without timestamp returns 200 silent reject."""
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "No Timestamp User",
                "email": "notimestamp@example.com",
                "message": "Message without timestamp",
                "website": "",
                "timestamp": None,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestContactFormRateLimiting:
    """Tests for Redis-backed rate limiting (Layer 3)."""

    @pytest.mark.asyncio
    async def test_rate_limit_per_email_exceeded(self, client: AsyncClient):
        """4th submission from same email within 1 hour returns 429."""
        current_time = time.time() - 10

        with patch("app.api.v1.contact.get_redis_client") as mock_redis:
            # Mock Redis to simulate 4th request from same email
            mock_redis_instance = MagicMock()
            # First call for email key returns 4 (exceeds limit of 3)
            mock_redis_instance.incr = AsyncMock(return_value=4)
            mock_redis_instance.expire = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "Rate Limited User",
                    "email": "ratelimited@example.com",
                    "message": "Fourth message",
                    "website": "",
                    "timestamp": current_time,
                },
            )

        assert response.status_code == 429
        data = response.json()
        assert "Too many submissions" in data["detail"]

    @pytest.mark.asyncio
    async def test_rate_limit_per_ip_exceeded(self, client: AsyncClient):
        """6th submission from same IP within 1 hour returns 429."""
        current_time = time.time() - 10

        with patch("app.api.v1.contact.get_redis_client") as mock_redis:
            # Mock Redis to simulate 6th request from same IP
            mock_redis_instance = MagicMock()

            # Mock incr to return different values for email vs IP checks
            call_count = [0]
            async def mock_incr(key):
                call_count[0] += 1
                if "email" in key:
                    return 1  # Email check passes
                elif "ip" in key:
                    return 6  # IP check fails (exceeds limit of 5)
                return 1

            mock_redis_instance.incr = mock_incr
            mock_redis_instance.expire = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "Different User",
                    "email": "different@example.com",
                    "message": "Sixth message from this IP",
                    "website": "",
                    "timestamp": current_time,
                },
            )

        assert response.status_code == 429
        data = response.json()
        assert "Too many submissions" in data["detail"]

    @pytest.mark.asyncio
    async def test_rate_limit_redis_unavailable_passes(self, client: AsyncClient):
        """When Redis is unavailable, fail open and allow request."""
        current_time = time.time() - 10

        with patch("app.api.v1.contact.get_redis_client") as mock_redis, \
             patch("app.api.v1.contact.send_contact_emails_task") as mock_task:
            # Mock Redis as unavailable
            mock_redis.return_value = None

            # Mock Celery task
            mock_task.delay = MagicMock()

            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "User",
                    "email": "user@example.com",
                    "message": "Message when Redis is down",
                    "website": "",
                    "timestamp": current_time,
                },
            )

        # Should pass (fail-open policy)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_task.delay.assert_called_once()


class TestContactFormRecaptcha:
    """Tests for reCAPTCHA verification (Layer 4)."""

    @pytest.mark.asyncio
    async def test_recaptcha_disabled_skips_verification(self, client: AsyncClient):
        """When reCAPTCHA secret is not configured, verification is skipped."""
        current_time = time.time() - 10

        with patch("app.api.v1.contact.settings") as mock_settings, \
             patch("app.api.v1.contact.get_redis_client") as mock_redis, \
             patch("app.api.v1.contact.send_contact_emails_task") as mock_task:
            # Mock settings with no reCAPTCHA secret
            mock_settings.recaptcha_secret_key = None
            mock_settings.contact_min_submit_time = 3
            mock_settings.contact_rate_limit_per_email = 3
            mock_settings.contact_rate_limit_per_ip = 5
            mock_settings.contact_rate_limit_global = 50

            # Mock Redis
            mock_redis_instance = MagicMock()
            mock_redis_instance.incr = AsyncMock(return_value=1)
            mock_redis_instance.expire = AsyncMock()
            mock_redis_instance.exists = AsyncMock(return_value=False)
            mock_redis_instance.setex = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Mock Celery task
            mock_task.delay = MagicMock()

            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "User",
                    "email": "user@example.com",
                    "message": "Message without reCAPTCHA",
                    "website": "",
                    "timestamp": current_time,
                    # No recaptcha_token
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_recaptcha_enabled_invalid_token_fails(self, client: AsyncClient):
        """When reCAPTCHA is enabled and token is invalid, return 400."""
        current_time = time.time() - 10

        with patch("app.api.v1.contact.settings") as mock_settings, \
             patch("app.api.v1.contact.get_redis_client") as mock_redis, \
             patch("app.api.v1.contact._verify_recaptcha") as mock_verify:
            # Mock settings with reCAPTCHA enabled
            mock_settings.recaptcha_secret_key = "test-secret-key"
            mock_settings.contact_min_submit_time = 3
            mock_settings.contact_rate_limit_per_email = 3
            mock_settings.contact_rate_limit_per_ip = 5
            mock_settings.contact_rate_limit_global = 50

            # Mock Redis
            mock_redis_instance = MagicMock()
            mock_redis_instance.incr = AsyncMock(return_value=1)
            mock_redis_instance.expire = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Mock reCAPTCHA verification to fail
            mock_verify.return_value = False

            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "User",
                    "email": "user@example.com",
                    "message": "Message with bad reCAPTCHA",
                    "website": "",
                    "timestamp": current_time,
                    "recaptcha_token": "invalid-token",
                },
            )

        assert response.status_code == 400
        data = response.json()
        assert "Verification failed" in data["detail"]


class TestContactFormContentValidation:
    """Tests for content validation (Layer 5)."""

    @pytest.mark.asyncio
    async def test_excessive_urls_silent_reject(self, client: AsyncClient):
        """Message with 4+ URLs returns 200 silent reject."""
        current_time = time.time() - 10

        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "Spammer",
                "email": "spammer@example.com",
                "message": (
                    "Check out https://spam1.com and https://spam2.com "
                    "and also https://spam3.com and https://spam4.com"
                ),
                "website": "",
                "timestamp": current_time,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Thank you, we'll be in touch."

    @pytest.mark.asyncio
    async def test_script_tag_silent_reject(self, client: AsyncClient):
        """Message with <script> tag returns 200 silent reject."""
        current_time = time.time() - 10

        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "Hacker",
                "email": "hacker@example.com",
                "message": "Hello <script>alert('XSS')</script> world",
                "website": "",
                "timestamp": current_time,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Thank you, we'll be in touch."

    @pytest.mark.asyncio
    async def test_duplicate_message_silent_reject(self, client: AsyncClient):
        """Same email+message hash within 24h returns 200 silent reject."""
        current_time = time.time() - 10

        with patch("app.api.v1.contact.get_redis_client") as mock_redis:
            # Mock Redis to simulate duplicate message
            mock_redis_instance = MagicMock()
            mock_redis_instance.incr = AsyncMock(return_value=1)
            mock_redis_instance.expire = AsyncMock()
            # exists() returns True for duplicate check
            mock_redis_instance.exists = AsyncMock(return_value=True)
            mock_redis.return_value = mock_redis_instance

            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "User",
                    "email": "duplicate@example.com",
                    "message": "This exact message was already sent",
                    "website": "",
                    "timestamp": current_time,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_three_urls_allowed(self, client: AsyncClient):
        """Message with exactly 3 URLs is allowed."""
        current_time = time.time() - 10

        with patch("app.api.v1.contact.get_redis_client") as mock_redis, \
             patch("app.api.v1.contact.send_contact_emails_task") as mock_task:
            # Mock Redis
            mock_redis_instance = MagicMock()
            mock_redis_instance.incr = AsyncMock(return_value=1)
            mock_redis_instance.expire = AsyncMock()
            mock_redis_instance.exists = AsyncMock(return_value=False)
            mock_redis_instance.setex = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Mock Celery task
            mock_task.delay = MagicMock()

            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "User",
                    "email": "user@example.com",
                    "message": (
                        "Check https://example1.com and https://example2.com "
                        "and also https://example3.com"
                    ),
                    "website": "",
                    "timestamp": current_time,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Verify task was called (not a silent reject)
        mock_task.delay.assert_called_once()


class TestContactFormValidation:
    """Tests for client-side validation (Pydantic schema)."""

    @pytest.mark.asyncio
    async def test_missing_name_returns_422(self, client: AsyncClient):
        """Missing name field returns 422."""
        response = await client.post(
            "/api/v1/contact",
            json={
                # name missing
                "email": "user@example.com",
                "message": "Message",
                "website": "",
                "timestamp": time.time() - 10,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_name_returns_422(self, client: AsyncClient):
        """Empty name field returns 422."""
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "",  # Empty
                "email": "user@example.com",
                "message": "Message",
                "website": "",
                "timestamp": time.time() - 10,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_email_returns_422(self, client: AsyncClient):
        """Missing email field returns 422."""
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "User",
                # email missing
                "message": "Message",
                "website": "",
                "timestamp": time.time() - 10,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_email_returns_422(self, client: AsyncClient):
        """Invalid email format returns 422."""
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "User",
                "email": "not-an-email",  # Invalid
                "message": "Message",
                "website": "",
                "timestamp": time.time() - 10,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_message_returns_422(self, client: AsyncClient):
        """Missing message field returns 422."""
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "User",
                "email": "user@example.com",
                # message missing
                "website": "",
                "timestamp": time.time() - 10,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_message_returns_422(self, client: AsyncClient):
        """Empty message field returns 422."""
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "User",
                "email": "user@example.com",
                "message": "",  # Empty
                "website": "",
                "timestamp": time.time() - 10,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_message_too_long_returns_422(self, client: AsyncClient):
        """Message exceeding 2000 chars returns 422."""
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "User",
                "email": "user@example.com",
                "message": "x" * 2001,  # Exceeds max_length
                "website": "",
                "timestamp": time.time() - 10,
            },
        )

        assert response.status_code == 422


class TestContactFormSuccess:
    """Tests for successful contact form submission."""

    @pytest.mark.asyncio
    async def test_successful_submission_dispatches_task(self, client: AsyncClient):
        """Valid form data returns 200 and dispatches Celery task."""
        current_time = time.time() - 10

        with patch("app.api.v1.contact.get_redis_client") as mock_redis, \
             patch("app.api.v1.contact.send_contact_emails_task") as mock_task:
            # Mock Redis
            mock_redis_instance = MagicMock()
            mock_redis_instance.incr = AsyncMock(return_value=1)
            mock_redis_instance.expire = AsyncMock()
            mock_redis_instance.exists = AsyncMock(return_value=False)
            mock_redis_instance.setex = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Mock Celery task
            mock_task.delay = MagicMock()

            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "Valid User",
                    "email": "valid@example.com",
                    "message": "This is a legitimate contact form submission.",
                    "website": "",
                    "timestamp": current_time,
                },
            )

        # Assert response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Thank you, we'll be in touch."

        # Assert task was dispatched
        mock_task.delay.assert_called_once_with(
            name="Valid User",
            email="valid@example.com",
            message="This is a legitimate contact form submission.",
        )

    @pytest.mark.asyncio
    async def test_client_ip_extraction_from_forwarded_for(self, client: AsyncClient):
        """Client IP is correctly extracted from X-Forwarded-For header."""
        current_time = time.time() - 10

        with patch("app.api.v1.contact.get_redis_client") as mock_redis, \
             patch("app.api.v1.contact.send_contact_emails_task") as mock_task:
            # Mock Redis
            mock_redis_instance = MagicMock()

            # Track which IP was used in rate limit check
            checked_ip = None
            async def mock_incr(key):
                nonlocal checked_ip
                if "ip:" in key:
                    checked_ip = key.split("ip:")[1]
                return 1

            mock_redis_instance.incr = mock_incr
            mock_redis_instance.expire = AsyncMock()
            mock_redis_instance.exists = AsyncMock(return_value=False)
            mock_redis_instance.setex = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Mock Celery task
            mock_task.delay = MagicMock()

            # Send request with X-Forwarded-For header
            response = await client.post(
                "/api/v1/contact",
                json={
                    "name": "User",
                    "email": "user@example.com",
                    "message": "Test message",
                    "website": "",
                    "timestamp": current_time,
                },
                headers={
                    "X-Forwarded-For": "203.0.113.42, 198.51.100.17",
                },
            )

        assert response.status_code == 200
        # Verify that the first IP from X-Forwarded-For was used
        assert checked_ip == "203.0.113.42"
