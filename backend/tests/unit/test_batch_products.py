"""
Unit tests for the Product Batch Fetch feature.

Tests the new POST /api/v1/products/batch endpoint and supporting
functionality for cache-optimized navigation.
"""

import pytest
from uuid import uuid4
from pydantic import ValidationError
from decimal import Decimal

from app.schemas.product import ProductBatchFetchRequest


class TestProductBatchFetchRequest:
    """Test ProductBatchFetchRequest schema validation."""

    def test_valid_request_with_5_ids(self):
        """Valid request with 5 product IDs."""
        ids = [uuid4() for _ in range(5)]
        req = ProductBatchFetchRequest(product_ids=ids)
        assert len(req.product_ids) == 5
        assert all(isinstance(id, type(uuid4())) for id in req.product_ids)

    def test_valid_request_with_1_id(self):
        """Valid request with minimum 1 product ID."""
        ids = [uuid4()]
        req = ProductBatchFetchRequest(product_ids=ids)
        assert len(req.product_ids) == 1

    def test_empty_list_rejected(self):
        """Empty product_ids list is rejected (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            ProductBatchFetchRequest(product_ids=[])

        errors = exc_info.value.errors()
        assert any(
            "at least 1" in err["msg"].lower() or "min_length" in str(err).lower()
            for err in errors
        ), f"Expected min_length error, got: {errors}"

    def test_over_20_rejected(self):
        """More than 20 product IDs is rejected (max_length=20)."""
        ids = [uuid4() for _ in range(21)]
        with pytest.raises(ValidationError) as exc_info:
            ProductBatchFetchRequest(product_ids=ids)

        errors = exc_info.value.errors()
        assert any(
            "at most 20" in err["msg"].lower() or "max_length" in str(err).lower()
            for err in errors
        ), f"Expected max_length error, got: {errors}"

    def test_exactly_20_accepted(self):
        """Exactly 20 product IDs is accepted (boundary test)."""
        ids = [uuid4() for _ in range(20)]
        req = ProductBatchFetchRequest(product_ids=ids)
        assert len(req.product_ids) == 20

    def test_exactly_10_accepted(self):
        """10 product IDs is accepted (mid-range test)."""
        ids = [uuid4() for _ in range(10)]
        req = ProductBatchFetchRequest(product_ids=ids)
        assert len(req.product_ids) == 10

    def test_invalid_uuid_string_rejected(self):
        """Non-UUID string is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ProductBatchFetchRequest(product_ids=["not-a-uuid"])

        errors = exc_info.value.errors()
        assert any(
            "uuid" in err["msg"].lower() or "invalid" in err["msg"].lower()
            for err in errors
        ), f"Expected UUID validation error, got: {errors}"

    def test_mixed_valid_and_invalid_uuids_rejected(self):
        """Mixed valid and invalid UUIDs are rejected."""
        ids = [uuid4(), "invalid-uuid", uuid4()]
        with pytest.raises(ValidationError):
            ProductBatchFetchRequest(product_ids=ids)

    def test_duplicate_ids_allowed(self):
        """Duplicate UUIDs are allowed (deduplication is server responsibility)."""
        id1 = uuid4()
        req = ProductBatchFetchRequest(product_ids=[id1, id1, id1])
        assert len(req.product_ids) == 3
        assert req.product_ids[0] == req.product_ids[1] == req.product_ids[2]

    def test_none_value_rejected(self):
        """None value is rejected."""
        with pytest.raises(ValidationError):
            ProductBatchFetchRequest(product_ids=None)

    def test_string_uuid_auto_parsed(self):
        """Valid UUID strings are automatically parsed to UUID objects."""
        uuid_str = str(uuid4())
        req = ProductBatchFetchRequest(product_ids=[uuid_str])
        assert len(req.product_ids) == 1
        # Pydantic should auto-parse string to UUID
        assert isinstance(req.product_ids[0], type(uuid4()))


