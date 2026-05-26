"""
Pure Unit Tests for API Key Authentication Logic.

These tests verify the logic without requiring database setup, using mocking.
Run directly with: python -m pytest tests/unit/test_api_key_auth_unit.py -v

Or run standalone: python tests/unit/test_api_key_auth_unit.py
"""

import sys
import os
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch

# Test can run standalone
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-minimum-32-chars"


from app.models.api_key import APIKey
from app.models.user import User
from app.models.organization import Organization
from app.utils.security import hash_password


class TestAPIKeyGeneration:
    """Tests for API key generation and hashing."""

    def test_generate_key_format(self):
        """Test that generated API keys have the correct format."""
        key = APIKey.generate_key()

        assert key.startswith("lep_")
        assert len(key) > 10  # lep_ + random part

    def test_generate_key_unique(self):
        """Test that generated keys are unique."""
        key1 = APIKey.generate_key()
        key2 = APIKey.generate_key()

        assert key1 != key2

    def test_hash_key_consistent(self):
        """Test that hashing the same key produces the same hash."""
        key = "lep_test_key_12345"
        hash1 = APIKey.hash_key(key)
        hash2 = APIKey.hash_key(key)

        assert hash1 == hash2
        assert hash1 != key  # Hash should be different from key

    def test_hash_key_different_keys(self):
        """Test that different keys produce different hashes."""
        key1 = "lep_test_key_1"
        key2 = "lep_test_key_2"

        hash1 = APIKey.hash_key(key1)
        hash2 = APIKey.hash_key(key2)

        assert hash1 != hash2


class TestAPIKeyCreation:
    """Tests for API key creation logic."""

    def test_create_key_returns_tuple(self):
        """Test that create_key returns (APIKey, raw_key) tuple."""
        user_id = uuid4()
        org_id = uuid4()

        api_key, raw_key = APIKey.create_key(
            user_id=user_id,
            organization_id=org_id,
            name="Test Key",
            scopes=["read"],
        )

        assert isinstance(api_key, APIKey)
        assert isinstance(raw_key, str)
        assert raw_key.startswith("lep_")

    def test_create_key_sets_prefix(self):
        """Test that key_prefix is set from raw key."""
        user_id = uuid4()
        org_id = uuid4()

        api_key, raw_key = APIKey.create_key(
            user_id=user_id,
            organization_id=org_id,
            name="Test Key",
            scopes=["read"],
        )

        assert api_key.key_prefix == raw_key[:12]

    def test_create_key_with_expiration(self):
        """Test that expiration is set correctly."""
        user_id = uuid4()
        org_id = uuid4()

        api_key, raw_key = APIKey.create_key(
            user_id=user_id,
            organization_id=org_id,
            name="Test Key",
            scopes=["read"],
            expires_in_days=7,
        )

        assert api_key.expires_at is not None
        # Should expire approximately 7 days from now
        expected_expiry = datetime.utcnow() + timedelta(days=7)
        assert abs((api_key.expires_at - expected_expiry).total_seconds()) < 10

    def test_create_key_with_daily_limit(self):
        """Test that daily_limit is set."""
        user_id = uuid4()
        org_id = uuid4()

        api_key, raw_key = APIKey.create_key(
            user_id=user_id,
            organization_id=org_id,
            name="Limited Key",
            scopes=["read"],
            daily_limit=100,
        )

        assert api_key.daily_limit == 100

    def test_create_key_with_ip_whitelist(self):
        """Test that IP whitelist is set."""
        user_id = uuid4()
        org_id = uuid4()

        allowed_ips = ["192.168.1.1", "10.0.0.1"]
        api_key, raw_key = APIKey.create_key(
            user_id=user_id,
            organization_id=org_id,
            name="IP Restricted Key",
            scopes=["read"],
            allowed_ips=allowed_ips,
        )

        assert api_key.allowed_ips == allowed_ips


