"""
Custom Exception Classes for the Leaflet Data Extraction Platform.

This module defines a hierarchy of custom exceptions used throughout
the application for consistent error handling and API responses.

Example Usage:
    from app.utils.exceptions import NotFoundError, ValidationException
    
    # Raise a not found error
    raise NotFoundError("Leaflet", "LEAF_2025_001234")
    
    # Raise a validation error
    raise ValidationException([
        {"field": "email", "message": "Invalid email format"}
    ])
"""

from typing import Any, Dict, List, Optional


class APIException(Exception):
    """
    Base exception class for all API exceptions.
    
    All custom exceptions should inherit from this class to ensure
    consistent error handling throughout the application.
    
    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code
        status_code: HTTP status code
        details: Additional error details
        
    Example:
        >>> raise APIException(
        ...     message="Something went wrong",
        ...     error_code="GENERAL_ERROR",
        ...     status_code=500
        ... )
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "API_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize API exception.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            status_code: HTTP status code
            details: Additional error details
        """
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary representation.
        
        Returns:
            Dict containing error information
        """
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationException(APIException):
    """
    Exception raised for validation errors.
    
    Used when request data fails validation rules.
    
    Attributes:
        errors: List of validation errors
        
    Example:
        >>> raise ValidationException([
        ...     {"field": "email", "message": "Invalid email format"},
        ...     {"field": "password", "message": "Password too short"}
        ... ])
    """
    
    def __init__(
        self,
        errors: List[Dict[str, Any]],
        message: str = "Validation failed",
    ) -> None:
        """
        Initialize validation exception.
        
        Args:
            errors: List of validation error dictionaries
            message: Overall error message
        """
        self.errors = errors
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details={"errors": errors},
        )


class NotFoundError(APIException):
    """
    Exception raised when a resource is not found.
    
    Example:
        >>> raise NotFoundError("Leaflet", "LEAF_2025_001234")
        # Message: "Leaflet not found: LEAF_2025_001234"
    """
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """
        Initialize not found exception.
        
        Args:
            resource_type: Type of resource (e.g., "Leaflet", "Product")
            resource_id: ID of the resource
            message: Custom message (optional)
        """
        if message is None:
            if resource_id:
                message = f"{resource_type} not found: {resource_id}"
            else:
                message = f"{resource_type} not found"
        
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class AuthenticationError(APIException):
    """
    Exception raised for authentication failures.
    
    Example:
        >>> raise AuthenticationError("Invalid or expired token")
    """
    
    def __init__(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize authentication exception.
        
        Args:
            message: Error message
            details: Additional details
        """
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details,
        )


class AuthorizationError(APIException):
    """
    Exception raised for authorization failures.
    
    Example:
        >>> raise AuthorizationError("Insufficient permissions to access this resource")
    """
    
    def __init__(
        self,
        message: str = "Access denied",
        required_permission: Optional[str] = None,
    ) -> None:
        """
        Initialize authorization exception.
        
        Args:
            message: Error message
            required_permission: The permission that was required
        """
        details = {}
        if required_permission:
            details["required_permission"] = required_permission
        
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
            details=details,
        )


class RateLimitError(APIException):
    """
    Exception raised when rate limit is exceeded.
    
    Example:
        >>> raise RateLimitError(retry_after=60)
    """
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
    ) -> None:
        """
        Initialize rate limit exception.
        
        Args:
            message: Error message
            retry_after: Seconds until rate limit resets
        """
        self.retry_after = retry_after
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details={"retry_after": retry_after},
        )


class ProcessingError(APIException):
    """
    Exception raised for processing failures.
    
    Used when PDF processing, VLM extraction, or image
    processing fails.
    
    Example:
        >>> raise ProcessingError(
        ...     "PDF processing failed",
        ...     stage="pdf_conversion",
        ...     leaflet_id="LEAF_2025_001234"
        ... )
    """
    
    def __init__(
        self,
        message: str,
        stage: Optional[str] = None,
        leaflet_id: Optional[str] = None,
        page_number: Optional[int] = None,
    ) -> None:
        """
        Initialize processing exception.
        
        Args:
            message: Error message
            stage: Processing stage where error occurred
            leaflet_id: ID of the leaflet being processed
            page_number: Page number where error occurred
        """
        details = {}
        if stage:
            details["stage"] = stage
        if leaflet_id:
            details["leaflet_id"] = leaflet_id
        if page_number:
            details["page_number"] = page_number
        
        super().__init__(
            message=message,
            error_code="PROCESSING_ERROR",
            status_code=500,
            details=details,
        )


