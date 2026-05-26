"""
Unit tests for VLM provider API schema validation and logic.

This test file validates the Pydantic schemas and encryption logic used
by the VLM provider creation endpoint (POST /api/v1/vlm-providers/).

Tests cover:
1. Schema validation for VLMProviderCreate
2. Input validation (type, length, range checks)
3. Error response format verification
4. API key encryption/decryption

Note: These are unit tests that don't require a database or FastAPI test client.
They validate schema logic and encryption independently.
"""

import pytest
from pydantic import ValidationError
from decimal import Decimal


# --- Schema Validation Tests ---


def test_valid_provider_create():
    """Valid data should pass schema validation."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    data = VLMProviderCreate(
        provider_type=VLMProviderType.ANTHROPIC,
        name='Test Provider',
        api_key='sk-ant-api03-xxxxxxxxxxxx',
        model_name='claude-sonnet-4-20250514',
    )

    assert data.provider_type == VLMProviderType.ANTHROPIC
    assert data.name == 'Test Provider'
    assert data.api_key == 'sk-ant-api03-xxxxxxxxxxxx'
    assert data.model_name == 'claude-sonnet-4-20250514'


def test_valid_provider_create_all_fields():
    """Valid data with all optional fields should pass."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    data = VLMProviderCreate(
        provider_type=VLMProviderType.OPENAI,
        name='OpenAI Provider',
        api_key='sk-proj-test-key-12345678901234',
        api_endpoint='https://api.openai.com/v1',
        model_name='gpt-4o',
        max_tokens=4096,
        temperature=0.3,
        monthly_budget=100.0,
        is_default=True,
        config={'custom_param': 'value'},
    )

    assert data.provider_type == VLMProviderType.OPENAI
    assert data.max_tokens == 4096
    assert data.temperature == 0.3
    assert data.monthly_budget == 100.0
    assert data.is_default is True
    assert data.config == {'custom_param': 'value'}


def test_invalid_provider_type():
    """Invalid provider type should raise validation error."""
    from app.api.v1.vlm_providers import VLMProviderCreate

    with pytest.raises(ValidationError) as exc_info:
        VLMProviderCreate(
            provider_type='invalid_type',
            name='Test',
            api_key='sk-ant-api03-xxxxxxxxxxxx',
        )

    errors = exc_info.value.errors()
    assert any('provider_type' in str(err['loc']) for err in errors)


def test_api_key_too_short():
    """API key shorter than 10 chars should fail validation."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    with pytest.raises(ValidationError) as exc_info:
        VLMProviderCreate(
            provider_type=VLMProviderType.ANTHROPIC,
            name='Test',
            api_key='short',  # Only 5 characters
        )

    errors = exc_info.value.errors()
    assert any('api_key' in str(err['loc']) for err in errors)
    # Should mention minimum length
    assert any('at least 10' in str(err['msg']).lower() for err in errors)


def test_name_empty():
    """Empty name should fail validation."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    with pytest.raises(ValidationError) as exc_info:
        VLMProviderCreate(
            provider_type=VLMProviderType.ANTHROPIC,
            name='',  # Empty string
            api_key='sk-ant-api03-xxxxxxxxxxxx',
        )

    errors = exc_info.value.errors()
    assert any('name' in str(err['loc']) for err in errors)


def test_name_too_long():
    """Name longer than 100 chars should fail validation."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    long_name = 'A' * 101  # 101 characters

    with pytest.raises(ValidationError) as exc_info:
        VLMProviderCreate(
            provider_type=VLMProviderType.ANTHROPIC,
            name=long_name,
            api_key='sk-ant-api03-xxxxxxxxxxxx',
        )

    errors = exc_info.value.errors()
    assert any('name' in str(err['loc']) for err in errors)


def test_monthly_budget_negative():
    """Negative monthly budget should fail validation."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    with pytest.raises(ValidationError) as exc_info:
        VLMProviderCreate(
            provider_type=VLMProviderType.ANTHROPIC,
            name='Test',
            api_key='sk-ant-api03-xxxxxxxxxxxx',
            monthly_budget=-10.0,  # Negative
        )

    errors = exc_info.value.errors()
    assert any('monthly_budget' in str(err['loc']) for err in errors)