class TestAPIKeyValidation:
    """Tests for API key validation logic."""

    def test_is_valid_active_key(self):
        """Test that an active, non-expired key is valid."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Valid Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            is_active=True,
            expires_at=None,  # No expiration
        )

        assert api_key.is_valid is True

    def test_is_valid_inactive_key(self):
        """Test that an inactive key is not valid."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Inactive Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            is_active=False,
            expires_at=None,
        )

        assert api_key.is_valid is False

    def test_is_expired_future_date(self):
        """Test that a key expiring in the future is not expired."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Future Expiry Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=1),
        )

        assert api_key.is_expired is False

    def test_is_expired_past_date(self):
        """Test that a key expired in the past is expired."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Expired Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            is_active=True,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )

        assert api_key.is_expired is True

    def test_is_expired_no_expiration(self):
        """Test that a key with no expiration is not expired."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="No Expiry Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            is_active=True,
            expires_at=None,
        )

        assert api_key.is_expired is False


class TestAPIKeyScopeChecking:
    """Tests for scope checking logic."""

    def test_has_scope_present(self):
        """Test that has_scope returns True for a scope the key has."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Read Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read", "write"],
        )

        assert api_key.has_scope("read") is True
        assert api_key.has_scope("write") is True

    def test_has_scope_absent(self):
        """Test that has_scope returns False for a scope the key doesn't have."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Read Only Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
        )

        assert api_key.has_scope("write") is False
        assert api_key.has_scope("delete") is False

    def test_has_scope_admin_grants_all(self):
        """Test that 'admin' scope grants all permissions."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Admin Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["admin"],
        )

        assert api_key.has_scope("read") is True
        assert api_key.has_scope("write") is True
        assert api_key.has_scope("delete") is True
        assert api_key.has_scope("any_other_scope") is True


class TestAPIKeyIPCheck:
    """Tests for IP whitelist checking."""

    def test_check_ip_no_whitelist(self):
        """Test that any IP is allowed when there's no whitelist."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="No Whitelist Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            allowed_ips=None,
        )

        assert api_key.check_ip("192.168.1.1") is True
        assert api_key.check_ip("10.0.0.1") is True
        assert api_key.check_ip("any.ip.address") is True

    def test_check_ip_whitelist_allowed(self):
        """Test that whitelisted IPs are allowed."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Whitelist Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            allowed_ips=["192.168.1.1", "10.0.0.1"],
        )

        assert api_key.check_ip("192.168.1.1") is True
        assert api_key.check_ip("10.0.0.1") is True

    def test_check_ip_whitelist_blocked(self):
        """Test that non-whitelisted IPs are blocked."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Whitelist Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            allowed_ips=["192.168.1.1"],
        )

        assert api_key.check_ip("10.0.0.1") is False
        assert api_key.check_ip("8.8.8.8") is False


class TestAPIKeyDailyLimit:
    """Tests for daily limit checking."""

    def test_check_daily_limit_no_limit(self):
        """Test that no limit means always allowed."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Unlimited Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            daily_limit=None,
            requests_today=1000,
        )

        assert api_key.check_daily_limit() is True

    def test_check_daily_limit_no_reset_date(self):
        """Test that first use is allowed."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="First Use Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            daily_limit=100,
            requests_today=0,
            last_reset_date=None,
        )

        assert api_key.check_daily_limit() is True

    def test_check_daily_limit_under_limit(self):
        """Test that usage under limit is allowed."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Under Limit Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            daily_limit=100,
            requests_today=50,
            last_reset_date=datetime.utcnow(),
        )

        assert api_key.check_daily_limit() is True

    def test_check_daily_limit_at_limit(self):
        """Test that usage at limit is blocked."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="At Limit Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            daily_limit=100,
            requests_today=100,
            last_reset_date=datetime.utcnow(),
        )

        assert api_key.check_daily_limit() is False

    def test_check_daily_limit_over_limit(self):
        """Test that usage over limit is blocked."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Over Limit Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            daily_limit=100,
            requests_today=150,
            last_reset_date=datetime.utcnow(),
        )

        assert api_key.check_daily_limit() is False


