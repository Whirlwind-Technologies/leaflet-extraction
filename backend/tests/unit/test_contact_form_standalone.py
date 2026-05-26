"""
Contact Form Tests - Standalone Version (bypasses pytest fixtures).

Run with: python tests/unit/test_contact_form_standalone.py

Tests all 5 layers of spam protection in the contact form.
"""

import sys
import time
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

# Must set environment before importing app modules
import os
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'

# Import after environment is set
from app.api.v1.contact import (
    _get_client_ip,
    _message_dedup_key,
    _check_rate_limits,
    _verify_recaptcha,
    _is_duplicate_message,
    submit_contact_form,
)
from app.schemas.contact import ContactRequest, ContactResponse
from fastapi import Request
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import hashlib
import asyncio


# Test helpers
class MockRequest:
    """Mock FastAPI Request object."""
    def __init__(self, headers=None, client_host="127.0.0.1"):
        self.headers = headers or {}
        self.client = Mock()
        self.client.host = client_host


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def assert_equal(self, actual, expected, test_name):
        if actual == expected:
            self.passed += 1
            print(f"[PASS] {test_name}")
        else:
            self.failed += 1
            error = f"[FAIL] {test_name}: Expected {expected}, got {actual}"
            self.errors.append(error)
            print(error)

    def assert_true(self, value, test_name):
        self.assert_equal(value, True, test_name)

    def assert_false(self, value, test_name):
        self.assert_equal(value, False, test_name)

    def assert_in(self, substring, string, test_name):
        if substring in str(string):
            self.passed += 1
            print(f"[PASS] {test_name}")
        else:
            self.failed += 1
            error = f"[FAIL] {test_name}: '{substring}' not in '{string}'"
            self.errors.append(error)
            print(error)

    def summary(self):
        print(f"\n{'='*60}")
        print(f"Test Results: {self.passed} passed, {self.failed} failed")
        if self.errors:
            print(f"\nFailures:")
            for error in self.errors:
                print(f"  {error}")
        print(f"{'='*60}")
        return self.failed == 0


results = TestResults()


# ============================================================================
# Test: Client IP Extraction
# ============================================================================

def test_client_ip_extraction():
    """Test _get_client_ip extracts IP from X-Forwarded-For."""
    # Test with X-Forwarded-For header
    request = MockRequest(headers={"X-Forwarded-For": "203.0.113.42, 198.51.100.17"})
    ip = _get_client_ip(request)
    results.assert_equal(ip, "203.0.113.42", "IP extracted from X-Forwarded-For")

    # Test with direct client IP
    request = MockRequest(client_host="192.168.1.100")
    ip = _get_client_ip(request)
    results.assert_equal(ip, "192.168.1.100", "IP extracted from request.client.host")


# ============================================================================
# Test: Message Dedup Key
# ============================================================================

def test_message_dedup_key():
    """Test _message_dedup_key generates consistent hash."""
    email = "test@example.com"
    message = "Hello world"

    key1 = _message_dedup_key(email, message)
    key2 = _message_dedup_key(email, message)

    results.assert_equal(key1, key2, "Dedup keys are consistent")

    # Verify format
    expected_hash = hashlib.sha256(f"{email}{message}".encode()).hexdigest()
    expected_key = f"contact:dedup:{expected_hash}"
    results.assert_equal(key1, expected_key, "Dedup key format correct")

    # Different message -> different key
    key3 = _message_dedup_key(email, "Different message")
    results.assert_true(key1 != key3, "Different messages have different keys")


# ============================================================================
# Test: Rate Limiting
# ============================================================================

async def test_rate_limiting():
    """Test _check_rate_limits with mocked Redis."""
    # Test: Rate limit exceeded
    with patch("app.api.v1.contact.get_redis_client") as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis_instance.incr = AsyncMock(return_value=4)  # Exceeds limit of 3
        mock_redis_instance.expire = AsyncMock()
        mock_redis.return_value = mock_redis_instance

        response = await _check_rate_limits("test@example.com", "127.0.0.1")
        results.assert_true(response is not None, "Rate limit returns response")
        results.assert_equal(response.status_code, 429, "Rate limit status is 429")

    # Test: Rate limit not exceeded
    with patch("app.api.v1.contact.get_redis_client") as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis_instance.incr = AsyncMock(return_value=1)  # Under limit
        mock_redis_instance.expire = AsyncMock()
        mock_redis.return_value = mock_redis_instance

        response = await _check_rate_limits("test@example.com", "127.0.0.1")
        results.assert_true(response is None, "Under rate limit returns None")

    # Test: Redis unavailable (fail-open)
    with patch("app.api.v1.contact.get_redis_client") as mock_redis:
        mock_redis.return_value = None  # Redis unavailable

        response = await _check_rate_limits("test@example.com", "127.0.0.1")
        results.assert_true(response is None, "Redis unavailable fails open")


