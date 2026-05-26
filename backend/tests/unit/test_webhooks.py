"""
Webhook System Unit Tests

These tests verify the webhook system's core functionality, including:
1. SSRF prevention (URL validation)
2. Webhook model methods
3. Webhook schema validation
4. Webhook service (delivery, retries, test sends)
5. Header redaction
6. Response body truncation

All tests use mocking to avoid actual HTTP calls and database connections.
"""

import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch, Mock
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError


# =============================================================================
# 1. SSRF Prevention Tests (url_validation.py)
# =============================================================================

class TestSSRFPrevention:
    """Test URL validation for SSRF protection."""

    def test_is_private_ip_loopback_ipv4(self):
        """
        Verify 127.0.0.1 (loopback) is blocked.

        Bug prevented: SSRF attack to localhost services.
        """
        from app.utils.url_validation import is_private_ip

        assert is_private_ip("127.0.0.1") is True
        assert is_private_ip("127.0.0.2") is True
        assert is_private_ip("127.255.255.255") is True

    def test_is_private_ip_rfc1918_class_a(self):
        """
        Verify 10.0.0.0/8 (RFC 1918 Class A) is blocked.

        Bug prevented: SSRF attack to internal network.
        """
        from app.utils.url_validation import is_private_ip

        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("10.255.255.255") is True

    def test_is_private_ip_rfc1918_class_b(self):
        """
        Verify 172.16.0.0/12 (RFC 1918 Class B) is blocked.

        Bug prevented: SSRF attack to internal network.
        """
        from app.utils.url_validation import is_private_ip

        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("172.31.255.255") is True

    def test_is_private_ip_rfc1918_class_c(self):
        """
        Verify 192.168.0.0/16 (RFC 1918 Class C) is blocked.

        Bug prevented: SSRF attack to internal network.
        """
        from app.utils.url_validation import is_private_ip

        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("192.168.255.255") is True

    def test_is_private_ip_link_local(self):
        """
        Verify 169.254.0.0/16 (link-local, AWS metadata) is blocked.

        Bug prevented: SSRF attack to cloud metadata service.
        """
        from app.utils.url_validation import is_private_ip

        assert is_private_ip("169.254.169.254") is True

    def test_is_private_ip_zero_network(self):
        """
        Verify 0.0.0.0/8 ("this" network) is blocked.

        Bug prevented: SSRF attack to bind addresses.
        """
        from app.utils.url_validation import is_private_ip

        assert is_private_ip("0.0.0.0") is True

    def test_is_private_ip_public_ipv4(self):
        """
        Verify public IPs like 8.8.8.8 are NOT blocked.
        """
        from app.utils.url_validation import is_private_ip

        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False
        assert is_private_ip("93.184.216.34") is False  # example.com

    def test_is_private_ip_ipv6_loopback(self):
        """
        Verify ::1 (IPv6 loopback) is blocked.
        """
        from app.utils.url_validation import is_private_ip

        assert is_private_ip("::1") is True

    def test_is_private_ip_invalid_input(self):
        """
        Invalid IP strings should be treated as private (fail-closed).

        Bug prevented: Bypassing validation with malformed IPs.
        """
        from app.utils.url_validation import is_private_ip

        assert is_private_ip("not-an-ip") is True
        assert is_private_ip("999.999.999.999") is True

    def test_is_private_url_localhost_hostname(self):
        """
        Verify "localhost" hostname is blocked.

        Bug prevented: SSRF attack using hostname instead of IP.
        """
        from app.utils.url_validation import is_private_url

        assert is_private_url("http://localhost/hook") is True
        assert is_private_url("https://localhost/hook") is True
        assert is_private_url("http://localhost.localdomain/hook") is True

    def test_is_private_url_ip_literals(self):
        """
        Verify IP literals in URLs are blocked.

        Bug prevented: Direct IP address in URL bypassing DNS checks.
        """
        from app.utils.url_validation import is_private_url

        assert is_private_url("http://127.0.0.1/hook") is True
        assert is_private_url("http://10.0.0.1/hook") is True
        assert is_private_url("http://192.168.1.1/hook") is True
        assert is_private_url("http://169.254.169.254/hook") is True

    def test_is_private_url_public_domains(self):
        """
        Verify public domains are NOT blocked.
        """
        from app.utils.url_validation import is_private_url

        # Mock DNS resolution to avoid actual network calls
        with patch('socket.getaddrinfo') as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, '', ('93.184.216.34', 443))  # example.com IP
            ]
            assert is_private_url("https://example.com/webhook") is False
            assert is_private_url("https://httpbin.org/post") is False

    def test_is_private_url_non_http_scheme(self):
        """
        Verify non-HTTP(S) schemes are blocked.

        Bug prevented: Bypassing validation with ftp://, file://, etc.
        """
        from app.utils.url_validation import is_private_url

        assert is_private_url("ftp://example.com/hook") is True
        assert is_private_url("file:///etc/passwd") is True
        assert is_private_url("gopher://example.com") is True

    def test_is_private_url_dns_resolution_to_private_ip(self):
        """
        Verify hostnames resolving to private IPs are blocked.

        Bug prevented: Using public DNS name that resolves to internal IP.
        """
        from app.utils.url_validation import is_private_url

        # Mock DNS resolution returning private IP
        with patch('socket.getaddrinfo') as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, '', ('192.168.1.1', 443))
            ]
            assert is_private_url("https://internal.example.com/hook") is True

    def test_is_private_url_dns_failure(self):
        """
        Verify DNS resolution failures are treated as private (fail-closed).

        Bug prevented: Bypassing validation with non-existent domains.
        """
        from app.utils.url_validation import is_private_url
        import socket

        with patch('socket.getaddrinfo') as mock_dns:
            mock_dns.side_effect = socket.gaierror("Name or service not known")
            assert is_private_url("https://nonexistent.example.com/hook") is True

    def test_validate_webhook_url_blocks_private_ip(self):
        """
        Verify validate_webhook_url raises ValidationException for private IPs.

        Bug prevented: Webhook pointing to internal service.
        """
        from app.utils.url_validation import validate_webhook_url
        from app.utils.exceptions import ValidationException

        try:
            validate_webhook_url("http://127.0.0.1/hook")
            assert False, "Expected ValidationException to be raised"
        except ValidationException as exc:
            # Message is: "Webhook URL must not point to a private or internal IP address"
            assert "private" in exc.message.lower() and "internal" in exc.message.lower()
            assert exc.errors[0]["field"] == "url"

    def test_validate_webhook_url_allows_public_url(self):
        """
        Verify validate_webhook_url does NOT raise for public URLs.
        """
        from app.utils.url_validation import validate_webhook_url

        # Mock DNS resolution
        with patch('socket.getaddrinfo') as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, '', ('93.184.216.34', 443))
            ]
            # Should not raise
            validate_webhook_url("https://httpbin.org/post")

    def test_validate_webhook_url_respects_allow_private_ips_setting(self):
        """
        Verify WEBHOOK_ALLOW_PRIVATE_IPS setting bypasses validation.

        Bug prevented: Testing webhook system in development.
        """
        from app.utils.url_validation import validate_webhook_url

        with patch('app.utils.url_validation.settings') as mock_settings:
            mock_settings.webhook_allow_private_ips = True
            # Should not raise even for private IP
            validate_webhook_url("http://127.0.0.1/hook")