def test_monthly_budget_zero_is_valid():
    """Zero monthly budget is technically valid (no spending allowed)."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    data = VLMProviderCreate(
        provider_type=VLMProviderType.ANTHROPIC,
        name='Test',
        api_key='sk-ant-api03-xxxxxxxxxxxx',
        monthly_budget=0.0,
    )

    assert data.monthly_budget == 0.0


def test_temperature_out_of_range_high():
    """Temperature > 2 should fail validation."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    with pytest.raises(ValidationError) as exc_info:
        VLMProviderCreate(
            provider_type=VLMProviderType.ANTHROPIC,
            name='Test',
            api_key='sk-ant-api03-xxxxxxxxxxxx',
            temperature=3.0,  # > 2
        )

    errors = exc_info.value.errors()
    assert any('temperature' in str(err['loc']) for err in errors)


def test_temperature_out_of_range_negative():
    """Negative temperature should fail validation."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    with pytest.raises(ValidationError) as exc_info:
        VLMProviderCreate(
            provider_type=VLMProviderType.ANTHROPIC,
            name='Test',
            api_key='sk-ant-api03-xxxxxxxxxxxx',
            temperature=-0.1,  # Negative
        )

    errors = exc_info.value.errors()
    assert any('temperature' in str(err['loc']) for err in errors)


def test_max_tokens_below_minimum():
    """max_tokens < 100 should fail validation."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    with pytest.raises(ValidationError) as exc_info:
        VLMProviderCreate(
            provider_type=VLMProviderType.ANTHROPIC,
            name='Test',
            api_key='sk-ant-api03-xxxxxxxxxxxx',
            max_tokens=50,  # < 100
        )

    errors = exc_info.value.errors()
    assert any('max_tokens' in str(err['loc']) for err in errors)


def test_max_tokens_above_maximum():
    """max_tokens > 32000 should fail validation."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    with pytest.raises(ValidationError) as exc_info:
        VLMProviderCreate(
            provider_type=VLMProviderType.ANTHROPIC,
            name='Test',
            api_key='sk-ant-api03-xxxxxxxxxxxx',
            max_tokens=50000,  # > 32000
        )

    errors = exc_info.value.errors()
    assert any('max_tokens' in str(err['loc']) for err in errors)


def test_optional_fields_default():
    """Optional fields should have correct defaults."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    data = VLMProviderCreate(
        provider_type=VLMProviderType.OPENAI,
        name='Test',
        api_key='sk-test-key-12345',
    )

    assert data.max_tokens == 8192
    assert data.temperature == 0.1
    assert data.is_default is False
    assert data.monthly_budget is None
    assert data.api_endpoint is None
    assert data.model_name is None
    assert data.config is None


# --- Error Format Tests ---


def test_422_error_format():
    """
    FastAPI 422 errors have detail array format.

    This validates that Pydantic validation errors match the structure
    that the frontend's extractErrorMessage() helper expects.
    """
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    try:
        VLMProviderCreate(
            provider_type='invalid',
            name='',
            api_key='short',
        )
    except ValidationError as e:
        errors = e.errors()

        # Verify structure matches FastAPI 422 format
        assert isinstance(errors, list)
        assert len(errors) > 0

        for error in errors:
            assert 'msg' in error
            assert 'loc' in error
            assert 'type' in error
            assert isinstance(error['loc'], tuple)


def test_custom_error_format():
    """
    Custom app errors have error.message format.

    This documents the expected structure for custom ValidationException
    and other app exceptions.
    """
    # Document expected format for custom errors
    error_body = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Provider name already exists",
            "details": None,
        }
    }

    assert error_body["error"]["message"] == "Provider name already exists"
    assert error_body["error"]["code"] == "VALIDATION_ERROR"


# --- Fernet Encryption Tests ---


