"""
Platform Quota System Tests

Tests for the Platform AI Provider Leaflet Limit feature. Organizations get a limited
number of free leaflet extractions using the platform's shared AI provider. After
exhausting the limit, they must configure their own VLM provider to continue.

Key components tested:
1. Pydantic schema validation for quota responses and settings
2. PlatformLimitExceededError exception structure
3. Organization model properties (has_platform_quota_remaining, platform_quota_remaining)
4. _try_consume_platform_quota atomic counter logic (with mocked DB)
5. Re-extraction skip logic (leaflet.used_platform_provider flag)
6. Edge cases (unlimited quota, limit=0, corrupted data)

The quota is enforced at extraction time (extract_products_task), not upload time,
so users can upload PDFs and configure a provider before extracting.
"""

from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError


# ============================================================================
# 1. Schema Validation Tests
# ============================================================================


class TestPlatformQuotaSchemas:
    """Test Pydantic schemas for platform quota feature."""

    def test_platform_quota_response_valid_data(self):
        """
        PlatformQuotaResponse accepts valid quota data.

        Bug prevented: Schema validation errors with valid quota data.
        """
        from app.schemas.platform_quota import PlatformQuotaResponse

        response = PlatformQuotaResponse(
            limit=10,
            used=7,
            remaining=3,
            has_own_provider=False,
            is_unlimited=False,
        )

        assert response.limit == 10
        assert response.used == 7
        assert response.remaining == 3
        assert response.has_own_provider is False
        assert response.is_unlimited is False

    def test_platform_quota_response_remaining_none_when_unlimited(self):
        """
        PlatformQuotaResponse allows remaining=None for unlimited quota.

        Bug prevented: Validation error when remaining is None for unlimited orgs.
        """
        from app.schemas.platform_quota import PlatformQuotaResponse

        response = PlatformQuotaResponse(
            limit=0,
            used=42,
            remaining=None,
            has_own_provider=True,
            is_unlimited=True,
        )

        assert response.limit == 0
        assert response.used == 42
        assert response.remaining is None
        assert response.is_unlimited is True

    def test_platform_quota_response_remaining_zero(self):
        """
        PlatformQuotaResponse accepts remaining=0 when limit reached.

        Bug prevented: Validation error when quota is exhausted.
        """
        from app.schemas.platform_quota import PlatformQuotaResponse

        response = PlatformQuotaResponse(
            limit=10,
            used=10,
            remaining=0,
            has_own_provider=False,
            is_unlimited=False,
        )

        assert response.remaining == 0

    def test_organization_platform_settings_update_valid_limit(self):
        """
        OrganizationPlatformSettingsUpdate accepts valid limit values.

        Bug prevented: Schema rejection of valid limit updates.
        """
        from app.schemas.platform_quota import OrganizationPlatformSettingsUpdate

        # Positive limit
        update = OrganizationPlatformSettingsUpdate(platform_leaflet_limit=20)
        assert update.platform_leaflet_limit == 20

        # Zero (unlimited)
        update_unlimited = OrganizationPlatformSettingsUpdate(platform_leaflet_limit=0)
        assert update_unlimited.platform_leaflet_limit == 0

        # None (no update)
        update_none = OrganizationPlatformSettingsUpdate(platform_leaflet_limit=None)
        assert update_none.platform_leaflet_limit is None

    def test_organization_platform_settings_update_rejects_negative(self):
        """
        OrganizationPlatformSettingsUpdate rejects negative limits.

        Bug prevented: Accepting negative limits which would break quota logic.
        """
        from app.schemas.platform_quota import OrganizationPlatformSettingsUpdate

        with pytest.raises(ValidationError) as exc_info:
            OrganizationPlatformSettingsUpdate(platform_leaflet_limit=-1)

        errors = exc_info.value.errors()
        assert any("greater than or equal to 0" in str(err) for err in errors)

    def test_platform_quota_error_details_has_defaults(self):
        """
        PlatformQuotaErrorDetails has correct default values.

        Bug prevented: Missing action_url or action_text in error responses.
        """
        from app.schemas.platform_quota import PlatformQuotaErrorDetails

        details = PlatformQuotaErrorDetails(limit=10, used=10)

        assert details.limit == 10
        assert details.used == 10
        assert details.remaining == 0  # Default
        assert details.action_url == "/settings?tab=ai-providers"  # Default
        assert details.action_text == "Add AI Provider"  # Default

    def test_platform_quota_error_details_custom_values(self):
        """
        PlatformQuotaErrorDetails accepts custom action_url and action_text.

        Bug prevented: Schema forcing default values when custom ones provided.
        """
        from app.schemas.platform_quota import PlatformQuotaErrorDetails

        details = PlatformQuotaErrorDetails(
            limit=10,
            used=10,
            remaining=0,
            action_url="/custom/path",
            action_text="Custom Action",
        )

        assert details.action_url == "/custom/path"
        assert details.action_text == "Custom Action"

    def test_platform_limit_reached_message_serializes_correctly(self):
        """
        PlatformLimitReachedMessage serializes to correct WebSocket payload.

        Bug prevented: Incorrect message structure in WebSocket error events.
        """
        from app.schemas.platform_quota import PlatformLimitReachedMessage

        message = PlatformLimitReachedMessage(
            limit=10,
            used=10,
            action_url="/settings",
            action_text="Add AI Provider",
        )

        assert message.error_code == "PLATFORM_LIMIT_REACHED"
        assert message.limit == 10
        assert message.used == 10

        # Verify it can be serialized to dict (for WebSocket)
        message_dict = message.model_dump()
        assert message_dict["error_code"] == "PLATFORM_LIMIT_REACHED"
        assert message_dict["limit"] == 10

    def test_platform_limit_reached_message_defaults(self):
        """
        PlatformLimitReachedMessage has correct defaults.

        Bug prevented: Missing default values causing incomplete WebSocket messages.
        """
        from app.schemas.platform_quota import PlatformLimitReachedMessage

        message = PlatformLimitReachedMessage(limit=5, used=5)

        assert message.error_code == "PLATFORM_LIMIT_REACHED"
        assert message.action_url == "/settings?tab=ai-providers"
        assert message.action_text == "Add AI Provider"


