"""
Standalone unit tests for leaflet performance optimizations (no pytest fixtures).

This file tests the serialize_product_for_list function directly without
requiring database setup or pytest fixtures.
"""
import sys
sys.path.insert(0, '.')

from decimal import Decimal
from uuid import uuid4
from app.models.product import Product, ReviewStatus


def create_mock_product(**overrides):
    """Create a mock Product instance for testing."""
    defaults = {
        'id': uuid4(),
        'leaflet_id': uuid4(),
        'organization_id': uuid4(),
        'page_number': 1,
        'product_name': 'Test Product',
        'brand': 'Test Brand',
        'product_code': 'SKU-001',
        'regular_price': Decimal('9.99'),
        'discounted_price': None,
        'discount_percentage': None,
        'currency': 'EUR',
        'confidence': Decimal('0.95'),
        'review_status': ReviewStatus.PENDING,
        'validation_passed': True,
        'image_storage_type': 'base64',
        'image_base64': 'iVBORw0KGgo' + 'A' * 1000 + '==',
        'image_url': None,
        'image_path': None,
        'image_format': 'JPEG',
        'image_width': 200,
        'image_height': 250,
        'image_size_bytes': 1024,
        'image_quality_score': None,
        'bbox_x': 100,
        'bbox_y': 100,
        'bbox_width': 280,
        'bbox_height': 380,
        'quantity': None,
        'units': None,
        'size': None,
        'product_id': None,
        'promotional_info': None,
        'suggested_category': None,
        'category': None,
        'category_confidence': None,
        'category_alternatives': None,
        'field_confidence': None,
        'uncertainty_flags': None,
        'review_priority': 0,
        'reviewed_by': None,
        'reviewed_at': None,
        'validation_errors': None,
        'is_corrected': False,
        'is_split_product': False,
        'created_at': None,
        'updated_at': None,
    }
    defaults.update(overrides)

    # Create a mock object that acts like a Product
    class MockProduct:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    return MockProduct(**defaults)


def test_serialize_excludes_base64_by_default():
    """Base64 image data is excluded when include_base64 is False (default).

    Note: Products whose only image source is base64 (image_storage_type='base64'
    with no image_url) will still include base64 data.  This test uses a product
    with image_storage_type='file' and an image_url to verify true exclusion.
    """
    from app.api.v1.products import serialize_product_for_list

    product = create_mock_product(
        image_storage_type='file',
        image_url='https://s3.example.com/image.jpg',
    )
    result = serialize_product_for_list(product, include_base64=False)

    # image_base64 should be None
    assert result["image_base64"] is None, (
        "image_base64 must be None in list serialization"
    )

    # image.data should also be None
    assert result["image"] is not None
    assert result["image"]["data"] is None, (
        "image.data must be None in list serialization"
    )

    print("PASS: test_serialize_excludes_base64_by_default")


def test_serialize_includes_base64_when_requested():
    """Base64 image data is included when include_base64=True."""
    from app.api.v1.products import serialize_product_for_list

    product = create_mock_product()
    result = serialize_product_for_list(product, include_base64=True)

    # image_base64 should contain the actual data
    assert result["image_base64"] is not None
    assert len(result["image_base64"]) > 100, (
        "image_base64 should contain actual base64 data"
    )

    # image.data should also contain the data
    assert result["image"]["data"] is not None
    assert len(result["image"]["data"]) > 100

    print("PASS: test_serialize_includes_base64_when_requested")


def test_serialize_core_fields_always_present():
    """Core product fields are always present regardless of include_base64."""
    from app.api.v1.products import serialize_product_for_list

    product = create_mock_product(
        product_name="Test Product Name",
        brand="Test Brand Name",
        product_code="SKU-123",
        regular_price=Decimal('19.99'),
        currency="EUR",
        confidence=Decimal('0.92'),
    )
    result = serialize_product_for_list(product, include_base64=False)

    # Verify essential fields
    assert result["id"] is not None
    assert result["product_name"] == "Test Product Name"
    assert result["brand"] == "Test Brand Name"
    assert result["product_code"] == "SKU-123"
    assert result["page_number"] == 1
    assert result["regular_price"] == 19.99  # Converted to float
    assert result["currency"] == "EUR"
    assert result["confidence"] is not None
    assert "bounding_box" in result
    assert result["bounding_box"]["width"] == 280
    assert result["bounding_box"]["height"] == 380

    print("PASS: test_serialize_core_fields_always_present")


