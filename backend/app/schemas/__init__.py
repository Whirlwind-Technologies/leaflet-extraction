"""
Schemas Package.

This package contains all Pydantic schemas for request/response validation.

Example Usage:
    from app.schemas import UserCreate, LeafletResponse, ProductUpdate
    
    # Validate user creation
    user = UserCreate(email="user@example.com", password="secure123")
    
    # Product update
    update = ProductUpdate(regular_price=2.99)
"""

from app.schemas.common import (
    BaseSchema,
    BoundingBox,
    ErrorDetail,
    ErrorResponse,
    FieldConfidence,
    HealthResponse,
    ImageData,
    PaginatedResponse,
    PaginationParams,
    SuccessResponse,
)
from app.schemas.user import (
    APIKeyCreate,
    APIKeyCreated,
    APIKeyResponse,
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    Token,
    TokenPayload,
    UserCreate,
    UserInDB,
    UserResponse,
    UserUpdate,
)
from app.schemas.leaflet import (
    LeafletCreate,
    LeafletDetail,
    LeafletListParams,
    LeafletPageResponse,
    LeafletProcessingStatus,
    LeafletQualityMetrics,
    LeafletResponse,
    LeafletUpdate,
    LeafletUploadResponse,
)
from app.schemas.product import (
    ProductBatchReviewCreate,
    ProductBatchReviewResponse,
    ProductCreate,
    ProductExportParams,
    ProductListParams,
    ProductListResponse,
    ProductResponse,
    ProductReviewCreate,
    ProductReviewResponse,
    ProductUpdate,
    VLMExtractionResult,
)

__all__ = [
    # Common
    "BaseSchema",
    "BoundingBox",
    "ErrorDetail",
    "ErrorResponse",
    "FieldConfidence",
    "HealthResponse",
    "ImageData",
    "PaginatedResponse",
    "PaginationParams",
    "SuccessResponse",
    # User
    "APIKeyCreate",
    "APIKeyCreated",
    "APIKeyResponse",
    "ChangePasswordRequest",
    "LoginRequest",
    "PasswordResetConfirm",
    "PasswordResetRequest",
    "RefreshTokenRequest",
    "Token",
    "TokenPayload",
    "UserCreate",
    "UserInDB",
    "UserResponse",
    "UserUpdate",
    # Leaflet
    "LeafletCreate",
    "LeafletDetail",
    "LeafletListParams",
    "LeafletPageResponse",
    "LeafletProcessingStatus",
    "LeafletQualityMetrics",
    "LeafletResponse",
    "LeafletUpdate",
    "LeafletUploadResponse",
    # Product
    "ProductBatchReviewCreate",
    "ProductBatchReviewResponse",
    "ProductCreate",
    "ProductExportParams",
    "ProductListParams",
    "ProductListResponse",
    "ProductResponse",
    "ProductReviewCreate",
    "ProductReviewResponse",
    "ProductUpdate",
    "VLMExtractionResult",
]