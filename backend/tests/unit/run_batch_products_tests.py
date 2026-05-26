#!/usr/bin/env python
"""
Direct test runner for batch products feature.

This script bypasses pytest to avoid conftest environment issues.
Run with: python tests/unit/run_batch_products_tests.py
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4
from decimal import Decimal
from datetime import datetime
from pydantic import ValidationError

# Import test subjects
from app.schemas.product import ProductBatchFetchRequest
from app.api.v1.products import serialize_product_for_list
from app.models.product import Product, ReviewStatus


def run_schema_tests():
    """Run ProductBatchFetchRequest schema validation tests."""
    print("\n" + "="*70)
    print("TESTING: ProductBatchFetchRequest Schema Validation")
    print("="*70)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Valid request with 5 IDs
    try:
        ids = [uuid4() for _ in range(5)]
        req = ProductBatchFetchRequest(product_ids=ids)
        assert len(req.product_ids) == 5
        print("[PASS] Valid request with 5 IDs")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Valid request with 5 IDs: {e}")
        tests_failed += 1

    # Test 2: Valid request with 1 ID (minimum)
    try:
        ids = [uuid4()]
        req = ProductBatchFetchRequest(product_ids=ids)
        assert len(req.product_ids) == 1
        print("[PASS] Valid request with 1 ID (minimum)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Valid request with 1 ID: {e}")
        tests_failed += 1

    # Test 3: Empty list rejected
    try:
        try:
            ProductBatchFetchRequest(product_ids=[])
            print("[FAIL] Empty list should be rejected")
            tests_failed += 1
        except ValidationError:
            print("[PASS] Empty list rejected (min_length=1)")
            tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Empty list test: {e}")
        tests_failed += 1

    # Test 4: Over 20 rejected
    try:
        ids = [uuid4() for _ in range(21)]
        try:
            ProductBatchFetchRequest(product_ids=ids)
            print("[FAIL] Over 20 IDs should be rejected")
            tests_failed += 1
        except ValidationError:
            print("[PASS] Over 20 IDs rejected (max_length=20)")
            tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Over 20 test: {e}")
        tests_failed += 1

    # Test 5: Exactly 20 accepted
    try:
        ids = [uuid4() for _ in range(20)]
        req = ProductBatchFetchRequest(product_ids=ids)
        assert len(req.product_ids) == 20
        print("[PASS] Exactly 20 IDs accepted (boundary)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Exactly 20 IDs: {e}")
        tests_failed += 1

    # Test 6: Invalid UUID rejected
    try:
        try:
            ProductBatchFetchRequest(product_ids=["not-a-uuid"])
            print("[FAIL] Invalid UUID should be rejected")
            tests_failed += 1
        except ValidationError:
            print("[PASS] Invalid UUID string rejected")
            tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Invalid UUID test: {e}")
        tests_failed += 1

    # Test 7: Valid UUID string auto-parsed
    try:
        uuid_str = str(uuid4())
        req = ProductBatchFetchRequest(product_ids=[uuid_str])
        assert len(req.product_ids) == 1
        assert isinstance(req.product_ids[0], type(uuid4()))
        print("[PASS] Valid UUID string auto-parsed to UUID object")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] UUID string auto-parse: {e}")
        tests_failed += 1

    # Test 8: Duplicate IDs allowed
    try:
        id1 = uuid4()
        req = ProductBatchFetchRequest(product_ids=[id1, id1, id1])
        assert len(req.product_ids) == 3
        print("[PASS] Duplicate IDs allowed")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Duplicate IDs: {e}")
        tests_failed += 1

    return tests_passed, tests_failed


def run_serialization_tests():
    """Run serialize_product_for_list function tests."""
    print("\n" + "="*70)
    print("TESTING: serialize_product_for_list Function")
    print("="*70)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Serializes all required fields
    try:
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
            bbox_x=100,
            bbox_y=200,
            bbox_width=150,
            bbox_height=200,
            image_storage_type="file",
            image_url="https://example.com/image.jpg",
            image_path="leaflets/LEAF_2025_000001/products/image.jpg",
            image_width=400,
            image_height=500,
            confidence=0.89,
            review_status=ReviewStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        result = serialize_product_for_list(product)

        assert result["page_number"] == 3
        assert result["brand"] == "TestBrand"
        assert result["regular_price"] == 4.99
        assert result["bounding_box"]["x"] == 100
        assert result["image"]["storage_type"] == "file"
        assert result["review_status"] == "pending"

        print("[PASS] Serializes all required fields")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Serialize all fields: {e}")
        tests_failed += 1

    # Test 2: Handles None prices
    try:
        product = Product(
            id=uuid4(),
            leaflet_id=uuid4(),
            page_number=1,
            product_name="Test",
            regular_price=None,
            discounted_price=None,
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

        print("[PASS] Handles None prices gracefully")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Handle None prices: {e}")
        tests_failed += 1

    # Test 3: Converts Decimal to float
    try:
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
        assert result["regular_price"] == 9.99
        assert result["discounted_price"] == 7.49

        print("[PASS] Converts Decimal to float")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Convert Decimal to float: {e}")
        tests_failed += 1

    # Test 4: Handles enum review status
    try:
        for status in [ReviewStatus.PENDING, ReviewStatus.APPROVED, ReviewStatus.REJECTED]:
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
            assert isinstance(result["review_status"], str)
            assert result["review_status"] == status.value

        print("[PASS] Handles enum review status")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Handle enum status: {e}")
        tests_failed += 1

    # Test 5: Handles missing image storage
    try:
        product = Product(
            id=uuid4(),
            leaflet_id=uuid4(),
            page_number=1,
            product_name="Test",
            image_storage_type=None,
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
            review_status=ReviewStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        result = serialize_product_for_list(product)

        assert result["image"] is None

        print("[PASS] Handles missing image storage type")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Handle missing image: {e}")
        tests_failed += 1

    # Test 6: Handles base64 image storage
    try:
        product = Product(
            id=uuid4(),
            leaflet_id=uuid4(),
            page_number=1,
            product_name="Test",
            image_storage_type="base64",
            image_base64="iVBORw0KGgoAAAANSUhEUgAAAAUA...",
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

        print("[PASS] Handles base64 image storage")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Handle base64 image: {e}")
        tests_failed += 1

    return tests_passed, tests_failed


def main():
    """Run all tests and report results."""
    print("\n" + "="*70)
    print("BATCH PRODUCTS FEATURE TEST SUITE")
    print("="*70)

    schema_passed, schema_failed = run_schema_tests()
    serial_passed, serial_failed = run_serialization_tests()

    total_passed = schema_passed + serial_passed
    total_failed = schema_failed + serial_failed
    total_tests = total_passed + total_failed

    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Schema Validation:  {schema_passed}/{schema_passed + schema_failed} passed")
    print(f"Serialization:      {serial_passed}/{serial_passed + serial_failed} passed")
    print(f"\nTOTAL:              {total_passed}/{total_tests} passed")

    if total_failed == 0:
        print("\nRESULT: ALL TESTS PASSED")
        return 0
    else:
        print(f"\nRESULT: {total_failed} TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