def test_api_key_encryption():
    """
    API key should be encrypted with Fernet and decryptable.

    Tests the VLMProvider model's set_api_key() and get_api_key() methods
    to ensure encryption is working correctly.
    """
    from app.models.vlm_provider import VLMProvider

    test_key = "sk-ant-api03-test-key-12345"
    provider = VLMProvider()

    # Encrypt the key
    provider.set_api_key(test_key)

    # Verify it's encrypted (not plaintext)
    assert provider.api_key_encrypted != test_key
    assert len(provider.api_key_encrypted) > len(test_key)

    # Verify it decrypts back to original
    decrypted = provider.get_api_key()
    assert decrypted == test_key


def test_api_key_masked():
    """Masked API key should hide most characters."""
    from app.models.vlm_provider import VLMProvider

    test_key = "sk-ant-api03-test-key-12345"
    provider = VLMProvider()
    provider.set_api_key(test_key)

    masked = provider.get_masked_api_key()

    # Should show first 4 and last 4 characters
    assert masked.startswith("sk-a")
    assert masked.endswith("2345")
    assert "..." in masked
    # Should be shorter than original
    assert len(masked) < len(test_key)


def test_api_key_masked_short():
    """Very short API keys should mask to ****."""
    from app.models.vlm_provider import VLMProvider

    # Test with a short key (less than 8 chars)
    short_key = "test123"
    provider = VLMProvider()
    provider.set_api_key(short_key)

    masked = provider.get_masked_api_key()
    assert masked == "****"


def test_encryption_different_each_time():
    """
    Encrypting the same key twice should produce different ciphertext.

    Fernet uses a timestamp and random IV, so the same plaintext encrypts
    to different ciphertext each time.
    """
    from app.models.vlm_provider import VLMProvider

    test_key = "sk-ant-api03-test-key-12345"

    provider1 = VLMProvider()
    provider1.set_api_key(test_key)

    provider2 = VLMProvider()
    provider2.set_api_key(test_key)

    # Different ciphertext
    assert provider1.api_key_encrypted != provider2.api_key_encrypted

    # But both decrypt to same plaintext
    assert provider1.get_api_key() == test_key
    assert provider2.get_api_key() == test_key


# --- Provider Type Enum Tests ---


def test_all_provider_types_valid():
    """All VLMProviderType enum values should be valid in schema."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    for provider_type in VLMProviderType:
        data = VLMProviderCreate(
            provider_type=provider_type,
            name=f'Test {provider_type.value}',
            api_key='sk-test-key-1234567890',
        )
        assert data.provider_type == provider_type


def test_provider_type_string_value():
    """Provider type can be passed as string value."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    # Pydantic should accept string value and convert to enum
    data = VLMProviderCreate(
        provider_type='anthropic',  # String, not enum
        name='Test',
        api_key='sk-ant-api03-xxxxxxxxxxxx',
    )

    assert data.provider_type == VLMProviderType.ANTHROPIC


# --- Edge Case Tests ---


def test_config_empty_dict():
    """Empty config dict should be valid."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    data = VLMProviderCreate(
        provider_type=VLMProviderType.ANTHROPIC,
        name='Test',
        api_key='sk-ant-api03-xxxxxxxxxxxx',
        config={},
    )

    assert data.config == {}


def test_config_nested_dict():
    """Config can have nested dictionaries."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    nested_config = {
        'aws_region': 'us-east-1',
        'credentials': {
            'access_key': 'xxx',
            'secret_key': 'yyy',
        },
        'retry_config': {
            'max_retries': 3,
            'backoff_factor': 2.0,
        },
    }

    data = VLMProviderCreate(
        provider_type=VLMProviderType.AWS_BEDROCK,
        name='Test Bedrock',
        api_key='bedrock-key-1234567890',
        config=nested_config,
    )

    assert data.config == nested_config