def test_serialize_decimal_to_float_conversion():
    """Decimal prices should be converted to float for JSON serialization."""
    from app.api.v1.products import serialize_product_for_list

    product = create_mock_product(
        regular_price=Decimal('12.50'),
        discounted_price=Decimal('9.99'),
        discount_percentage=Decimal('20.08'),
    )
    result = serialize_product_for_list(product, include_base64=False)

    # All prices should be float type
    assert isinstance(result["regular_price"], float)
    assert isinstance(result["discounted_price"], float)
    assert isinstance(result["discount_percentage"], float)

    # Values should be preserved
    assert result["regular_price"] == 12.50
    assert result["discounted_price"] == 9.99
    assert result["discount_percentage"] == 20.08

    print("PASS: test_serialize_decimal_to_float_conversion")


def test_serialize_null_prices_handled():
    """Null prices should be handled gracefully."""
    from app.api.v1.products import serialize_product_for_list

    product = create_mock_product(
        regular_price=None,
        discounted_price=None,
        discount_percentage=None,
    )
    result = serialize_product_for_list(product, include_base64=False)

    # Null prices should remain None
    assert result["regular_price"] is None
    assert result["discounted_price"] is None
    assert result["discount_percentage"] is None

    print("PASS: test_serialize_null_prices_handled")


def test_serialize_bounding_box_structure():
    """Bounding box should have correct structure."""
    from app.api.v1.products import serialize_product_for_list

    product = create_mock_product(
        bbox_x=150,
        bbox_y=200,
        bbox_width=300,
        bbox_height=400,
    )
    result = serialize_product_for_list(product, include_base64=False)

    bbox = result["bounding_box"]
    assert bbox["x"] == 150
    assert bbox["y"] == 200
    assert bbox["width"] == 300
    assert bbox["height"] == 400

    print("PASS: test_serialize_bounding_box_structure")


def test_serialize_image_structure():
    """Image data structure should be correct."""
    from app.api.v1.products import serialize_product_for_list

    product = create_mock_product(
        image_storage_type="file",
        image_url="https://s3.example.com/image.jpg",
        image_path="leaflets/LEAF_001/products/product_1.jpg",
        image_format="PNG",
    )
    result = serialize_product_for_list(product, include_base64=False)

    image = result["image"]
    assert image["storage_type"] == "file"
    assert image["data"] is None  # Excluded by default
    assert image["url"] == "https://s3.example.com/image.jpg"
    assert image["path"] == "leaflets/LEAF_001/products/product_1.jpg"
    assert image["format"] == "PNG"

    print("PASS: test_serialize_image_structure")


def test_payload_size_reduction():
    """Excluding base64 should significantly reduce serialized payload size."""
    import json
    from app.api.v1.products import serialize_product_for_list

    # Create product with realistic base64 blob (~10 KB) and a file URL so
    # that the base64 data is not treated as the only image source.
    large_base64 = "iVBORw0KGgo" + "A" * 10000 + "=="
    product = create_mock_product(
        image_base64=large_base64,
        image_storage_type='file',
        image_url='https://s3.example.com/image.jpg',
    )

    result_slim = serialize_product_for_list(product, include_base64=False)
    result_full = serialize_product_for_list(product, include_base64=True)

    slim_size = len(json.dumps(result_slim, default=str))
    full_size = len(json.dumps(result_full, default=str))

    # The full payload should be substantially larger due to base64
    reduction_ratio = full_size / slim_size
    assert reduction_ratio > 1.5, (
        f"Full payload ({full_size}) should be at least 50% larger than "
        f"slim payload ({slim_size}), got ratio {reduction_ratio:.2f}"
    )

    print(f"PASS: test_payload_size_reduction (slim: {slim_size}B, full: {full_size}B, ratio: {reduction_ratio:.2f}x)")


if __name__ == "__main__":
    print("\nRunning standalone unit tests for serialize_product_for_list...\n")

    try:
        test_serialize_excludes_base64_by_default()
        test_serialize_includes_base64_when_requested()
        test_serialize_core_fields_always_present()
        test_serialize_decimal_to_float_conversion()
        test_serialize_null_prices_handled()
        test_serialize_bounding_box_structure()
        test_serialize_image_structure()
        test_payload_size_reduction()

        print("\n" + "="*60)
        print("All 8 standalone tests passed!")
        print("="*60)
    except AssertionError as e:
        print(f"\nFAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