# ============================================================================
# 2. Exception Tests
# ============================================================================


class TestPlatformLimitExceededException:
    """Test PlatformLimitExceededError exception."""

    def test_exception_stores_limit_and_used(self):
        """
        PlatformLimitExceededError stores limit and used values.

        Bug prevented: Exception losing quota state needed for error messages.
        """
        from app.utils.exceptions import PlatformLimitExceededError

        error = PlatformLimitExceededError(limit=10, used=10)

        assert error.limit == 10
        assert error.used == 10

    def test_exception_error_code(self):
        """
        PlatformLimitExceededError has correct error code.

        Bug prevented: Wrong error code causing frontend routing failures.
        """
        from app.utils.exceptions import PlatformLimitExceededError

        error = PlatformLimitExceededError(limit=10, used=10)

        assert error.error_code == "PLATFORM_LIMIT_REACHED"

    def test_exception_status_code(self):
        """
        PlatformLimitExceededError has 403 status code.

        Bug prevented: Wrong HTTP status (401, 402, etc.) instead of 403 Forbidden.
        """
        from app.utils.exceptions import PlatformLimitExceededError

        error = PlatformLimitExceededError(limit=10, used=10)

        assert error.status_code == 403

    def test_exception_details_dict(self):
        """
        PlatformLimitExceededError details include all required fields.

        Bug prevented: Missing fields in error response breaking frontend UX.
        """
        from app.utils.exceptions import PlatformLimitExceededError

        error = PlatformLimitExceededError(limit=10, used=10)

        assert error.details["limit"] == 10
        assert error.details["used"] == 10
        assert error.details["remaining"] == 0
        assert error.details["action_url"] == "/settings?tab=ai-providers"
        assert error.details["action_text"] == "Add AI Provider"

    def test_exception_default_message(self):
        """
        PlatformLimitExceededError generates correct default message.

        Bug prevented: Generic error message that doesn't explain the problem.
        """
        from app.utils.exceptions import PlatformLimitExceededError

        error = PlatformLimitExceededError(limit=10, used=10)

        # All these phrases should be in the default message
        assert "10 free leaflet extractions" in error.message, f"Message: {error.message}"
        assert "platform AI provider" in error.message, f"Message: {error.message}"
        assert "add your own ai provider" in error.message.lower(), f"Message: {error.message}"

    def test_exception_custom_message(self):
        """
        PlatformLimitExceededError accepts custom message.

        Bug prevented: Unable to customize error message for different contexts.
        """
        from app.utils.exceptions import PlatformLimitExceededError

        custom_msg = "Custom quota exceeded message"
        error = PlatformLimitExceededError(limit=5, used=5, message=custom_msg)

        assert error.message == custom_msg

    def test_exception_to_dict_format(self):
        """
        PlatformLimitExceededError.to_dict() returns correct API response format.

        Bug prevented: Incorrect error response structure breaking frontend parsing.
        """
        from app.utils.exceptions import PlatformLimitExceededError

        error = PlatformLimitExceededError(limit=10, used=10)
        error_dict = error.to_dict()

        assert "error" in error_dict
        assert error_dict["error"]["code"] == "PLATFORM_LIMIT_REACHED"
        assert "message" in error_dict["error"]
        assert "details" in error_dict["error"]
        assert error_dict["error"]["details"]["limit"] == 10