# ============================================================================
# Test: Duplicate Message Detection
# ============================================================================

async def test_duplicate_detection():
    """Test _is_duplicate_message with mocked Redis."""
    # Test: Message is duplicate
    with patch("app.api.v1.contact.get_redis_client") as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis_instance.exists = AsyncMock(return_value=True)  # Exists
        mock_redis.return_value = mock_redis_instance

        is_dup = await _is_duplicate_message("test@example.com", "Message")
        results.assert_true(is_dup, "Duplicate message detected")

    # Test: Message is not duplicate
    with patch("app.api.v1.contact.get_redis_client") as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis_instance.exists = AsyncMock(return_value=False)  # Does not exist
        mock_redis_instance.setex = AsyncMock()
        mock_redis.return_value = mock_redis_instance

        is_dup = await _is_duplicate_message("test@example.com", "Message")
        results.assert_false(is_dup, "New message not marked as duplicate")

    # Test: Redis unavailable
    with patch("app.api.v1.contact.get_redis_client") as mock_redis:
        mock_redis.return_value = None  # Redis unavailable

        is_dup = await _is_duplicate_message("test@example.com", "Message")
        results.assert_false(is_dup, "Redis unavailable fails open for duplicates")


# ============================================================================
# Test: Honeypot Detection
# ============================================================================

async def test_honeypot_detection():
    """Test honeypot field detection (Layer 1)."""
    current_time = time.time() - 10

    # Test: Honeypot filled (silent reject)
    with patch("app.api.v1.contact.get_redis_client"):
        payload = ContactRequest(
            name="Bot",
            email="bot@example.com",
            message="Spam",
            website="https://spam.com",  # Honeypot filled
            timestamp=current_time,
        )
        request = MockRequest()

        response = await submit_contact_form(payload, request)
        results.assert_equal(response.success, True, "Honeypot filled returns success")
        results.assert_equal(response.message, "Thank you, we'll be in touch.", "Honeypot message correct")


# ============================================================================
# Test: Timing Validation
# ============================================================================

async def test_timing_validation():
    """Test time-based validation (Layer 2)."""
    # Test: Too fast (submitted <3 seconds)
    fast_timestamp = time.time() - 1  # 1 second ago
    with patch("app.api.v1.contact.get_redis_client"):
        payload = ContactRequest(
            name="User",
            email="user@example.com",
            message="Message",
            website="",
            timestamp=fast_timestamp,
        )
        request = MockRequest()

        response = await submit_contact_form(payload, request)
        results.assert_equal(response.success, True, "Too fast returns success (silent reject)")

    # Test: Too old (>2 hours)
    old_timestamp = time.time() - 7300  # 2 hours + 100 seconds ago
    with patch("app.api.v1.contact.get_redis_client"):
        payload = ContactRequest(
            name="User",
            email="user@example.com",
            message="Message",
            website="",
            timestamp=old_timestamp,
        )
        request = MockRequest()

        response = await submit_contact_form(payload, request)
        results.assert_equal(response.success, True, "Too old returns success (silent reject)")

    # Test: Missing timestamp
    with patch("app.api.v1.contact.get_redis_client"):
        payload = ContactRequest(
            name="User",
            email="user@example.com",
            message="Message",
            website="",
            timestamp=None,
        )
        request = MockRequest()

        response = await submit_contact_form(payload, request)
        results.assert_equal(response.success, True, "Missing timestamp returns success (silent reject)")


# ============================================================================
# Test: Content Validation
# ============================================================================