class TestSerializeProductForList:
    """Test serialize_product_for_list function logic."""

    def test_serializes_all_required_fields(self):
        """Test that serialize_product_for_list includes all fields needed by frontend."""
        from app.api.v1.products import serialize_product_for_list
        from app.models.product import Product, ReviewStatus
        from datetime import datetime

        # Create a mock product with all fields
        product = Product(
            id=uuid4(),
            leaflet_id=uuid4(),
            page_number=3,
            brand="TestBrand",
            product_code="TEST123",
            product_name="Test Product",
            quantity=500.0,
            units="g",
            size="500g",
            regular_price=Decimal("4.99"),
            discounted_price=None,
            discount_percentage=None,
            currency="EUR",
            product_id="1234567890",
            promotional_info="New!",
            suggested_category="Food & Groceries",
            category="Food & Groceries",
            category_confidence=0.95,
            category_alternatives=[],
            bbox_x=100,
            bbox_y=200,
            bbox_width=150,
            bbox_height=200,
            image_storage_type="file",
            image_base64=None,
            image_url="https://example.com/image.jpg",
            image_path="leaflets/LEAF_2025_000001/products/image.jpg",
            image_format="JPEG",
            image_width=400,
            image_height=500,
            image_size_bytes=50000,
            image_quality_score=0.92,
            confidence=0.89,
            field_confidence={"brand": 0.95, "product_name": 0.98},
            uncertainty_flags=["bbox_fallback"],
            review_status=ReviewStatus.PENDING,
            review_priority=5,
            reviewed_by=None,
            reviewed_at=None,
            validation_passed=True,
            validation_errors=[],
            is_corrected=False,
            is_split_product=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        result = serialize_product_for_list(product)

        # Check all essential fields are present
        assert result["id"] == product.id
        assert result["leaflet_id"] == product.leaflet_id
        assert result["page_number"] == 3
        assert result["brand"] == "TestBrand"
        assert result["product_code"] == "TEST123"
        assert result["product_name"] == "Test Product"
        assert result["quantity"] == 500.0
        assert result["units"] == "g"
        assert result["size"] == "500g"
        assert result["regular_price"] == 4.99  # Converted from Decimal to float
        assert result["discounted_price"] is None
        assert result["discount_percentage"] is None
        assert result["currency"] == "EUR"

        # Check bounding box structure
        assert "bounding_box" in result
        assert result["bounding_box"]["x"] == 100
        assert result["bounding_box"]["y"] == 200
        assert result["bounding_box"]["width"] == 150
        assert result["bounding_box"]["height"] == 200

        # Check image data structure
        assert "image" in result
        assert result["image"]["storage_type"] == "file"
        assert result["image"]["url"] == "https://example.com/image.jpg"
        assert result["image"]["path"] == "leaflets/LEAF_2025_000001/products/image.jpg"
        assert result["image"]["dimensions"]["width"] == 400
        assert result["image"]["dimensions"]["height"] == 500
        assert result["image"]["quality_score"] == 0.92

        # Check review fields
        assert result["review_status"] == "pending"
        assert result["confidence"] == 0.89
        assert result["validation_passed"] is True
        assert result["is_corrected"] is False

    def test_handles_none_prices_gracefully(self):
        """Test that None prices are handled correctly (not converted to float)."""
        from app.api.v1.products import serialize_product_for_list
        from app.models.product import Product, ReviewStatus
        from datetime import datetime

        product = Product(
            id=uuid4(),
            leaflet_id=uuid4(),
            page_number=1,
            product_name="Test",
            regular_price=None,
            discounted_price=None,
            discount_percentage=None,
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
            review_status=ReviewStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        result = serialize_product_for_list(product)

        assert result["regular_price"] is None
        assert result["discounted_price"] is None
        assert result["discount_percentage"] is None

    def test_converts_decimal_to_float(self):
        """Test that Decimal prices are converted to float for JSON serialization."""
        from app.api.v1.products import serialize_product_for_list
        from app.models.product import Product, ReviewStatus
        from datetime import datetime

        product = Product(
            id=uuid4(),
            leaflet_id=uuid4(),
            page_number=1,
            product_name="Test",
            regular_price=Decimal("9.99"),
            discounted_price=Decimal("7.49"),
            discount_percentage=Decimal("25.03"),
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
            review_status=ReviewStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        result = serialize_product_for_list(product)

        assert isinstance(result["regular_price"], float)
        assert isinstance(result["discounted_price"], float)
        assert isinstance(result["discount_percentage"], float)
        assert result["regular_price"] == 9.99
        assert result["discounted_price"] == 7.49
        assert result["discount_percentage"] == 25.03

    def test_handles_enum_review_status(self):
        """Test that ReviewStatus enum is converted to string value."""
        from app.api.v1.products import serialize_product_for_list
        from app.models.product import Product, ReviewStatus
        from datetime import datetime

        for status in [ReviewStatus.PENDING, ReviewStatus.APPROVED, ReviewStatus.REJECTED,
                       ReviewStatus.AUTO_APPROVED, ReviewStatus.NEEDS_CORRECTION]:
            product = Product(
                id=uuid4(),
                leaflet_id=uuid4(),
                page_number=1,
                product_name="Test",
                bbox_x=0,
                bbox_y=0,
                bbox_width=100,
                bbox_height=100,
                review_status=status,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            result = serialize_product_for_list(product)

            # Should be the enum's string value, not the enum object
            assert isinstance(result["review_status"], str)
            assert result["review_status"] == status.value

    def test_handles_missing_image_storage_type(self):
        """Test that products without images serialize correctly."""
        from app.api.v1.products import serialize_product_for_list
        from app.models.product import Product, ReviewStatus
        from datetime import datetime

        product = Product(
            id=uuid4(),
            leaflet_id=uuid4(),
            page_number=1,
            product_name="Test",
            image_storage_type=None,
            image_base64=None,
            image_url=None,
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
            review_status=ReviewStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        result = serialize_product_for_list(product)

        # Image field should be None when no storage type
        assert result["image"] is None
        assert result["image_storage_type"] is None

    def test_handles_base64_image_storage(self):
        """Test that base64-encoded images serialize correctly."""
        from app.api.v1.products import serialize_product_for_list
        from app.models.product import Product, ReviewStatus
        from datetime import datetime

        product = Product(
            id=uuid4(),
            leaflet_id=uuid4(),
            page_number=1,
            product_name="Test",
            image_storage_type="base64",
            image_base64="iVBORw0KGgoAAAANSUhEUgAAAAUA...",
            image_url=None,
            image_path=None,
            image_width=100,
            image_height=100,
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
            review_status=ReviewStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        result = serialize_product_for_list(product)

        assert result["image"]["storage_type"] == "base64"
        assert result["image"]["data"] == "iVBORw0KGgoAAAANSUhEUgAAAAUA..."
        assert result["image"]["url"] is None


if __name__ == "__main__":
    # Allow running tests directly with Python for quick verification
    pytest.main([__file__, "-v"])