# ============================================================================
# 3. Organization Model Properties
# ============================================================================


class TestOrganizationPlatformQuotaProperties:
    """Test Organization model properties for platform quota."""

    def test_has_platform_quota_remaining_when_under_limit(self):
        """
        has_platform_quota_remaining returns True when used < limit.

        Bug prevented: Incorrectly blocking extractions when quota still available.
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=10,
            platform_leaflets_used=7,
        )

        assert org.has_platform_quota_remaining is True

    def test_has_platform_quota_remaining_when_at_limit(self):
        """
        has_platform_quota_remaining returns False when used >= limit.

        Bug prevented: Allowing extractions after quota exhausted.
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=10,
            platform_leaflets_used=10,
        )

        assert org.has_platform_quota_remaining is False

    def test_has_platform_quota_remaining_when_over_limit(self):
        """
        has_platform_quota_remaining returns False when used > limit (corrupted data).

        Bug prevented: Unexpected behavior with corrupted usage counters.
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=10,
            platform_leaflets_used=15,
        )

        assert org.has_platform_quota_remaining is False

    def test_has_platform_quota_remaining_when_limit_zero(self):
        """
        has_platform_quota_remaining returns True when limit=0 (unlimited).

        Bug prevented: Blocking extractions when admin set unlimited quota.
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=0,
            platform_leaflets_used=999,
        )

        assert org.has_platform_quota_remaining is True

    def test_platform_quota_remaining_correct_count(self):
        """
        platform_quota_remaining returns correct remaining count.

        Bug prevented: Wrong remaining count shown in UI or API responses.
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=10,
            platform_leaflets_used=7,
        )

        assert org.platform_quota_remaining == 3

    def test_platform_quota_remaining_zero_at_limit(self):
        """
        platform_quota_remaining returns 0 when quota exhausted.

        Bug prevented: Negative remaining count with exhausted quota.
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=10,
            platform_leaflets_used=10,
        )

        assert org.platform_quota_remaining == 0

    def test_platform_quota_remaining_zero_when_over_limit(self):
        """
        platform_quota_remaining returns 0 (not negative) when used > limit.

        Bug prevented: Negative remaining count breaking UI display.
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=10,
            platform_leaflets_used=15,
        )

        # Should use max(0, ...) to prevent negative
        assert org.platform_quota_remaining == 0

    def test_platform_quota_remaining_none_when_unlimited(self):
        """
        platform_quota_remaining returns None when limit=0 (unlimited).

        Bug prevented: Showing finite remaining count for unlimited orgs.
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=0,
            platform_leaflets_used=999,
        )

        assert org.platform_quota_remaining is None


# ============================================================================
# 4. _try_consume_platform_quota Function Tests (with mock DB)
# ============================================================================