class StorageError(APIException):
    """
    Exception raised for storage operation failures.
    
    Example:
        >>> raise StorageError("Failed to upload file to S3", operation="upload")
    """
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        path: Optional[str] = None,
    ) -> None:
        """
        Initialize storage exception.
        
        Args:
            message: Error message
            operation: Storage operation that failed
            path: File path involved
        """
        details = {}
        if operation:
            details["operation"] = operation
        if path:
            details["path"] = path
        
        super().__init__(
            message=message,
            error_code="STORAGE_ERROR",
            status_code=500,
            details=details,
        )


class ExternalAPIError(APIException):
    """
    Exception raised for external API failures.
    
    Used when calls to external services (Claude API, etc.) fail.
    
    Example:
        >>> raise ExternalAPIError(
        ...     "Claude API request failed",
        ...     service="anthropic",
        ...     original_error="Rate limit exceeded"
        ... )
    """
    
    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        original_error: Optional[str] = None,
    ) -> None:
        """
        Initialize external API exception.
        
        Args:
            message: Error message
            service: Name of the external service
            original_error: Original error message from service
        """
        details = {}
        if service:
            details["service"] = service
        if original_error:
            details["original_error"] = original_error
        
        super().__init__(
            message=message,
            error_code="EXTERNAL_API_ERROR",
            status_code=502,
            details=details,
        )


class ConfigurationError(APIException):
    """
    Exception raised for configuration errors.
    
    Example:
        >>> raise ConfigurationError("Missing required API key: ANTHROPIC_API_KEY")
    """
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
    ) -> None:
        """
        Initialize configuration exception.
        
        Args:
            message: Error message
            config_key: Configuration key that is invalid/missing
        """
        details = {}
        if config_key:
            details["config_key"] = config_key
        
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=500,
            details=details,
        )


class DuplicateError(APIException):
    """
    Exception raised when attempting to create a duplicate resource.

    Example:
        >>> raise DuplicateError("User", "email", "user@example.com")
    """

    def __init__(
        self,
        resource_type: str,
        field: str,
        value: str,
    ) -> None:
        """
        Initialize duplicate exception.

        Args:
            resource_type: Type of resource
            field: Field that has duplicate value
            value: The duplicate value
        """
        super().__init__(
            message=f"{resource_type} with {field}='{value}' already exists",
            error_code="DUPLICATE_ERROR",
            status_code=409,
            details={
                "resource_type": resource_type,
                "field": field,
                "value": value,
            },
        )


class PlatformLimitExceededError(APIException):
    """
    Exception raised when an organization has exhausted its free platform
    AI provider leaflet extractions.

    This error is raised at extraction time (inside ``extract_products_task``)
    when the organization:
      1. Has no active VLM provider of its own, AND
      2. Has reached or exceeded its ``platform_leaflet_limit``.

    The error carries structured ``details`` that the frontend can use to
    render a helpful message with a CTA to add a provider.

    HTTP Status: 403 (Forbidden) -- the request is authenticated but the
    organization lacks the entitlement to perform this action.

    Attributes:
        limit: The configured platform limit for this organization.
        used: How many platform extractions have been consumed.

    Example:
        >>> raise PlatformLimitExceededError(limit=10, used=10)
        # Produces:
        # {
        #     "error": {
        #         "code": "PLATFORM_LIMIT_REACHED",
        #         "message": "Your organization has used all 10 free ...",
        #         "details": {
        #             "limit": 10,
        #             "used": 10,
        #             "remaining": 0,
        #             "action_url": "/settings",
        #             "action_text": "Add AI Provider"
        #         }
        #     }
        # }
    """

    def __init__(
        self,
        limit: int,
        used: int,
        message: Optional[str] = None,
    ) -> None:
        """
        Initialize platform limit exceeded exception.

        Args:
            limit: The configured platform leaflet limit.
            used: Number of platform extractions consumed.
            message: Optional custom message. If not provided, a default
                     message is generated from the limit value.
        """
        self.limit = limit
        self.used = used

        if message is None:
            message = (
                f"Your organization has used all {limit} free leaflet extractions "
                f"with the platform AI provider. Please add your own AI provider "
                f"in Settings to continue."
            )

        super().__init__(
            message=message,
            error_code="PLATFORM_LIMIT_REACHED",
            status_code=403,
            details={
                "limit": limit,
                "used": used,
                "remaining": 0,
                "action_url": "/settings?tab=ai-providers",
                "action_text": "Add AI Provider",
            },
        )