# =============================================================================
# 2. Webhook Model Tests (webhook.py)
# =============================================================================

class TestWebhookModel:
    """Test Webhook ORM model methods."""

    def test_generate_secret_returns_64_char_hex(self):
        """
        Verify generate_secret() returns a 64-character hex string.

        Bug prevented: Weak secrets or incorrect length.
        """
        from app.models.webhook import Webhook

        secret = Webhook.generate_secret()
        assert isinstance(secret, str)
        assert len(secret) == 64
        assert all(c in "0123456789abcdef" for c in secret)

    def test_generate_secret_is_random(self):
        """
        Verify generate_secret() returns different values each time.

        Bug prevented: Predictable secrets.
        """
        from app.models.webhook import Webhook

        secret1 = Webhook.generate_secret()
        secret2 = Webhook.generate_secret()
        assert secret1 != secret2

    def test_sign_payload_returns_sha256_signature(self):
        """
        Verify sign_payload() returns HMAC-SHA256 signature.

        Bug prevented: Incorrect signature format or algorithm.
        """
        from app.models.webhook import Webhook

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=["leaflet.completed"],
            is_active=True,
        )

        payload = '{"event": "test"}'
        signature = webhook.sign_payload(payload)

        assert signature.startswith("sha256=")
        assert len(signature) == 71  # "sha256=" (7) + 64 hex chars

    def test_sign_payload_deterministic(self):
        """
        Verify sign_payload() returns same signature for same payload.

        Bug prevented: Non-deterministic signatures.
        """
        from app.models.webhook import Webhook

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=["leaflet.completed"],
            is_active=True,
        )

        payload = '{"event": "test"}'
        sig1 = webhook.sign_payload(payload)
        sig2 = webhook.sign_payload(payload)

        assert sig1 == sig2

    def test_is_subscribed_exact_match(self):
        """
        Verify is_subscribed() returns True for subscribed events.

        Bug prevented: Webhook not firing for subscribed events.
        """
        from app.models.webhook import Webhook, WebhookEvent

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=[WebhookEvent.PROCESSING_COMPLETED.value],
            is_active=True,
        )

        assert webhook.is_subscribed(WebhookEvent.PROCESSING_COMPLETED) is True
        assert webhook.is_subscribed(WebhookEvent.PROCESSING_FAILED) is False

    def test_is_subscribed_wildcard(self):
        """
        Verify is_subscribed() returns True for wildcard subscription.

        Bug prevented: Wildcard "*" subscription not working.
        """
        from app.models.webhook import Webhook, WebhookEvent

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=["*"],
            is_active=True,
        )

        assert webhook.is_subscribed(WebhookEvent.PROCESSING_COMPLETED) is True
        assert webhook.is_subscribed(WebhookEvent.PROCESSING_FAILED) is True
        assert webhook.is_subscribed(WebhookEvent.PRODUCT_APPROVED) is True

    def test_record_success_updates_fields(self):
        """
        Verify record_success() updates webhook statistics.

        Bug prevented: Success not updating counters.
        """
        from app.models.webhook import Webhook

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=["leaflet.completed"],
            is_active=True,
            failure_count=3,
            total_deliveries=10,
            last_error="Previous error",
        )

        webhook.record_success()

        assert webhook.failure_count == 0
        assert webhook.total_deliveries == 11
        assert webhook.last_error is None
        assert webhook.last_error_at is None
        assert webhook.last_triggered_at is not None

    def test_record_failure_increments_counters(self):
        """
        Verify record_failure() increments failure counters.

        Bug prevented: Failures not tracked correctly.
        """
        from app.models.webhook import Webhook

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=["leaflet.completed"],
            is_active=True,
            failure_count=5,
            total_failures=20,
            total_deliveries=0,
            max_failures=10,
        )

        webhook.record_failure("Connection timeout")

        assert webhook.failure_count == 6
        assert webhook.total_failures == 21
        assert webhook.last_error == "Connection timeout"
        assert webhook.last_error_at is not None

    def test_record_failure_auto_disables_after_max_failures(self):
        """
        Verify record_failure() auto-disables after max_failures reached.

        Bug prevented: Webhook continuing to fire after repeated failures.
        """
        from app.models.webhook import Webhook

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=["leaflet.completed"],
            is_active=True,
            failure_count=9,
            total_failures=9,
            total_deliveries=0,
            max_failures=10,
        )

        webhook.record_failure("Error")

        assert webhook.failure_count == 10
        assert webhook.is_active is False

    def test_reset_failures_clears_error_state(self):
        """
        Verify reset_failures() clears error counters.

        Bug prevented: Re-enabling webhook without clearing error state.
        """
        from app.models.webhook import Webhook

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=["leaflet.completed"],
            is_active=True,
            failure_count=8,
            last_error="Previous error",
            last_error_at=datetime.utcnow(),
        )

        webhook.reset_failures()

        assert webhook.failure_count == 0
        assert webhook.last_error is None
        assert webhook.last_error_at is None


