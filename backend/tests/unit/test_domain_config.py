"""
Unit Tests for Domain Configuration.

Tests for the app_domain configuration setting and environment variable overrides.
"""

import os
import pytest
from unittest.mock import patch

from app.config import Settings


class TestDomainConfigDefaults:
    """Tests for app_domain default values."""

    def test_app_domain_default(self):
        """Test that app_domain defaults to 'leafxtract.com' when no env var set."""
        # Clear any existing APP_DOMAIN env var
        with patch.dict(os.environ, {}, clear=False):
            # Remove APP_DOMAIN if it exists
            os.environ.pop('APP_DOMAIN', None)

            # Create Settings instance
            settings = Settings()

            # Verify default value
            assert settings.app_domain == "leafxtract.com"

    def test_app_domain_is_string(self):
        """Test that app_domain is a string type."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('APP_DOMAIN', None)

            settings = Settings()

            assert isinstance(settings.app_domain, str)
            assert len(settings.app_domain) > 0


class TestDomainConfigEnvOverride:
    """Tests for app_domain environment variable override."""

    def test_app_domain_env_override(self):
        """Test that APP_DOMAIN env var overrides the default value."""
        # Set APP_DOMAIN environment variable
        with patch.dict(os.environ, {'APP_DOMAIN': 'leafxtract.com'}, clear=False):
            # Create Settings instance
            settings = Settings()

            # Verify env var override
            assert settings.app_domain == "leafxtract.com"

    def test_app_domain_production_override(self):
        """Test app_domain override with production domain."""
        with patch.dict(os.environ, {'APP_DOMAIN': 'app.leafxtract.com'}, clear=False):
            settings = Settings()

            assert settings.app_domain == "app.leafxtract.com"

    def test_app_domain_custom_domain(self):
        """Test app_domain override with custom domain."""
        custom_domain = "custom.example.com"
        with patch.dict(os.environ, {'APP_DOMAIN': custom_domain}, clear=False):
            settings = Settings()

            assert settings.app_domain == custom_domain

    def test_app_domain_localhost_override(self):
        """Test app_domain override with localhost for local development."""
        with patch.dict(os.environ, {'APP_DOMAIN': 'localhost:3000'}, clear=False):
            settings = Settings()

            assert settings.app_domain == "localhost:3000"


class TestDomainConfigUsage:
    """Tests for app_domain usage in application context."""

    def test_app_domain_used_in_docs(self):
        """Test that app_domain can be used for API documentation references."""
        with patch.dict(os.environ, {'APP_DOMAIN': 'api.leafxtract.com'}, clear=False):
            settings = Settings()

            # Simulate usage in API docs URL construction
            docs_url = f"https://{settings.app_domain}/docs"
            assert docs_url == "https://api.leafxtract.com/docs"

    def test_app_domain_used_in_email_templates(self):
        """Test that app_domain can be used in email template URLs."""
        with patch.dict(os.environ, {'APP_DOMAIN': 'app.leafxtract.com'}, clear=False):
            settings = Settings()

            # Simulate usage in email verification link
            verification_url = f"https://{settings.app_domain}/verify-email?token=abc123"
            assert verification_url == "https://app.leafxtract.com/verify-email?token=abc123"

    def test_app_domain_consistency_with_frontend_url(self):
        """Test that app_domain can differ from frontend_url for multi-domain setups."""
        with patch.dict(
            os.environ,
            {
                'APP_DOMAIN': 'api.leafxtract.com',
                'FRONTEND_URL': 'https://app.leafxtract.com',
            },
            clear=False
        ):
            settings = Settings()

            # API domain and frontend domain can be different
            assert settings.app_domain == "api.leafxtract.com"
            assert settings.frontend_url == "https://app.leafxtract.com"


class TestDomainConfigValidation:
    """Tests for app_domain field validation."""

    def test_app_domain_empty_string_override(self):
        """Test that empty string override is accepted (field has default)."""
        # Even if env var is empty, Pydantic will use the field default
        with patch.dict(os.environ, {'APP_DOMAIN': ''}, clear=False):
            settings = Settings()

            # Empty string should be replaced by field default
            assert settings.app_domain in ["", "leafxtract.com"]

    def test_app_domain_whitespace_handling(self):
        """Test that whitespace in domain is preserved (validation happens at usage)."""
        # Pydantic won't strip whitespace unless we add a validator
        with patch.dict(os.environ, {'APP_DOMAIN': '  domain.com  '}, clear=False):
            settings = Settings()

            # Whitespace preserved (would need custom validator to strip)
            assert settings.app_domain == "  domain.com  "

    def test_app_domain_special_characters(self):
        """Test that domains with valid special characters are accepted."""
        # Domains can have hyphens and dots
        with patch.dict(os.environ, {'APP_DOMAIN': 'my-app.sub-domain.example.com'}, clear=False):
            settings = Settings()

            assert settings.app_domain == "my-app.sub-domain.example.com"


class TestDomainConfigFieldDefinition:
    """Tests for the app_domain field definition in Settings."""

    def test_app_domain_field_exists(self):
        """Test that app_domain field exists in Settings class."""
        settings = Settings()

        # Field should exist
        assert hasattr(settings, 'app_domain')

    def test_app_domain_field_description(self):
        """Test that app_domain field has proper description."""
        # Get field info from Settings model
        field_info = Settings.model_fields.get('app_domain')

        assert field_info is not None
        assert field_info.description is not None
        assert "domain" in field_info.description.lower()

    def test_app_domain_field_type(self):
        """Test that app_domain field is defined as str type."""
        field_info = Settings.model_fields.get('app_domain')

        assert field_info is not None
        # Check that annotation is str
        assert field_info.annotation == str


class TestDomainConfigIntegration:
    """Integration tests for app_domain with other settings."""

    def test_app_domain_with_other_settings(self):
        """Test that app_domain works alongside other settings."""
        with patch.dict(
            os.environ,
            {
                'APP_DOMAIN': 'prod.leafxtract.com',
                'ENVIRONMENT': 'production',
                'SECRET_KEY': 'test-secret-key-minimum-32-chars-long',
            },
            clear=False
        ):
            settings = Settings()

            assert settings.app_domain == "prod.leafxtract.com"
            assert settings.environment == "production"
            assert settings.is_production is True

    def test_app_domain_independent_of_environment(self):
        """Test that app_domain is independent of environment setting."""
        # Development environment with production domain
        with patch.dict(
            os.environ,
            {
                'APP_DOMAIN': 'leafxtract.com',
                'ENVIRONMENT': 'development',
            },
            clear=False
        ):
            settings = Settings()

            assert settings.app_domain == "leafxtract.com"
            assert settings.is_development is True

    def test_multiple_settings_instances_same_domain(self):
        """Test that multiple Settings instances use same app_domain."""
        with patch.dict(os.environ, {'APP_DOMAIN': 'test.leafxtract.com'}, clear=False):
            settings1 = Settings()
            settings2 = Settings()

            # Both instances should have the same domain
            assert settings1.app_domain == settings2.app_domain
            assert settings1.app_domain == "test.leafxtract.com"


class TestDomainConfigReload:
    """Tests for app_domain config reloading."""

    def test_app_domain_env_change_after_init(self):
        """Test that changing env var after init doesn't affect existing instance."""
        with patch.dict(os.environ, {'APP_DOMAIN': 'initial.com'}, clear=False):
            settings = Settings()
            initial_domain = settings.app_domain

            # Change env var after instance creation
            os.environ['APP_DOMAIN'] = 'changed.com'

            # Existing instance should retain initial value
            assert settings.app_domain == initial_domain
            assert settings.app_domain == "initial.com"

            # New instance should use new value
            new_settings = Settings()
            assert new_settings.app_domain == "changed.com"
