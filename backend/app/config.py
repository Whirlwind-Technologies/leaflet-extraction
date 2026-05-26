"""
Configuration Module for Leaflet Data Extraction Platform.

This module provides centralized configuration management using Pydantic Settings.
It loads configuration from environment variables with validation and type safety.

NOTE: VLM API keys and provider settings are managed via the database, not environment
variables. See Platform VLM Providers (admin) and Organization VLM Providers (user settings).

Example Usage:
    from app.config import settings

    # Access configuration values
    db_url = settings.database_url

    # Check environment
    if settings.is_development:
        print("Running in development mode")
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

from pydantic import (
    AnyHttpUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings can be overridden via environment variables.
    Nested settings use underscore separation (e.g., POSTGRES_HOST).
    
    Attributes:
        app_name: Name of the application
        app_version: Current application version
        environment: Deployment environment (development, staging, production)
        debug: Enable debug mode
        
    Example:
        >>> settings = Settings()
        >>> print(settings.app_name)
        'leaflet-extraction-platform'
    """
    
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    app_name: str = Field(
        default="leaflet-extraction-platform",
        description="Application name used in logs and API responses"
    )
    app_version: str = Field(
        default="1.0.0",
        description="Application version"
    )
    environment: str = Field(
        default="development",
        description="Deployment environment"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # -------------------------------------------------------------------------
    # Server Settings
    # -------------------------------------------------------------------------
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=4, description="Number of workers")
    reload: bool = Field(default=False, description="Enable auto-reload")
    
    # -------------------------------------------------------------------------
    # Security Settings
    # -------------------------------------------------------------------------
    secret_key: str = Field(
        default="",
        description="Secret key for JWT encoding (REQUIRED - generate with: openssl rand -hex 32)"
    )

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        """Validate security-critical settings."""
        if self.is_production:
            if not self.secret_key or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be set and at least 32 characters in production. "
                    "Generate one with: openssl rand -hex 32"
                )
            if self.secret_key == "change-me-in-production-use-openssl-rand-hex-32":
                raise ValueError(
                    "SECRET_KEY must be changed from default value in production"
                )
            # VLM providers are now configured via database (platform or organization level)
            # No environment variable API keys required
        return self
    algorithm: str = Field(
        default="HS256",
        description="JWT algorithm"
    )
    access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiration time in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiration time in days"
    )
    api_key_header: str = Field(
        default="X-API-Key",
        description="Header name for API key authentication"
    )
    
    # -------------------------------------------------------------------------
    # CORS Settings
    # -------------------------------------------------------------------------
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS requests"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    # -------------------------------------------------------------------------
    # Database Settings
    # -------------------------------------------------------------------------
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_user: str = Field(default="leaflet_user", description="PostgreSQL user")
    postgres_password: str = Field(
        default="password",
        description="PostgreSQL password"
    )
    postgres_db: str = Field(
        default="leaflet_extraction",
        description="PostgreSQL database name"
    )
    db_pool_size: int = Field(default=20, description="Database connection pool size")
    db_max_overflow: int = Field(default=10, description="Max overflow connections")
    db_pool_timeout: int = Field(default=30, description="Connection pool timeout")
    
    @property
    def database_url(self) -> str:
        """Construct async database URL for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def database_url_sync(self) -> str:
        """Construct sync database URL for Alembic migrations."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    # -------------------------------------------------------------------------
    # Redis Settings
    # -------------------------------------------------------------------------
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_db: int = Field(default=0, description="Redis database number")
    cache_ttl_default: int = Field(
        default=3600,
        description="Default cache TTL in seconds"
    )
    cache_ttl_leaflet: int = Field(
        default=86400,
        description="Leaflet cache TTL in seconds"
    )
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    # -------------------------------------------------------------------------
    # Celery Settings
    # -------------------------------------------------------------------------
    celery_broker_url: Optional[str] = Field(
        default=None,
        description="Celery broker URL"
    )
    celery_result_backend: Optional[str] = Field(
        default=None,
        description="Celery result backend URL"
    )
    celery_task_always_eager: bool = Field(
        default=False,
        description="Run Celery tasks synchronously (for testing)"
    )
    celery_worker_concurrency: int = Field(
        default=4,
        description="Celery worker concurrency"
    )
    
    @model_validator(mode="after")
    def set_celery_defaults(self) -> "Settings":
        """Set Celery URLs based on Redis if not explicitly provided."""
        if self.celery_broker_url is None:
            base = f"redis://{self.redis_host}:{self.redis_port}"
            if self.redis_password:
                base = f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}"
            self.celery_broker_url = f"{base}/1"
        if self.celery_result_backend is None:
            base = f"redis://{self.redis_host}:{self.redis_port}"
            if self.redis_password:
                base = f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}"
            self.celery_result_backend = f"{base}/2"
        return self
    
    # -------------------------------------------------------------------------
    # VLM Provider Settings (configured via database, not environment)
    # -------------------------------------------------------------------------
    # NOTE: VLM API keys and model settings are now managed through:
    # - Platform VLM Providers: Admin dashboard (admin/platform-providers)
    # - Organization VLM Providers: User settings (settings?tab=ai-providers)
    #
    # The following are operational defaults only (not API credentials):
    vlm_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for VLM API calls"
    )
    vlm_request_timeout: int = Field(
        default=120,
        description="VLM API request timeout in seconds"
    )
    vlm_concurrent_requests: int = Field(
        default=6,
        description="Maximum concurrent VLM requests per extraction"
    )
    
    # -------------------------------------------------------------------------
    # Storage Settings
    # -------------------------------------------------------------------------
    storage_mode: str = Field(
        default="local",
        description="Storage mode: 's3', 'minio', or 'local'"
    )
    aws_access_key_id: Optional[str] = Field(
        default=None,
        description="AWS access key ID"
    )
    aws_secret_access_key: Optional[str] = Field(
        default=None,
        description="AWS secret access key"
    )
    aws_region: str = Field(default="us-east-1", description="AWS region")
    s3_bucket_name: str = Field(
        default="leaflet-extraction-storage",
        description="S3 bucket name"
    )
    minio_endpoint: str = Field(
        default="localhost:9000",
        description="MinIO endpoint"
    )
    minio_access_key: str = Field(default="minioadmin", description="MinIO access key")
    minio_secret_key: str = Field(default="minioadmin", description="MinIO secret key")
    minio_secure: bool = Field(default=False, description="Use HTTPS for MinIO")
    local_storage_path: str = Field(
        default="./storage",
        description="Local storage path"
    )
    
    # -------------------------------------------------------------------------
    # File Processing Settings
    # -------------------------------------------------------------------------
    max_file_size: int = Field(
        default=104857600,
        description="Maximum file size in bytes (100MB)"
    )
    allowed_extensions: List[str] = Field(
        default=[".pdf"],
        description="Allowed file extensions"
    )
    pdf_dpi: int = Field(default=300, description="PDF rendering DPI")
    pdf_output_format: str = Field(
        default="PNG",
        description="PDF output image format"
    )
    pdf_max_pages: int = Field(
        default=100,
        description="Maximum pages per PDF"
    )
    
    # -------------------------------------------------------------------------
    # Default Region Settings (Adriatic/European)
    # -------------------------------------------------------------------------
    default_currency: str = Field(
        default="RSD",
        description="Default currency for price extraction (RSD for Serbia)"
    )
    default_language: str = Field(
        default="auto",
        description="Default language (auto, en, sl, hr, sr, etc.)"
    )
    default_country: str = Field(
        default="RS",
        description="Default country code (RS=Serbia, SI=Slovenia, HR=Croatia)"
    )
    supported_currencies: List[str] = Field(
        default=["EUR", "HRK", "RSD", "BAM", "MKD", "ALL"],
        description="Supported currencies in the Adriatic region"
    )
    supported_languages: List[str] = Field(
        default=["sl", "hr", "sr", "bs", "mk", "sq", "en", "de", "it"],
        description="Supported languages (Slovenian, Croatian, Serbian, Bosnian, Macedonian, Albanian, English, German, Italian)"
    )

    @field_validator("supported_currencies", "supported_languages", mode="before")
    @classmethod
    def parse_list_fields(cls, v: Any) -> List[str]:
        """Parse list from comma-separated string or list."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v: Any) -> List[str]:
        """Parse extensions from comma-separated string or list."""
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",") if ext.strip()]
        return v
    
    # -------------------------------------------------------------------------
    # Image Processing Settings
    # -------------------------------------------------------------------------
    image_quality_high: int = Field(default=95, description="High quality setting")
    image_quality_medium: int = Field(default=85, description="Medium quality setting")
    image_quality_low: int = Field(default=60, description="Low quality setting")
    base64_size_threshold: int = Field(
        default=102400,
        description="Size threshold for base64 storage (100KB)"
    )
    
    # -------------------------------------------------------------------------
    # Processing Queue Settings
    # -------------------------------------------------------------------------
    pdf_batch_size: int = Field(default=6, description="PDF processing batch size")
    vlm_batch_size: int = Field(default=6, description="VLM extraction batch size")
    image_batch_size: int = Field(default=10, description="Image processing batch size")
    pdf_processing_timeout: int = Field(
        default=300,
        description="PDF processing timeout in seconds"
    )
    vlm_extraction_timeout: int = Field(
        default=120,
        description="VLM extraction timeout in seconds"
    )
    image_extraction_timeout: int = Field(
        default=60,
        description="Image extraction timeout in seconds"
    )
    
    # -------------------------------------------------------------------------
    # Validation Settings
    # -------------------------------------------------------------------------
    confidence_high: float = Field(
        default=0.90,
        description="High confidence threshold"
    )
    confidence_medium: float = Field(
        default=0.75,
        description="Medium confidence threshold"
    )
    confidence_low: float = Field(
        default=0.50,
        description="Low confidence threshold"
    )
    auto_approval_threshold: float = Field(
        default=0.90,
        description="Auto-approval confidence threshold"
    )
    max_price: float = Field(
        default=10000.0,
        description="Maximum valid price"
    )
    min_price: float = Field(
        default=0.01,
        description="Minimum valid price"
    )
    
    # -------------------------------------------------------------------------
    # WebSocket Settings
    # -------------------------------------------------------------------------
    websocket_ping_interval: int = Field(
        default=30,
        description="WebSocket ping interval in seconds",
    )
    websocket_max_connections_per_user: int = Field(
        default=10,
        description="Maximum WebSocket connections per user",
    )

    # -------------------------------------------------------------------------
    # Rate Limiting Settings
    # -------------------------------------------------------------------------
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    rate_limit_requests: int = Field(
        default=100,
        description="Requests per window"
    )
    rate_limit_window: int = Field(
        default=60,
        description="Rate limit window in seconds"
    )
    
    # -------------------------------------------------------------------------
    # Monitoring Settings
    # -------------------------------------------------------------------------
    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking"
    )
    metrics_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics"
    )
    metrics_port: int = Field(default=9090, description="Metrics port")
    log_format: str = Field(
        default="text",
        description="Log format: 'json' or 'text'"
    )
    log_file: Optional[str] = Field(
        default=None,
        description="Log file path"
    )
    
    # -------------------------------------------------------------------------
    # Feature Flags
    # -------------------------------------------------------------------------
    feature_async_processing: bool = Field(
        default=True,
        description="Enable async processing"
    )
    feature_auto_approval: bool = Field(
        default=False,
        description="Enable auto-approval"
    )
    feature_feedback_loop: bool = Field(
        default=True,
        description="Enable feedback loop"
    )
    feature_analytics: bool = Field(
        default=True,
        description="Enable analytics"
    )

    # -------------------------------------------------------------------------
    # Webhook Settings
    # -------------------------------------------------------------------------
    webhook_allow_private_ips: bool = Field(
        default=False,
        description=(
            "Allow webhook URLs pointing to private/internal IP addresses. "
            "Should only be True in development environments for local testing."
        ),
    )

    # -------------------------------------------------------------------------
    # Email Settings
    # -------------------------------------------------------------------------
    smtp_host: str = Field(
        default="localhost",
        description="SMTP server host"
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port (587 for TLS, 465 for SSL)"
    )
    smtp_user: Optional[str] = Field(
        default=None,
        description="SMTP authentication username"
    )
    smtp_password: Optional[str] = Field(
        default=None,
        description="SMTP authentication password"
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use TLS for SMTP connection"
    )
    smtp_from_email: str = Field(
        default="info@leafxtract.com",
        description="Default sender email address"
    )
    smtp_from_name: str = Field(
        default="Leaflet Extraction Platform",
        description="Default sender name"
    )
    smtp_enabled: bool = Field(
        default=False,
        description="Enable email sending (disable for local dev)"
    )
    frontend_url: str = Field(
        default="http://localhost:3000",
        description="Frontend URL for email links"
    )
    app_domain: str = Field(
        default="leafxtract.com",
        description="Application domain used in API documentation and public-facing references"
    )

    # -------------------------------------------------------------------------
    # Support & Contact Settings
    # -------------------------------------------------------------------------
    support_email: str = Field(
        default="info@leafxtract.com",
        description=(
            "Support/contact email address for notifications and user-facing "
            "references. Used as the primary recipient for contact form "
            "submissions and registration alerts."
        ),
    )
    contact_email: Optional[str] = Field(
        default=None,
        description=(
            "Override recipient email for contact form submissions. "
            "If not set, falls back to support_email."
        ),
    )
    contact_rate_limit_per_email: int = Field(
        default=3,
        description="Max contact submissions per email address per hour",
    )
    contact_rate_limit_per_ip: int = Field(
        default=5,
        description="Max contact submissions per IP address per hour",
    )
    contact_rate_limit_global: int = Field(
        default=50,
        description="Max total contact submissions per hour (all senders)",
    )
    contact_min_submit_time: int = Field(
        default=3,
        description=(
            "Minimum seconds between form render and submission. "
            "Submissions faster than this are silently rejected as bot activity."
        ),
    )
    recaptcha_secret_key: Optional[str] = Field(
        default=None,
        description=(
            "Google reCAPTCHA v3 secret key. If not set, reCAPTCHA "
            "verification is skipped entirely."
        ),
    )

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment.lower() == "testing"
    
    @property
    def storage_base_path(self) -> Path:
        """Get the base storage path."""
        path = Path(self.local_storage_path)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses LRU cache to ensure settings are loaded only once.
    Call get_settings.cache_clear() to reload settings.
    
    Returns:
        Settings: Application settings instance
        
    Example:
        >>> settings = get_settings()
        >>> print(settings.app_name)
        'leaflet-extraction-platform'
    """
    return Settings()


# Global settings instance for convenience
settings = get_settings()