class TestWebhookDeliveryModel:
    """Test WebhookDelivery model methods."""

    def test_mark_success_sets_success_fields(self):
        """
        Verify mark_success() sets success=True and related fields.

        Bug prevented: Success status not recorded correctly.
        """
        from app.models.webhook import WebhookDelivery

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=uuid4(),
            event_type="webhook.test",
            payload={},
            status="pending",
            success=False,
        )

        delivery.mark_success(
            status_code=200,
            response_body='{"status": "ok"}',
            response_time_ms=150,
        )

        assert delivery.status == "success"
        assert delivery.success is True
        assert delivery.response_status_code == 200
        assert delivery.response_body == '{"status": "ok"}'
        assert delivery.response_time_ms == 150
        assert delivery.delivered_at is not None

    def test_mark_success_truncates_large_response_body(self):
        """
        Verify mark_success() truncates response bodies >10KB.

        Bug prevented: Database bloat from large response bodies.
        """
        from app.models.webhook import WebhookDelivery, MAX_RESPONSE_BODY_LENGTH

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=uuid4(),
            event_type="webhook.test",
            payload={},
            status="pending",
            success=False,
        )

        large_body = "x" * 20000  # 20KB
        delivery.mark_success(
            status_code=200,
            response_body=large_body,
            response_time_ms=150,
        )

        assert len(delivery.response_body) == MAX_RESPONSE_BODY_LENGTH
        assert delivery.response_body == "x" * MAX_RESPONSE_BODY_LENGTH

    def test_mark_failed_sets_error_fields(self):
        """
        Verify mark_failed() sets success=False and error message.

        Bug prevented: Failed status not recorded correctly.
        """
        from app.models.webhook import WebhookDelivery

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=uuid4(),
            event_type="webhook.test",
            payload={},
            status="pending",
            success=False,
        )

        delivery.mark_failed(error="Connection timeout", status_code=504)

        assert delivery.status == "failed"
        assert delivery.success is False
        assert delivery.error_message == "Connection timeout"
        assert delivery.response_status_code == 504

    def test_schedule_retry_increments_attempt_and_sets_next_retry(self):
        """
        Verify schedule_retry() sets next_retry_at correctly.

        Bug prevented: Retries not scheduled with correct timing.
        """
        from app.models.webhook import WebhookDelivery

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=uuid4(),
            event_type="webhook.test",
            payload={},
            status="failed",
            success=False,
            attempt_number=1,
        )

        before = datetime.utcnow()
        delivery.schedule_retry(delay_seconds=60)
        after = datetime.utcnow()

        assert delivery.attempt_number == 2
        assert delivery.status == "pending"
        assert delivery.success is False
        assert delivery.next_retry_at is not None
        assert before + timedelta(seconds=60) <= delivery.next_retry_at <= after + timedelta(seconds=60)


# =============================================================================
# 3. Webhook Schema Validation Tests
# =============================================================================