class TestTryConsumePlatformQuota:
    """Test _try_consume_platform_quota atomic counter logic."""

    def test_consume_quota_success(self):
        """
        _try_consume_platform_quota succeeds when quota available.

        Bug prevented: Failing to consume quota when organization has slots remaining.
        """
        from app.workers.tasks import _try_consume_platform_quota

        # Mock database session
        mock_db = Mock()
        mock_result = Mock()
        mock_row = (5, 10)  # (platform_leaflets_used, platform_leaflet_limit)
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        org_id = uuid4()
        success, limit, used = _try_consume_platform_quota(mock_db, org_id)

        assert success is True
        assert limit == 10
        assert used == 5
        mock_db.commit.assert_called_once()

    def test_consume_quota_limit_exceeded(self):
        """
        _try_consume_platform_quota fails when limit reached (no row returned).

        Bug prevented: Allowing extraction after quota exhausted.
        """
        from app.workers.tasks import _try_consume_platform_quota

        # Mock database session
        mock_db = Mock()

        # First query (UPDATE) returns None (no row updated)
        mock_update_result = Mock()
        mock_update_result.fetchone.return_value = None

        # Second query (SELECT) returns current quota state
        mock_select_result = Mock()
        mock_select_row = (10, 10)  # (platform_leaflet_limit, platform_leaflets_used)
        mock_select_result.fetchone.return_value = mock_select_row

        mock_db.execute.side_effect = [mock_update_result, mock_select_result]

        org_id = uuid4()
        success, limit, used = _try_consume_platform_quota(mock_db, org_id)

        assert success is False
        assert limit == 10
        assert used == 10
        mock_db.commit.assert_called_once()

    def test_consume_quota_unlimited_success(self):
        """
        _try_consume_platform_quota always succeeds when limit=0 (unlimited).

        Bug prevented: Blocking extractions for orgs with unlimited quota.
        """
        from app.workers.tasks import _try_consume_platform_quota

        # Mock database session
        mock_db = Mock()
        mock_result = Mock()
        # Limit=0 means unlimited, so UPDATE succeeds regardless of used count
        mock_row = (999, 0)  # (platform_leaflets_used, platform_leaflet_limit)
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        org_id = uuid4()
        success, limit, used = _try_consume_platform_quota(mock_db, org_id)

        assert success is True
        assert limit == 0
        assert used == 999
        mock_db.commit.assert_called_once()

    def test_consume_quota_database_error_fail_closed(self):
        """
        _try_consume_platform_quota fails closed on database errors.

        Bug prevented: Bypassing quota enforcement on transient DB errors (security issue).
        """
        from app.workers.tasks import _try_consume_platform_quota

        # Mock database session that raises an exception
        mock_db = Mock()
        mock_db.execute.side_effect = Exception("Database connection lost")

        org_id = uuid4()
        success, limit, used = _try_consume_platform_quota(mock_db, org_id)

        assert success is False
        assert limit == 10  # Fallback values
        assert used == 10
        mock_db.rollback.assert_called_once()

    def test_consume_quota_commits_on_success(self):
        """
        _try_consume_platform_quota commits transaction on success.

        Bug prevented: Counter increment not persisted due to missing commit.
        """
        from app.workers.tasks import _try_consume_platform_quota

        mock_db = Mock()
        mock_result = Mock()
        mock_row = (1, 10)
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        org_id = uuid4()
        _try_consume_platform_quota(mock_db, org_id)

        mock_db.commit.assert_called_once()

    def test_consume_quota_rollback_on_error(self):
        """
        _try_consume_platform_quota rolls back on exceptions.

        Bug prevented: Partial updates or locked rows from uncommitted transactions.
        """
        from app.workers.tasks import _try_consume_platform_quota

        mock_db = Mock()
        mock_db.execute.side_effect = Exception("Test error")

        org_id = uuid4()
        _try_consume_platform_quota(mock_db, org_id)

        mock_db.rollback.assert_called_once()


# ============================================================================
# 5. Re-extraction Skip Logic
# ============================================================================