class TestAPIKeyUsageRecording:
    """Tests for usage recording logic."""

    def test_record_usage_increments_counters(self):
        """Test that record_usage increments counters."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Usage Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            total_requests=0,
            requests_today=0,
            last_reset_date=datetime.utcnow(),
        )

        api_key.record_usage(ip="192.168.1.1")

        assert api_key.total_requests == 1
        assert api_key.requests_today == 1
        assert api_key.last_used_ip == "192.168.1.1"
        assert api_key.last_used_at is not None

    def test_record_usage_multiple_times(self):
        """Test that multiple usage recordings accumulate."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Usage Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            total_requests=10,
            requests_today=5,
            last_reset_date=datetime.utcnow(),
        )

        api_key.record_usage(ip="10.0.0.1")
        api_key.record_usage(ip="10.0.0.2")

        assert api_key.total_requests == 12
        assert api_key.requests_today == 7
        assert api_key.last_used_ip == "10.0.0.2"

    def test_record_usage_resets_daily_counter(self):
        """Test that daily counter resets on new day."""
        # Set last reset to yesterday
        yesterday = datetime.utcnow() - timedelta(days=1)

        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Reset Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            total_requests=100,
            requests_today=50,
            last_reset_date=yesterday,
        )

        api_key.record_usage()

        # Daily counter should reset, total should increment
        assert api_key.total_requests == 101
        assert api_key.requests_today == 1  # Reset to 1 (current request)
        assert api_key.last_reset_date.date() == datetime.utcnow().date()


class TestAPIKeyRevocation:
    """Tests for API key revocation."""

    def test_revoke_sets_inactive(self):
        """Test that revoking a key sets is_active to False."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Revoke Key",
            key_prefix="lep_test",
            key_hash="hash",
            scopes=["read"],
            is_active=True,
        )

        assert api_key.is_active is True
        api_key.revoke()
        assert api_key.is_active is False


class TestAPIKeySafeSerialization:
    """Tests for safe dictionary serialization."""

    def test_to_safe_dict_excludes_hash(self):
        """Test that to_safe_dict excludes the key_hash."""
        api_key = APIKey(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            name="Safe Dict Key",
            key_prefix="lep_test",
            key_hash="secret_hash_value",
            scopes=["read", "write"],
            total_requests=100,
            is_active=True,
        )

        safe_dict = api_key.to_safe_dict()

        assert "key_hash" not in safe_dict
        assert "name" in safe_dict
        assert safe_dict["name"] == "Safe Dict Key"
        assert safe_dict["key_prefix"] == "lep_test"
        assert safe_dict["scopes"] == ["read", "write"]


def run_standalone_tests():
    """Run tests without pytest."""
    import inspect

    # Collect all test classes
    test_classes = [
        TestAPIKeyGeneration,
        TestAPIKeyCreation,
        TestAPIKeyValidation,
        TestAPIKeyScopeChecking,
        TestAPIKeyIPCheck,
        TestAPIKeyDailyLimit,
        TestAPIKeyUsageRecording,
        TestAPIKeyRevocation,
        TestAPIKeySafeSerialization,
    ]

    passed = 0
    failed = 0
    errors = []

    print("Running API Key Auth Unit Tests (Standalone Mode)")
    print("=" * 60)

    for test_class in test_classes:
        class_name = test_class.__name__
        print(f"\n{class_name}:")

        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith("test_")]

        for method_name in methods:
            try:
                method = getattr(instance, method_name)
                method()
                passed += 1
                print(f"  PASS {method_name}")
            except AssertionError as e:
                failed += 1
                errors.append((f"{class_name}.{method_name}", str(e)))
                print(f"  FAIL {method_name}: {e}")
            except Exception as e:
                failed += 1
                errors.append((f"{class_name}.{method_name}", str(e)))
                print(f"  ERROR {method_name}: {type(e).__name__}: {e}")

    # Summary
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} tests passed")
    if failed > 0:
        print(f"\nFailed tests:")
        for test_name, error in errors:
            print(f"  - {test_name}")
            if error:
                print(f"    {error}")
    print(f"{'=' * 60}")

    return failed == 0


if __name__ == "__main__":
    success = run_standalone_tests()
    sys.exit(0 if success else 1)