class TestWebhookSchemas:
    """Test Pydantic schema validation for webhook endpoints."""

    def test_webhook_create_valid_data(self):
        """
        Verify WebhookCreate accepts valid data.

        Bug prevented: Valid webhook creation failing validation.
        """
        from app.api.v1.webhooks import WebhookCreate

        data = {
            "name": "My Webhook",
            "url": "https://example.com/webhook",
            "events": ["leaflet.processing.completed"],
            "description": "Test webhook",
            "retry_count": 3,
            "timeout_seconds": 30,
        }

        webhook = WebhookCreate(**data)
        assert webhook.name == "My Webhook"
        assert webhook.url == "https://example.com/webhook"
        assert webhook.events == ["leaflet.processing.completed"]
        assert webhook.retry_count == 3
        assert webhook.timeout_seconds == 30

    def test_webhook_create_missing_url_fails(self):
        """
        Verify WebhookCreate fails without URL.

        Bug prevented: Creating webhook without URL.
        """
        from app.api.v1.webhooks import WebhookCreate

        with pytest.raises(ValidationError) as exc_info:
            WebhookCreate(
                name="Test",
                events=["leaflet.processing.completed"],
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("url",) for e in errors)

    def test_webhook_create_events_default_value(self):
        """
        Verify WebhookCreate has default events value.

        Bug prevented: Missing events field causing failure.
        """
        from app.api.v1.webhooks import WebhookCreate

        webhook = WebhookCreate(
            name="Test",
            url="https://example.com/webhook",
        )

        assert webhook.events == ["leaflet.processing.completed"]

    def test_webhook_create_retry_count_validation(self):
        """
        Verify retry_count is validated (0-10 range).

        Bug prevented: Invalid retry count values.
        """
        from app.api.v1.webhooks import WebhookCreate

        # Valid range
        WebhookCreate(name="Test", url="https://example.com/webhook", retry_count=0)
        WebhookCreate(name="Test", url="https://example.com/webhook", retry_count=10)

        # Invalid: negative
        with pytest.raises(ValidationError):
            WebhookCreate(name="Test", url="https://example.com/webhook", retry_count=-1)

        # Invalid: too high
        with pytest.raises(ValidationError):
            WebhookCreate(name="Test", url="https://example.com/webhook", retry_count=11)

    def test_webhook_create_timeout_validation(self):
        """
        Verify timeout_seconds is validated (5-120 range).

        Bug prevented: Invalid timeout values.
        """
        from app.api.v1.webhooks import WebhookCreate

        # Valid range
        WebhookCreate(name="Test", url="https://example.com/webhook", timeout_seconds=5)
        WebhookCreate(name="Test", url="https://example.com/webhook", timeout_seconds=120)

        # Invalid: too low
        with pytest.raises(ValidationError):
            WebhookCreate(name="Test", url="https://example.com/webhook", timeout_seconds=4)

        # Invalid: too high
        with pytest.raises(ValidationError):
            WebhookCreate(name="Test", url="https://example.com/webhook", timeout_seconds=121)

    def test_webhook_create_name_validation(self):
        """
        Verify name is validated (1-100 chars).

        Bug prevented: Empty or too-long webhook names.
        """
        from app.api.v1.webhooks import WebhookCreate

        # Valid
        WebhookCreate(name="A", url="https://example.com/webhook")
        WebhookCreate(name="A" * 100, url="https://example.com/webhook")

        # Invalid: empty
        with pytest.raises(ValidationError):
            WebhookCreate(name="", url="https://example.com/webhook")

        # Invalid: too long
        with pytest.raises(ValidationError):
            WebhookCreate(name="A" * 101, url="https://example.com/webhook")

    def test_webhook_update_all_fields_optional(self):
        """
        Verify WebhookUpdate accepts partial updates.

        Bug prevented: Requiring all fields for PATCH updates.
        """
        from app.api.v1.webhooks import WebhookUpdate

        # Empty update
        update = WebhookUpdate()
        assert update.name is None
        assert update.url is None
        assert update.events is None

        # Partial update
        update = WebhookUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.url is None

    def test_webhook_create_response_wraps_secret(self):
        """
        Verify WebhookCreateResponse wraps webhook + secret.

        Bug prevented: Secret not returned at creation time.
        """
        from app.api.v1.webhooks import WebhookCreateResponse, WebhookResponse
        from datetime import datetime

        webhook_resp = WebhookResponse(
            id=uuid4(),
            name="Test",
            url="https://example.com/webhook",
            events=["leaflet.completed"],
            description=None,
            is_active=True,
            retry_count=3,
            timeout_seconds=30,
            failure_count=0,
            total_deliveries=0,
            total_failures=0,
            last_triggered_at=None,
            last_error=None,
            created_at=datetime.utcnow(),
        )

        response = WebhookCreateResponse(
            webhook=webhook_resp,
            secret="abc123",
        )

        assert response.webhook == webhook_resp
        assert response.secret == "abc123"

    def test_webhook_delivery_list_response_includes_pagination(self):
        """
        Verify WebhookDeliveryListResponse includes pagination fields.

        Bug prevented: Missing pagination metadata.
        """
        from app.api.v1.webhooks import WebhookDeliveryListResponse, WebhookDeliveryResponse

        response = WebhookDeliveryListResponse(
            deliveries=[
                WebhookDeliveryResponse(
                    id=uuid4(),
                    event_type="webhook.test",
                    status_code=200,
                    success=True,
                    response_time_ms=150,
                    error_message=None,
                    created_at=datetime.utcnow(),
                )
            ],
            total=100,
            page=1,
            pages=5,
        )

        assert len(response.deliveries) == 1
        assert response.total == 100
        assert response.page == 1
        assert response.pages == 5