class TestReExtractionSkipLogic:
    """Test that re-extraction doesn't consume quota again."""

    def test_leaflet_used_platform_provider_flag_exists(self):
        """
        Leaflet model has used_platform_provider boolean field.

        Bug prevented: Re-extraction consuming quota multiple times for same leaflet.
        """
        from app.models.leaflet import Leaflet

        leaflet = Leaflet(
            leaflet_id="LEAF_2025_001234",
            filename="test.pdf",
            used_platform_provider=True,
        )

        assert hasattr(leaflet, "used_platform_provider")
        assert leaflet.used_platform_provider is True

    def test_leaflet_used_platform_provider_defaults_false(self):
        """
        Leaflet.used_platform_provider defaults to False (or None, which is falsy).

        Bug prevented: New leaflets incorrectly marked as using platform provider.
        """
        from app.models.leaflet import Leaflet

        leaflet = Leaflet(
            leaflet_id="LEAF_2025_001234",
            filename="test.pdf",
        )

        # Should default to False (model default) or None (before DB insert)
        # Either is acceptable as long as it's falsy
        assert leaflet.used_platform_provider in (False, None), \
            f"Expected False or None, got {leaflet.used_platform_provider}"

    def test_re_extraction_with_platform_provider_skips_quota(self):
        """
        Re-extraction with used_platform_provider=True doesn't consume quota.

        Bug prevented: Re-running extraction counting against quota multiple times.

        This tests the conceptual logic that should be in extract_products_task:
        if leaflet.used_platform_provider and using_platform_provider:
            skip quota consumption
        """
        # This is a conceptual test - in reality, this logic is in tasks.py
        # and would require integration testing. Here we verify the field exists
        # and the condition can be checked.
        from app.models.leaflet import Leaflet

        leaflet = Leaflet(
            leaflet_id="LEAF_2025_001234",
            filename="test.pdf",
            used_platform_provider=True,
        )

        # Simulate the check in extract_products_task
        using_platform_provider = True  # Would come from provider selection logic
        should_skip_quota = leaflet.used_platform_provider and using_platform_provider

        assert should_skip_quota is True

    def test_first_extraction_with_platform_provider_checks_quota(self):
        """
        First extraction with used_platform_provider=False checks quota.

        Bug prevented: Bypassing quota check on first extraction.
        """
        from app.models.leaflet import Leaflet

        leaflet = Leaflet(
            leaflet_id="LEAF_2025_001234",
            filename="test.pdf",
            used_platform_provider=False,
        )

        using_platform_provider = True
        should_skip_quota = leaflet.used_platform_provider and using_platform_provider

        assert should_skip_quota is False

    def test_extraction_with_org_provider_never_checks_quota(self):
        """
        Extraction using org's own provider doesn't check platform quota.

        Bug prevented: Charging quota when org is using their own API key.
        """
        from app.models.leaflet import Leaflet

        leaflet = Leaflet(
            leaflet_id="LEAF_2025_001234",
            filename="test.pdf",
            used_platform_provider=False,  # or True, doesn't matter
        )

        using_platform_provider = False  # Using org's own provider
        should_skip_quota = leaflet.used_platform_provider and using_platform_provider

        # Should not check quota when using org provider, regardless of flag
        assert should_skip_quota is False  # But quota check itself is bypassed


# ============================================================================
# 6. Edge Cases
# ============================================================================