def test_boundary_values():
    """Test boundary values for numeric fields."""
    from app.api.v1.vlm_providers import VLMProviderCreate
    from app.models.vlm_provider import VLMProviderType

    # Minimum values
    data_min = VLMProviderCreate(
        provider_type=VLMProviderType.ANTHROPIC,
        name='M',  # 1 character (minimum)
        api_key='1234567890',  # 10 characters (minimum)
        max_tokens=100,  # Minimum
        temperature=0.0,  # Minimum
        monthly_budget=0.0,  # Minimum
    )

    assert data_min.name == 'M'
    assert len(data_min.api_key) == 10
    assert data_min.max_tokens == 100
    assert data_min.temperature == 0.0
    assert data_min.monthly_budget == 0.0

    # Maximum values
    data_max = VLMProviderCreate(
        provider_type=VLMProviderType.ANTHROPIC,
        name='A' * 100,  # 100 characters (maximum)
        api_key='sk-ant-api03-xxxxxxxxxxxx',
        max_tokens=32000,  # Maximum
        temperature=2.0,  # Maximum
        monthly_budget=999999.99,  # Very large
    )

    assert len(data_max.name) == 100
    assert data_max.max_tokens == 32000
    assert data_max.temperature == 2.0


# --- Model Method Tests ---


def test_record_usage_updates_counters():
    """
    record_usage() should increment token counters and costs.

    Tests the Decimal-safe cost arithmetic in the VLMProvider model.
    """
    from app.models.vlm_provider import VLMProvider

    provider = VLMProvider()
    provider.total_requests = 0
    provider.total_input_tokens = 0
    provider.total_output_tokens = 0
    provider.total_spent = Decimal("0")
    provider.current_month_spent = Decimal("0")

    # Record first usage
    provider.record_usage(
        input_tokens=1000,
        output_tokens=500,
        cost=0.15,  # Float input
    )

    assert provider.total_requests == 1
    assert provider.total_input_tokens == 1000
    assert provider.total_output_tokens == 500
    assert provider.total_spent == Decimal("0.15")
    assert provider.current_month_spent == Decimal("0.15")

    # Record second usage
    provider.record_usage(
        input_tokens=2000,
        output_tokens=1000,
        cost=Decimal("0.30"),  # Decimal input
    )

    assert provider.total_requests == 2
    assert provider.total_input_tokens == 3000
    assert provider.total_output_tokens == 1500
    assert provider.total_spent == Decimal("0.45")
    assert provider.current_month_spent == Decimal("0.45")


def test_check_budget_within_limit():
    """check_budget() should return True when within budget."""
    from app.models.vlm_provider import VLMProvider

    provider = VLMProvider()
    provider.monthly_budget = Decimal("100.00")
    provider.current_month_spent = Decimal("50.00")

    assert provider.check_budget() is True


def test_check_budget_exceeded():
    """check_budget() should return False when budget exceeded."""
    from app.models.vlm_provider import VLMProvider

    provider = VLMProvider()
    provider.monthly_budget = Decimal("100.00")
    provider.current_month_spent = Decimal("100.00")  # Equal to budget

    # Should return False when equal or exceeded
    assert provider.check_budget() is False


def test_check_budget_no_limit():
    """check_budget() should return True when no budget set."""
    from app.models.vlm_provider import VLMProvider

    provider = VLMProvider()
    provider.monthly_budget = None
    provider.current_month_spent = Decimal("999999.99")

    # No budget limit means always within budget
    assert provider.check_budget() is True


def test_reset_monthly_spent():
    """reset_monthly_spent() should reset the counter to zero."""
    from app.models.vlm_provider import VLMProvider

    provider = VLMProvider()
    provider.current_month_spent = Decimal("123.45")

    provider.reset_monthly_spent()

    assert provider.current_month_spent == Decimal("0")


def test_provider_display_name():
    """provider_display_name property should return friendly name."""
    from app.models.vlm_provider import VLMProvider, VLMProviderType

    test_cases = [
        (VLMProviderType.ANTHROPIC, "Anthropic Claude"),
        (VLMProviderType.OPENAI, "OpenAI GPT-4"),
        (VLMProviderType.GOOGLE, "Google Gemini"),
        (VLMProviderType.AZURE_OPENAI, "Azure OpenAI"),
        (VLMProviderType.AWS_BEDROCK, "AWS Bedrock"),
        (VLMProviderType.CUSTOM, "Custom Provider"),
    ]

    for provider_type, expected_name in test_cases:
        provider = VLMProvider()
        provider.provider_type = provider_type
        assert provider.provider_display_name == expected_name