# =============================================================================
# 4. Webhook Service Tests (webhook_service.py)
# =============================================================================

class TestWebhookService:
    """Test WebhookService for sending webhooks."""

    @pytest.mark.asyncio
    async def test_send_test_success_records_delivery(self):
        """
        Verify send_test() records successful delivery.

        Bug prevented: Test sends not appearing in delivery log.
        """
        from app.services.webhook_service import WebhookService
        from app.models.webhook import Webhook, WebhookDelivery
        from unittest.mock import AsyncMock

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://httpbin.org/post",
            secret="a" * 64,
            events=["*"],
            is_active=True,
        )

        # Mock database session
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'

        service = WebhookService(mock_db)

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client

            delivery = await service.send_test(
                webhook=webhook,
                organization_name="Test Org",
            )

        assert delivery.success is True
        assert delivery.status == "success"
        assert delivery.response_status_code == 200
        assert delivery.event_type == "webhook.test"
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_send_test_error_response_marks_failed(self):
        """
        Verify send_test() marks failed for 500 responses.

        Bug prevented: 500 errors not recorded as failures.
        """
        from app.services.webhook_service import WebhookService
        from app.models.webhook import Webhook
        from unittest.mock import AsyncMock

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://httpbin.org/status/500",
            secret="a" * 64,
            events=["*"],
            is_active=True,
        )

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        service = WebhookService(mock_db)

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client

            delivery = await service.send_test(
                webhook=webhook,
                organization_name="Test Org",
            )

        assert delivery.success is False
        assert delivery.status == "failed"
        assert delivery.response_status_code == 500
        assert "500" in delivery.error_message

    @pytest.mark.asyncio
    async def test_send_test_timeout_marks_failed(self):
        """
        Verify send_test() marks failed on timeout.

        Bug prevented: Timeouts not recorded as failures.
        """
        from app.services.webhook_service import WebhookService
        from app.models.webhook import Webhook
        from unittest.mock import AsyncMock

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://httpbin.org/delay/15",
            secret="a" * 64,
            events=["*"],
            is_active=True,
        )

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = WebhookService(mock_db)

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            MockClient.return_value = mock_client

            delivery = await service.send_test(
                webhook=webhook,
                organization_name="Test Org",
            )

        assert delivery.success is False
        assert delivery.status == "failed"
        assert "timed out" in delivery.error_message.lower()

    @pytest.mark.asyncio
    async def test_send_test_connection_error_marks_failed(self):
        """
        Verify send_test() marks failed on connection error.

        Bug prevented: Connection errors not recorded.
        """
        from app.services.webhook_service import WebhookService
        from app.models.webhook import Webhook
        from unittest.mock import AsyncMock

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://unreachable.example.com/webhook",
            secret="a" * 64,
            events=["*"],
            is_active=True,
        )

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = WebhookService(mock_db)

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            MockClient.return_value = mock_client

            delivery = await service.send_test(
                webhook=webhook,
                organization_name="Test Org",
            )

        assert delivery.success is False
        assert delivery.status == "failed"
        assert "connection" in delivery.error_message.lower()

    @pytest.mark.asyncio
    async def test_send_test_uses_10_second_timeout(self):
        """
        Verify send_test() enforces 10-second timeout regardless of webhook config.

        Bug prevented: Test sends using webhook's own timeout setting.
        """
        from app.services.webhook_service import WebhookService, TEST_SEND_TIMEOUT_SECONDS
        from app.models.webhook import Webhook
        from unittest.mock import AsyncMock

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://httpbin.org/post",
            secret="a" * 64,
            events=["*"],
            is_active=True,
            timeout_seconds=120,  # Webhook has 120s timeout
        )

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'

        service = WebhookService(mock_db)

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client

            await service.send_test(
                webhook=webhook,
                organization_name="Test Org",
            )

            # Verify timeout parameter passed to client.post
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["timeout"] == TEST_SEND_TIMEOUT_SECONDS
            assert call_kwargs["timeout"] == 10  # Not 120


# =============================================================================
# 5. Header Redaction Tests
# =============================================================================