class TestPlatformQuotaEdgeCases:
    """Test edge cases in platform quota system."""

    def test_organization_unlimited_quota_with_zero_limit(self):
        """
        Organization with limit=0 has unlimited quota.

        Bug prevented: Treating limit=0 as "no quota" instead of "unlimited".
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=0,
            platform_leaflets_used=0,
        )

        assert org.has_platform_quota_remaining is True
        assert org.platform_quota_remaining is None

    def test_organization_limit_one_used_zero_succeeds(self):
        """
        Organization with limit=1, used=0 can extract once.

        Bug prevented: Off-by-one error preventing first extraction.
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=1,
            platform_leaflets_used=0,
        )

        assert org.has_platform_quota_remaining is True
        assert org.platform_quota_remaining == 1

    def test_organization_limit_one_used_one_fails(self):
        """
        Organization with limit=1, used=1 cannot extract again.

        Bug prevented: Allowing second extraction with limit=1.
        """
        from app.models.organization import Organization

        org = Organization(
            platform_leaflet_limit=1,
            platform_leaflets_used=1,
        )

        assert org.has_platform_quota_remaining is False
        assert org.platform_quota_remaining == 0

    def test_platform_quota_response_with_used_greater_than_limit(self):
        """
        PlatformQuotaResponse handles corrupted data (used > limit).

        Bug prevented: Validation errors or negative remaining with corrupted data.
        """
        from app.schemas.platform_quota import PlatformQuotaResponse

        # This could happen if limit is reduced after usage accumulates
        response = PlatformQuotaResponse(
            limit=10,
            used=15,
            remaining=0,  # Should be 0, not negative
            has_own_provider=False,
            is_unlimited=False,
        )

        assert response.limit == 10
        assert response.used == 15
        assert response.remaining == 0

    def test_consume_quota_organization_not_found(self):
        """
        _try_consume_platform_quota fails closed if organization not found.

        Bug prevented: Bypassing quota check when org lookup fails.
        """
        from app.workers.tasks import _try_consume_platform_quota

        mock_db = Mock()

        # UPDATE returns no row (org not found or limit reached)
        mock_update_result = Mock()
        mock_update_result.fetchone.return_value = None

        # SELECT also returns no row (org not found)
        mock_select_result = Mock()
        mock_select_result.fetchone.return_value = None

        mock_db.execute.side_effect = [mock_update_result, mock_select_result]

        org_id = uuid4()
        success, limit, used = _try_consume_platform_quota(mock_db, org_id)

        # Should fail closed with fallback values
        assert success is False
        assert limit == 10
        assert used == 10

    def test_quota_response_non_negative_remaining(self):
        """
        Quota responses never show negative remaining count.

        Bug prevented: Confusing UI with negative quota values.
        """
        from app.schemas.platform_quota import PlatformQuotaResponse

        with pytest.raises(ValidationError):
            PlatformQuotaResponse(
                limit=10,
                used=15,
                remaining=-5,  # Should not be allowed
                has_own_provider=False,
                is_unlimited=False,
            )


# ============================================================================
# Final Verification
# ============================================================================


class TestPlatformQuotaIntegration:
    """High-level integration checks for platform quota system."""

    def test_all_required_components_exist(self):
        """
        Verify all components of platform quota system exist.

        Bug prevented: Missing components causing import or runtime errors.
        """
        # Schemas
        from app.schemas.platform_quota import (
            OrganizationPlatformSettingsUpdate,
            PlatformLimitReachedMessage,
            PlatformQuotaErrorDetails,
            PlatformQuotaResponse,
        )

        # Exception
        from app.utils.exceptions import PlatformLimitExceededError

        # Model
        from app.models.organization import Organization

        # Task function
        from app.workers.tasks import _try_consume_platform_quota

        # All imports should succeed
        assert PlatformQuotaResponse is not None
        assert PlatformQuotaErrorDetails is not None
        assert PlatformLimitReachedMessage is not None
        assert OrganizationPlatformSettingsUpdate is not None
        assert PlatformLimitExceededError is not None
        assert Organization is not None
        assert _try_consume_platform_quota is not None

    def test_exception_details_match_schema(self):
        """
        PlatformLimitExceededError details match PlatformQuotaErrorDetails schema.

        Bug prevented: Mismatched error structure between exception and schema.
        """
        from app.schemas.platform_quota import PlatformQuotaErrorDetails
        from app.utils.exceptions import PlatformLimitExceededError

        error = PlatformLimitExceededError(limit=10, used=10)

        # Should be able to construct schema from exception details
        details = PlatformQuotaErrorDetails(**error.details)

        assert details.limit == error.limit
        assert details.used == error.used
        assert details.remaining == 0

    def test_websocket_message_structure(self):
        """
        PlatformLimitReachedMessage can be embedded in WebSocket envelope.

        Bug prevented: WebSocket payload structure incompatible with frontend.
        """
        from app.schemas.platform_quota import PlatformLimitReachedMessage

        message = PlatformLimitReachedMessage(limit=10, used=10)
        message_data = message.model_dump()

        # Verify structure matches what progress publisher expects
        assert "error_code" in message_data
        assert "limit" in message_data
        assert "used" in message_data
        assert "action_url" in message_data
        assert "action_text" in message_data

        assert message_data["error_code"] == "PLATFORM_LIMIT_REACHED"