async def test_content_validation():
    """Test content validation (Layer 5)."""
    current_time = time.time() - 10

    # Test: Excessive URLs (4+)
    with patch("app.api.v1.contact.get_redis_client") as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis_instance.incr = AsyncMock(return_value=1)
        mock_redis_instance.expire = AsyncMock()
        mock_redis.return_value = mock_redis_instance

        payload = ContactRequest(
            name="User",
            email="user@example.com",
            message="https://spam1.com https://spam2.com https://spam3.com https://spam4.com",
            website="",
            timestamp=current_time,
        )
        request = MockRequest()

        response = await submit_contact_form(payload, request)
        results.assert_equal(response.success, True, "Excessive URLs returns success (silent reject)")

    # Test: Script tag detected
    with patch("app.api.v1.contact.get_redis_client") as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis_instance.incr = AsyncMock(return_value=1)
        mock_redis_instance.expire = AsyncMock()
        mock_redis.return_value = mock_redis_instance

        payload = ContactRequest(
            name="User",
            email="user@example.com",
            message="Hello <script>alert('XSS')</script> world",
            website="",
            timestamp=current_time,
        )
        request = MockRequest()

        response = await submit_contact_form(payload, request)
        results.assert_equal(response.success, True, "Script tag returns success (silent reject)")

    # Test: 3 URLs allowed
    with patch("app.api.v1.contact.get_redis_client") as mock_redis, \
         patch("app.workers.tasks.send_contact_emails_task") as mock_task:
        mock_redis_instance = MagicMock()
        mock_redis_instance.incr = AsyncMock(return_value=1)
        mock_redis_instance.expire = AsyncMock()
        mock_redis_instance.exists = AsyncMock(return_value=False)
        mock_redis_instance.setex = AsyncMock()
        mock_redis.return_value = mock_redis_instance
        mock_task.delay = MagicMock()

        payload = ContactRequest(
            name="User",
            email="user@example.com",
            message="https://example1.com https://example2.com https://example3.com",
            website="",
            timestamp=current_time,
        )
        request = MockRequest()

        response = await submit_contact_form(payload, request)
        results.assert_equal(response.success, True, "3 URLs allowed")
        results.assert_true(mock_task.delay.called, "Task was dispatched for valid 3-URL message")


# ============================================================================
# Test: Successful Submission
# ============================================================================

async def test_successful_submission():
    """Test that a valid submission dispatches the Celery task."""
    current_time = time.time() - 10

    with patch("app.api.v1.contact.get_redis_client") as mock_redis, \
         patch("app.workers.tasks.send_contact_emails_task") as mock_task:
        # Mock Redis (all checks pass)
        mock_redis_instance = MagicMock()
        mock_redis_instance.incr = AsyncMock(return_value=1)
        mock_redis_instance.expire = AsyncMock()
        mock_redis_instance.exists = AsyncMock(return_value=False)
        mock_redis_instance.setex = AsyncMock()
        mock_redis.return_value = mock_redis_instance

        # Mock Celery task
        mock_task.delay = MagicMock()

        payload = ContactRequest(
            name="Valid User",
            email="valid@example.com",
            message="This is a legitimate message.",
            website="",
            timestamp=current_time,
        )
        request = MockRequest()

        response = await submit_contact_form(payload, request)
        results.assert_equal(response.success, True, "Valid submission returns success")
        results.assert_true(mock_task.delay.called, "Celery task was dispatched")

        # Verify task arguments
        mock_task.delay.assert_called_once_with(
            name="Valid User",
            email="valid@example.com",
            message="This is a legitimate message.",
        )
        results.assert_true(True, "Task called with correct arguments")


# ============================================================================
# Test: Schema Validation (Pydantic)
# ============================================================================

def test_schema_validation():
    """Test Pydantic schema validation."""
    # Valid payload
    try:
        payload = ContactRequest(
            name="User",
            email="user@example.com",
            message="Message",
            website="",
            timestamp=time.time(),
        )
        results.assert_true(True, "Valid payload passes schema validation")
    except Exception as e:
        results.assert_true(False, f"Valid payload should not raise: {e}")

    # Missing name
    try:
        payload = ContactRequest(
            email="user@example.com",
            message="Message",
        )
        results.assert_true(False, "Missing name should raise validation error")
    except Exception:
        results.assert_true(True, "Missing name raises validation error")

    # Invalid email
    try:
        payload = ContactRequest(
            name="User",
            email="not-an-email",
            message="Message",
        )
        results.assert_true(False, "Invalid email should raise validation error")
    except Exception:
        results.assert_true(True, "Invalid email raises validation error")

    # Empty message
    try:
        payload = ContactRequest(
            name="User",
            email="user@example.com",
            message="",
        )
        results.assert_true(False, "Empty message should raise validation error")
    except Exception:
        results.assert_true(True, "Empty message raises validation error")

    # Message too long (>2000 chars)
    try:
        payload = ContactRequest(
            name="User",
            email="user@example.com",
            message="x" * 2001,
        )
        results.assert_true(False, "Message >2000 chars should raise validation error")
    except Exception:
        results.assert_true(True, "Message >2000 chars raises validation error")


# ============================================================================
# Main Test Runner
# ============================================================================

async def run_async_tests():
    """Run all async tests."""
    await test_rate_limiting()
    await test_duplicate_detection()
    await test_honeypot_detection()
    await test_timing_validation()
    await test_content_validation()
    await test_successful_submission()


def main():
    """Run all tests."""
    print("="*60)
    print("Contact Form Spam Protection Tests")
    print("="*60)
    print()

    # Sync tests
    print("Running synchronous tests...")
    test_client_ip_extraction()
    test_message_dedup_key()
    test_schema_validation()

    # Async tests
    print("\nRunning asynchronous tests...")
    asyncio.run(run_async_tests())

    # Summary
    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