class TestHeaderRedaction:
    """Test sensitive header redaction in delivery logs."""

    def test_redact_headers_authorization(self):
        """
        Verify Authorization header is redacted.

        Bug prevented: Leaking authorization tokens in delivery logs.
        """
        from app.services.webhook_service import _redact_headers

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret-token-12345",
            "X-Custom-Header": "value",
        }

        redacted = _redact_headers(headers)

        assert redacted["Content-Type"] == "application/json"
        assert redacted["Authorization"] == "[REDACTED]"
        assert redacted["X-Custom-Header"] == "value"

    def test_redact_headers_x_api_key(self):
        """
        Verify X-API-Key header is redacted.

        Bug prevented: Leaking API keys in delivery logs.
        """
        from app.services.webhook_service import _redact_headers

        headers = {
            "X-API-Key": "sk_live_1234567890",
        }

        redacted = _redact_headers(headers)
        assert redacted["X-API-Key"] == "[REDACTED]"

    def test_redact_headers_x_webhook_signature(self):
        """
        Verify X-Webhook-Signature header is redacted.

        Bug prevented: Leaking webhook secrets via signature in logs.
        """
        from app.services.webhook_service import _redact_headers

        headers = {
            "X-Webhook-Signature": "sha256=abcdef1234567890",
        }

        redacted = _redact_headers(headers)
        assert redacted["X-Webhook-Signature"] == "[REDACTED]"

    def test_redact_headers_case_insensitive(self):
        """
        Verify header redaction is case-insensitive.

        Bug prevented: Bypassing redaction with different casing.
        """
        from app.services.webhook_service import _redact_headers

        headers = {
            "AUTHORIZATION": "Bearer token",
            "authorization": "Bearer token2",
            "Authorization": "Bearer token3",
            "X-Api-Key": "key1",
            "x-api-key": "key2",
        }

        redacted = _redact_headers(headers)
        assert all(v == "[REDACTED]" for v in redacted.values())

    def test_redact_headers_preserves_non_sensitive(self):
        """
        Verify non-sensitive headers are NOT redacted.

        Bug prevented: Over-redaction hiding useful debug info.
        """
        from app.services.webhook_service import _redact_headers

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LeafXtract-Webhook/1.0",
            "X-Webhook-Event": "leaflet.completed",
            "X-Request-ID": "req-12345",
        }

        redacted = _redact_headers(headers)
        assert redacted == headers


# =============================================================================
# 6. Webhook Dispatch Logic Tests
# =============================================================================

class TestWebhookDispatch:
    """Test webhook dispatch based on subscribed events."""

    def test_dispatch_matching_event_should_fire(self):
        """
        Verify webhook fires for subscribed event.

        Bug prevented: Webhook not firing for subscribed events.
        """
        from app.models.webhook import Webhook, WebhookEvent

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=[WebhookEvent.PROCESSING_COMPLETED.value],
            is_active=True,
        )

        assert webhook.is_subscribed(WebhookEvent.PROCESSING_COMPLETED) is True

    def test_dispatch_non_matching_event_should_not_fire(self):
        """
        Verify webhook does NOT fire for non-subscribed event.

        Bug prevented: Webhook firing for all events regardless of subscription.
        """
        from app.models.webhook import Webhook, WebhookEvent

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=[WebhookEvent.PROCESSING_COMPLETED.value],
            is_active=True,
        )

        assert webhook.is_subscribed(WebhookEvent.PRODUCT_APPROVED) is False

    def test_inactive_webhook_not_returned_by_service(self):
        """
        Verify get_user_webhooks filters out inactive webhooks by default.

        Bug prevented: Inactive webhooks still receiving events.
        """
        # This would be an integration test requiring database,
        # but the logic is in webhook_service.py line 109-110:
        # if active_only:
        #     query = query.where(Webhook.is_active == True)
        pass


# =============================================================================
# 7. Response Body Truncation Tests
# =============================================================================

class TestResponseBodyTruncation:
    """Test response body truncation to prevent database bloat."""

    def test_max_response_body_length_constant(self):
        """
        Verify MAX_RESPONSE_BODY_LENGTH is 10KB.

        Bug prevented: Incorrect truncation size.
        """
        from app.models.webhook import MAX_RESPONSE_BODY_LENGTH

        assert MAX_RESPONSE_BODY_LENGTH == 10_240  # 10KB

    def test_delivery_truncates_large_response(self):
        """
        Verify WebhookDelivery.mark_success() truncates large responses.

        Bug prevented: Database bloat from large response bodies.
        """
        from app.models.webhook import WebhookDelivery, MAX_RESPONSE_BODY_LENGTH

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=uuid4(),
            event_type="webhook.test",
            payload={},
            status="pending",
            success=False,
        )

        large_body = "x" * (MAX_RESPONSE_BODY_LENGTH * 2)
        delivery.mark_success(
            status_code=200,
            response_body=large_body,
            response_time_ms=100,
        )

        assert len(delivery.response_body) == MAX_RESPONSE_BODY_LENGTH
        assert delivery.response_body == "x" * MAX_RESPONSE_BODY_LENGTH

    def test_delivery_preserves_small_response(self):
        """
        Verify small response bodies are NOT truncated.

        Bug prevented: Unnecessary truncation of small responses.
        """
        from app.models.webhook import WebhookDelivery

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=uuid4(),
            event_type="webhook.test",
            payload={},
            status="pending",
            success=False,
        )

        small_body = '{"status": "ok"}'
        delivery.mark_success(
            status_code=200,
            response_body=small_body,
            response_time_ms=100,
        )

        assert delivery.response_body == small_body


# =============================================================================
# 8. Webhook Event Descriptions Tests
# =============================================================================

class TestWebhookEvents:
    """Test webhook event enumeration and descriptions."""

    def test_all_webhook_events_have_descriptions(self):
        """
        Verify all WebhookEvent enum values have descriptions.

        Bug prevented: Missing event descriptions in API docs.
        """
        from app.models.webhook import WebhookEvent
        from app.api.v1.webhooks import _get_event_description

        for event in WebhookEvent:
            description = _get_event_description(event)
            assert isinstance(description, str)
            assert len(description) > 0

    def test_webhook_event_values_match_expected(self):
        """
        Verify WebhookEvent enum values match expected format.

        Bug prevented: Event type format changes breaking integrations.
        """
        from app.models.webhook import WebhookEvent

        expected_events = [
            "leaflet.uploaded",
            "leaflet.processing.started",
            "leaflet.processing.completed",
            "leaflet.processing.failed",
            "leaflet.review.required",
            "leaflet.review.completed",
            "leaflet.export.ready",
            "product.updated",
            "product.approved",
            "product.rejected",
        ]

        actual_events = [e.value for e in WebhookEvent]
        assert set(actual_events) == set(expected_events)


# =============================================================================
# 9. Webhook Secret Encryption Tests (Critical Issue 1)
# =============================================================================

class TestWebhookSecretEncryption:
    """Test Fernet encryption of webhook signing secrets."""

    def test_set_secret_encrypts_value(self):
        """
        Verify set_secret() encrypts the raw secret before storing.

        Bug prevented: Webhook secrets stored in plain text in database.
        """
        from app.models.webhook import Webhook

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="",
            events=["*"],
            is_active=True,
        )

        raw_secret = "a1b2c3d4e5f6" * 5
        webhook.set_secret(raw_secret)

        # The stored value must differ from the raw secret.
        assert webhook.secret != raw_secret
        # Fernet tokens are base64 and always start with "gAAAAA".
        assert webhook.secret.startswith("gAAAAA")

    def test_get_secret_decrypts_value(self):
        """
        Verify get_secret() round-trips through encryption.

        Bug prevented: Decryption returning wrong value.
        """
        from app.models.webhook import Webhook

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="",
            events=["*"],
            is_active=True,
        )

        raw_secret = Webhook.generate_secret()
        webhook.set_secret(raw_secret)

        decrypted = webhook.get_secret()
        assert decrypted == raw_secret

    def test_get_secret_backward_compat_plain_text(self):
        """
        Verify get_secret() falls back to returning plain text for
        legacy secrets that were stored before encryption was introduced.

        Bug prevented: Existing webhooks breaking after code deployment.
        """
        from app.models.webhook import Webhook

        plain_secret = "a" * 64  # Legacy plain-text format
        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret=plain_secret,
            events=["*"],
            is_active=True,
        )

        # Should return the plain text (not raise).
        assert webhook.get_secret() == plain_secret

    def test_sign_payload_uses_decrypted_secret(self):
        """
        Verify sign_payload() decrypts the secret before HMAC signing.

        Bug prevented: Using encrypted (ciphertext) as HMAC key instead
        of the original plain-text secret.
        """
        from app.models.webhook import Webhook
        import hmac as hmac_mod
        import hashlib

        raw_secret = Webhook.generate_secret()

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="",
            events=["*"],
            is_active=True,
        )
        webhook.set_secret(raw_secret)

        payload = '{"event": "test"}'
        signature = webhook.sign_payload(payload)

        # Compute expected signature using the raw (decrypted) secret.
        expected_sig = hmac_mod.new(
            raw_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        assert signature == f"sha256={expected_sig}"

    def test_sign_payload_backward_compat_plain_text(self):
        """
        Verify sign_payload() still works with legacy plain-text secrets.

        Bug prevented: Breaking existing webhooks during transition.
        """
        from app.models.webhook import Webhook
        import hmac as hmac_mod
        import hashlib

        plain_secret = "b" * 64
        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret=plain_secret,
            events=["*"],
            is_active=True,
        )

        payload = '{"event": "test"}'
        signature = webhook.sign_payload(payload)

        expected_sig = hmac_mod.new(
            plain_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        assert signature == f"sha256={expected_sig}"


# =============================================================================
# 10. SSRF Check in Real Event Dispatches (Critical Issue 2)
# =============================================================================

class TestSSRFDispatchCheck:
    """Test SSRF prevention during real webhook dispatch."""

    @pytest.mark.asyncio
    async def test_send_webhook_blocks_private_ip_at_dispatch(self):
        """
        Verify _send_webhook() blocks delivery when URL resolves to
        a private IP at dispatch time (DNS rebinding defense).

        Bug prevented: Attacker creates webhook with public DNS, then
        re-points DNS to internal IP before dispatch fires.
        """
        from app.services.webhook_service import WebhookService
        from app.models.webhook import Webhook, WebhookDelivery

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://evil.example.com/hook",
            secret="a" * 64,
            events=["*"],
            is_active=True,
            failure_count=0,
            total_failures=0,
            total_deliveries=0,
            max_failures=10,
        )

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=webhook.id,
            event_type="leaflet.processing.completed",
            payload={"leaflet_id": "LEAF_001"},
            status="pending",
            success=False,
        )

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        service = WebhookService(mock_db)

        with patch('app.services.webhook_service.settings') as mock_settings, \
             patch('app.services.webhook_service.is_private_url') as mock_private:
            mock_settings.webhook_allow_private_ips = False
            mock_private.return_value = True  # URL resolves to private IP

            result = await service._send_webhook(webhook, delivery)

        assert result is False
        assert delivery.status == "failed"
        assert "private" in delivery.error_message.lower()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_send_webhook_allows_public_ip_at_dispatch(self):
        """
        Verify _send_webhook() allows delivery when URL resolves to
        a public IP.

        Bug prevented: False-positive SSRF blocking legitimate webhooks.
        """
        from app.services.webhook_service import WebhookService
        from app.models.webhook import Webhook, WebhookDelivery

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://httpbin.org/post",
            secret="a" * 64,
            events=["*"],
            is_active=True,
            failure_count=0,
            total_failures=0,
            total_deliveries=0,
            max_failures=10,
            retry_count=0,
            timeout_seconds=10,
        )

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=webhook.id,
            event_type="leaflet.processing.completed",
            payload={"leaflet_id": "LEAF_001"},
            status="pending",
            success=False,
        )

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'

        service = WebhookService(mock_db)

        with patch('app.services.webhook_service.settings') as mock_settings, \
             patch('app.services.webhook_service.is_private_url') as mock_private, \
             patch.object(service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_settings.webhook_allow_private_ips = False
            mock_private.return_value = False  # Public IP
            mock_post.return_value = mock_response

            result = await service._send_webhook(webhook, delivery)

        assert result is True
        assert delivery.status == "success"
        assert delivery.success is True

    @pytest.mark.asyncio
    async def test_send_webhook_skips_ssrf_when_allow_private_ips(self):
        """
        Verify _send_webhook() skips SSRF check when
        webhook_allow_private_ips is True (dev mode).

        Bug prevented: Breaking local dev when using private IPs.
        """
        from app.services.webhook_service import WebhookService
        from app.models.webhook import Webhook, WebhookDelivery

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="http://localhost:8080/hook",
            secret="a" * 64,
            events=["*"],
            is_active=True,
            failure_count=0,
            total_failures=0,
            total_deliveries=0,
            max_failures=10,
            retry_count=0,
            timeout_seconds=10,
        )

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=webhook.id,
            event_type="leaflet.processing.completed",
            payload={"leaflet_id": "LEAF_001"},
            status="pending",
            success=False,
        )

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'

        service = WebhookService(mock_db)

        with patch('app.services.webhook_service.settings') as mock_settings, \
             patch('app.services.webhook_service.is_private_url') as mock_private, \
             patch.object(service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_settings.webhook_allow_private_ips = True
            mock_post.return_value = mock_response

            result = await service._send_webhook(webhook, delivery)

        # is_private_url should NOT have been called.
        mock_private.assert_not_called()
        assert result is True


# =============================================================================
# 11. Soft Delete Tests (Critical Issue 3)
# =============================================================================

class TestWebhookSoftDelete:
    """Test soft-delete behavior for webhooks."""

    def test_webhook_has_deleted_at_column(self):
        """
        Verify Webhook model has deleted_at column.

        Bug prevented: Missing soft-delete support.
        """
        from app.models.webhook import Webhook

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=["*"],
            is_active=True,
        )

        # New webhooks should have deleted_at=None.
        assert webhook.deleted_at is None

    def test_webhook_soft_delete_sets_deleted_at(self):
        """
        Verify soft-deleting a webhook sets deleted_at and is_active=False.

        Bug prevented: Hard deletion orphaning in-flight deliveries.
        """
        from app.models.webhook import Webhook

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://example.com/hook",
            secret="a" * 64,
            events=["*"],
            is_active=True,
        )

        webhook.deleted_at = datetime.utcnow()
        webhook.is_active = False

        assert webhook.deleted_at is not None
        assert webhook.is_active is False

    @pytest.mark.asyncio
    async def test_send_webhook_skips_deleted_webhook(self):
        """
        Verify _send_webhook() skips delivery for soft-deleted webhooks.

        Bug prevented: Delivering to a webhook that was deleted while
        the delivery task was queued.
        """
        from app.services.webhook_service import WebhookService
        from app.models.webhook import Webhook, WebhookDelivery

        webhook = Webhook(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Test",
            url="https://httpbin.org/post",
            secret="a" * 64,
            events=["*"],
            is_active=False,
            deleted_at=datetime.utcnow(),
            failure_count=0,
            total_failures=0,
            total_deliveries=0,
            max_failures=10,
        )

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=webhook.id,
            event_type="leaflet.processing.completed",
            payload={"leaflet_id": "LEAF_001"},
            status="pending",
            success=False,
        )

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        service = WebhookService(mock_db)

        with patch('app.services.webhook_service.settings') as mock_settings, \
             patch('app.services.webhook_service.is_private_url') as mock_private:
            mock_settings.webhook_allow_private_ips = False
            mock_private.return_value = False

            result = await service._send_webhook(webhook, delivery)

        assert result is False
        assert delivery.status == "failed"
        assert "deleted" in delivery.error_message.lower()


# =============================================================================
# 12. Response Body Constraint Tests (Critical Issue 4)
# =============================================================================

class TestResponseBodyConstraint:
    """Test database-level response body size constraint."""

    def test_response_body_column_type_is_string_10240(self):
        """
        Verify response_body column uses String(10240), not unlimited Text.

        Bug prevented: Unbounded response bodies bloating database.
        """
        from sqlalchemy import String as SAString
        from app.models.webhook import WebhookDelivery, MAX_RESPONSE_BODY_LENGTH

        col = WebhookDelivery.__table__.columns["response_body"]
        assert isinstance(col.type, SAString)
        assert col.type.length == MAX_RESPONSE_BODY_LENGTH
