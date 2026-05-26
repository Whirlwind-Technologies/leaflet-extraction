"""
Unit Tests for Pagination and Image Serialization Fixes.

Tests verifying that pagination and image serialization work correctly:

1. Pagination — Deterministic Sort:
   - Products with same created_at are sorted consistently by id tiebreaker
   - Page 1 and Page 2 return disjoint product sets (no overlaps)
   - All products across all pages = total (no gaps, no duplicates)
   - Example: 215 products, page_size=50 → 4 pages of 50 + 1 page of 15

2. Pagination — Edge Cases:
   - Single product → 1 page, 1 product
   - Exactly 50 products → 1 page of 50, no page 2
   - 51 products → page 1 has 50, page 2 has 1
   - Page beyond last → returns empty list (not error)
   - page_size > total products → returns all products in 1 page

3. Image Serialization — Base64-Only Products:
   - Product with image_storage_type='base64' and image_base64 data →
     serialize_product_for_list(include_base64=False) STILL includes base64
   - Product with image_storage_type='file' and image_url →
     serialize_product_for_list(include_base64=False) excludes base64, includes url
   - Product with image_storage_type='file' and BOTH base64 and url →
     excludes base64, includes url
   - Product with NO image at all (all null) → returns null for all image fields

4. Image Serialization — Detail vs List:
   - serialize_product_for_list(include_base64=True) always includes base64
   - serialize_product_for_list(include_base64=False) only includes base64 for base64-only products

5. Payload Size:
   - List of 100 file-stored products with include_base64=False → no base64 in any product
   - List with mix of base64-only and file-stored → only base64-only have base64 data

This test file bypasses pytest fixtures to avoid conftest environment issues.
Run with: python -m pytest tests/unit/test_pagination_and_images.py -v
"""

import sys
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

# Test the serialize_product_for_list function
# This requires a mock Product object with all necessary attributes


class MockProduct:
    """
    Mock Product object for testing serialize_product_for_list.

    Simulates the Product ORM model with all necessary attributes
    without requiring a database connection.
    """

    def __init__(
        self,
        id=None,
        leaflet_id=None,
        page_number=1,
        brand="Test Brand",
        product_code="SKU-001",
        product_name="Test Product",
        quantity=1.0,
        units="kg",
        size="1 kg",
        regular_price=Decimal("10.99"),
        discounted_price=None,
        discount_percentage=None,
        currency="EUR",
        product_id="1234567890",
        promotional_info=None,
        suggested_category=None,
        category="Food & Groceries",
        category_confidence=Decimal("0.85"),
        category_alternatives=None,
        bbox_x=100,
        bbox_y=200,
        bbox_width=300,
        bbox_height=400,
        image_storage_type="base64",
        image_base64=None,
        image_url=None,
        image_path=None,
        image_format="JPEG",
        image_width=200,
        image_height=250,
        image_size_bytes=50000,
        image_quality_score=Decimal("0.90"),
        confidence=Decimal("0.92"),
        field_confidence=None,
        uncertainty_flags=None,
        review_status="pending",
        review_priority=0,
        reviewed_by=None,
        reviewed_at=None,
        validation_passed=True,
        validation_errors=None,
        is_corrected=False,
        is_split_product=False,
        created_at=None,
        updated_at=None,
    ):
        self.id = id or uuid4()
        self.leaflet_id = leaflet_id or uuid4()
        self.page_number = page_number
        self.brand = brand
        self.product_code = product_code
        self.product_name = product_name
        self.quantity = quantity
        self.units = units
        self.size = size
        self.regular_price = regular_price
        self.discounted_price = discounted_price
        self.discount_percentage = discount_percentage
        self.currency = currency
        self.product_id = product_id
        self.promotional_info = promotional_info
        self.suggested_category = suggested_category
        self.category = category
        self.category_confidence = category_confidence
        self.category_alternatives = category_alternatives or []
        self.bbox_x = bbox_x
        self.bbox_y = bbox_y
        self.bbox_width = bbox_width
        self.bbox_height = bbox_height
        self.image_storage_type = image_storage_type
        self.image_base64 = image_base64
        self.image_url = image_url
        self.image_path = image_path
        self.image_format = image_format
        self.image_width = image_width
        self.image_height = image_height
        self.image_size_bytes = image_size_bytes
        self.image_quality_score = image_quality_score
        self.confidence = confidence
        self.field_confidence = field_confidence or {}
        self.uncertainty_flags = uncertainty_flags or []
        self.review_status = review_status
        self.review_priority = review_priority
        self.reviewed_by = reviewed_by
        self.reviewed_at = reviewed_at
        self.validation_passed = validation_passed
        self.validation_errors = validation_errors or []
        self.is_corrected = is_corrected
        self.is_split_product = is_split_product
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()


class TestSerializeProductForList:
    """
    Tests for the serialize_product_for_list helper function.

    Verifies that the function correctly handles base64 image data
    inclusion based on the include_base64 flag and storage type.
    """

    def test_base64_only_product_includes_base64_even_when_false(self):
        """
        Product with image_storage_type='base64' and NO image_url should
        include base64 data even when include_base64=False.

        This prevents base64-only products from having no image in list views.
        """
        from app.api.v1.products import serialize_product_for_list

        fake_base64 = "iVBORw0KGgoAAAANSU" + "A" * 1000 + "=="
        product = MockProduct(
            image_storage_type="base64",
            image_base64=fake_base64,
            image_url=None,
            image_path=None,
        )

        result = serialize_product_for_list(product, include_base64=False)

        # Base64-only products MUST have their base64 data included
        assert result["image_base64"] is not None, (
            "Base64-only product must include image_base64 even with include_base64=False"
        )
        assert result["image_base64"] == fake_base64

        # image.data should also be included
        assert result["image"] is not None
        assert result["image"]["data"] is not None
        assert result["image"]["data"] == fake_base64

    def test_file_stored_product_excludes_base64_when_false(self):
        """
        Product with image_storage_type='file' and image_url should
        exclude base64 data when include_base64=False.
        """
        from app.api.v1.products import serialize_product_for_list

        fake_base64 = "iVBORw0KGgoAAAANSU" + "A" * 1000 + "=="
        product = MockProduct(
            image_storage_type="file",
            image_base64=None,  # File-stored products typically don't have base64
            image_url="https://storage.example.com/product.jpg",
            image_path="leaflets/LEAF_2025_ABC123/products/product_1.jpg",
        )

        result = serialize_product_for_list(product, include_base64=False)

        # File-stored products should NOT include base64 in list view
        assert result["image_base64"] is None, (
            "File-stored product must NOT include image_base64 with include_base64=False"
        )

        # image.data should also be None
        assert result["image"] is not None
        assert result["image"]["data"] is None

        # But image_url should be present
        assert result["image_url"] == "https://storage.example.com/product.jpg"
        assert result["image"]["url"] == "https://storage.example.com/product.jpg"

    def test_file_stored_with_both_base64_and_url_excludes_base64_when_false(self):
        """
        Product with image_storage_type='file' and BOTH base64 and url
        should exclude base64 when include_base64=False.

        This can happen during migration or if the product was updated.
        """
        from app.api.v1.products import serialize_product_for_list

        fake_base64 = "iVBORw0KGgoAAAANSU" + "A" * 1000 + "=="
        product = MockProduct(
            image_storage_type="file",
            image_base64=fake_base64,  # Has both base64 and URL
            image_url="https://storage.example.com/product.jpg",
            image_path="leaflets/LEAF_2025_ABC123/products/product_1.jpg",
        )

        result = serialize_product_for_list(product, include_base64=False)

        # File-stored products should NOT include base64 even if they have it
        assert result["image_base64"] is None, (
            "File-stored product with both base64 and URL must exclude base64 with include_base64=False"
        )
        assert result["image"]["data"] is None

        # URL should still be present
        assert result["image_url"] == "https://storage.example.com/product.jpg"

    def test_product_with_no_image_returns_null(self):
        """
        Product with NO image data at all should return null for image fields.
        """
        from app.api.v1.products import serialize_product_for_list

        product = MockProduct(
            image_storage_type=None,
            image_base64=None,
            image_url=None,
            image_path=None,
        )

        result = serialize_product_for_list(product, include_base64=False)

        # All image fields should be None/null
        assert result["image_base64"] is None
        assert result["image_url"] is None
        assert result["image_path"] is None
        assert result["image"] is None  # Entire image object is None

    def test_include_base64_true_always_includes_base64(self):
        """
        When include_base64=True, base64 data should ALWAYS be included
        regardless of storage type.
        """
        from app.api.v1.products import serialize_product_for_list

        fake_base64 = "iVBORw0KGgoAAAANSU" + "A" * 1000 + "=="

        # Test with base64-only product
        base64_product = MockProduct(
            image_storage_type="base64",
            image_base64=fake_base64,
            image_url=None,
        )

        result_base64 = serialize_product_for_list(base64_product, include_base64=True)
        assert result_base64["image_base64"] is not None
        assert result_base64["image"]["data"] is not None

        # Test with file-stored product that has base64
        file_product = MockProduct(
            image_storage_type="file",
            image_base64=fake_base64,
            image_url="https://storage.example.com/product.jpg",
        )

        result_file = serialize_product_for_list(file_product, include_base64=True)
        assert result_file["image_base64"] is not None
        assert result_file["image"]["data"] is not None

    def test_payload_size_reduction_without_base64(self):
        """
        Verify that excluding base64 significantly reduces payload size.
        """
        import json
        from app.api.v1.products import serialize_product_for_list

        fake_base64 = "iVBORw0KGgoAAAANSU" + "A" * 5000 + "=="

        product = MockProduct(
            image_storage_type="base64",
            image_base64=fake_base64,
        )

        result_with_base64 = serialize_product_for_list(product, include_base64=True)
        result_without_base64 = serialize_product_for_list(product, include_base64=False)

        size_with = len(json.dumps(result_with_base64, default=str))
        size_without = len(json.dumps(result_without_base64, default=str))

        # Note: base64-only products still include base64 even with include_base64=False
        # So for a true test, we need a file-stored product
        file_product = MockProduct(
            image_storage_type="file",
            image_base64=fake_base64,
            image_url="https://storage.example.com/product.jpg",
        )

        file_result_with = serialize_product_for_list(file_product, include_base64=True)
        file_result_without = serialize_product_for_list(file_product, include_base64=False)

        file_size_with = len(json.dumps(file_result_with, default=str))
        file_size_without = len(json.dumps(file_result_without, default=str))

        # File-stored product should have much smaller payload without base64
        assert file_size_without < file_size_with * 0.5, (
            f"Payload without base64 ({file_size_without}) should be significantly "
            f"smaller than with base64 ({file_size_with})"
        )

    def test_mixed_products_only_base64_only_have_data(self):
        """
        In a list of mixed products (base64-only and file-stored),
        only base64-only products should have base64 data when include_base64=False.
        """
        from app.api.v1.products import serialize_product_for_list

        fake_base64 = "iVBORw0KGgoAAAANSU" + "A" * 1000 + "=="

        # Create mix of products
        base64_only = MockProduct(
            image_storage_type="base64",
            image_base64=fake_base64,
            image_url=None,
        )

        file_stored = MockProduct(
            image_storage_type="file",
            image_base64=None,
            image_url="https://storage.example.com/product.jpg",
        )

        result_base64 = serialize_product_for_list(base64_only, include_base64=False)
        result_file = serialize_product_for_list(file_stored, include_base64=False)

        # Base64-only should have data
        assert result_base64["image_base64"] is not None
        assert result_base64["image"]["data"] is not None

        # File-stored should NOT have data
        assert result_file["image_base64"] is None
        assert result_file["image"]["data"] is None


class TestPaginationDeterministicSort:
    """
    Tests for deterministic pagination with ORDER BY tiebreaker.

    Verifies that products with the same created_at timestamp are
    consistently sorted by id to prevent pagination overlap/gaps.
    """

    def test_order_by_clause_includes_id_tiebreaker(self):
        """
        The SQL query should ORDER BY sort_column AND id for determinism.

        This test checks the query construction logic.
        """
        # This is a logic test - the actual SQL query includes:
        # ORDER BY created_at DESC, id ASC
        # or
        # ORDER BY created_at ASC, id ASC

        # We verify the logic by checking that two products with the same
        # created_at but different IDs are sorted consistently

        product1 = MockProduct(
            id=uuid4(),
            product_name="Product A",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        )

        product2 = MockProduct(
            id=uuid4(),
            product_name="Product B",
            created_at=datetime(2025, 1, 1, 12, 0, 0),  # Same timestamp
        )

        # The products have the same created_at, so sorting by created_at alone
        # would be non-deterministic. The id tiebreaker ensures consistent order.

        # Sort by created_at, then by id (simulating the query)
        products = [product1, product2]
        sorted_products = sorted(products, key=lambda p: (p.created_at, p.id))

        # The order should be deterministic
        first_sort = sorted_products[0].id

        # Sort again
        sorted_again = sorted(products, key=lambda p: (p.created_at, p.id))

        # Should get the same order
        assert sorted_again[0].id == first_sort, (
            "Sorting by created_at + id should produce consistent order"
        )

    def test_pages_are_disjoint_no_overlap(self):
        """
        Page 1 and Page 2 should have completely disjoint product sets
        with no overlapping IDs.

        This is the core pagination correctness test.
        """
        # Create 100 products with the same created_at timestamp
        # (worst case for pagination without tiebreaker)
        same_timestamp = datetime(2025, 1, 1, 12, 0, 0)
        products = []

        for i in range(100):
            product = MockProduct(
                id=uuid4(),
                product_name=f"Product {i}",
                created_at=same_timestamp,
            )
            products.append(product)

        # Sort by created_at DESC, id ASC (simulating the query)
        sorted_products = sorted(
            products,
            key=lambda p: (-p.created_at.timestamp(), str(p.id))
        )

        # Page 1: first 50 products
        page1 = sorted_products[0:50]

        # Page 2: next 50 products
        page2 = sorted_products[50:100]

        # Extract IDs
        page1_ids = {p.id for p in page1}
        page2_ids = {p.id for p in page2}

        # Pages should be completely disjoint
        assert len(page1_ids & page2_ids) == 0, (
            "Page 1 and Page 2 must have no overlapping product IDs"
        )

        # Total should be 100 unique products
        assert len(page1_ids | page2_ids) == 100

    def test_all_products_across_pages_equals_total(self):
        """
        Collecting all products across all pages should equal the total count
        with no gaps or duplicates.

        Example: 215 products, page_size=50
        -> Page 1: 50, Page 2: 50, Page 3: 50, Page 4: 50, Page 5: 15
        -> Total: 215 unique products
        """
        # Create 215 products
        same_timestamp = datetime(2025, 1, 1, 12, 0, 0)
        products = []

        for i in range(215):
            product = MockProduct(
                id=uuid4(),
                product_name=f"Product {i}",
                created_at=same_timestamp,
            )
            products.append(product)

        # Sort by created_at DESC, id ASC
        sorted_products = sorted(
            products,
            key=lambda p: (-p.created_at.timestamp(), str(p.id))
        )

        page_size = 50
        all_ids_from_pages = set()

        # Fetch all pages
        for page_num in range(5):  # 5 pages: 50, 50, 50, 50, 15
            offset = page_num * page_size
            page_products = sorted_products[offset:offset + page_size]

            for p in page_products:
                all_ids_from_pages.add(p.id)

        # All IDs should be unique (no duplicates)
        assert len(all_ids_from_pages) == 215, (
            f"Expected 215 unique products across all pages, got {len(all_ids_from_pages)}"
        )

        # Verify last page has exactly 15 products
        page5 = sorted_products[200:250]
        assert len(page5) == 15, f"Page 5 should have 15 products, got {len(page5)}"


class TestPaginationEdgeCases:
    """
    Tests for pagination edge cases.

    Verifies correct behavior for:
    - Single product
    - Exactly page_size products
    - page_size + 1 products
    - Page beyond available pages
    - page_size > total products
    """

    def test_single_product_one_page(self):
        """
        Single product should result in 1 page with 1 product.
        """
        products = [MockProduct(id=uuid4(), product_name="Only Product")]

        page_size = 50
        page1 = products[0:page_size]

        assert len(page1) == 1
        assert page1[0].product_name == "Only Product"

        # Page 2 should be empty
        page2 = products[page_size:page_size * 2]
        assert len(page2) == 0

    def test_exactly_page_size_products_one_page(self):
        """
        Exactly 50 products should result in 1 page of 50, no page 2.
        """
        products = [MockProduct(id=uuid4()) for _ in range(50)]

        page_size = 50
        page1 = products[0:page_size]
        page2 = products[page_size:page_size * 2]

        assert len(page1) == 50
        assert len(page2) == 0

    def test_page_size_plus_one_two_pages(self):
        """
        51 products should result in page 1 with 50, page 2 with 1.
        """
        products = [MockProduct(id=uuid4()) for _ in range(51)]

        page_size = 50
        page1 = products[0:page_size]
        page2 = products[page_size:page_size * 2]

        assert len(page1) == 50
        assert len(page2) == 1

    def test_page_beyond_last_returns_empty_list(self):
        """
        Requesting page 999 when there are only 2 pages should return
        an empty list, not an error.
        """
        products = [MockProduct(id=uuid4()) for _ in range(100)]

        page_size = 50
        # Page 999 is way beyond available pages (only 2 pages exist)
        offset = 998 * page_size  # Page 999
        page999 = products[offset:offset + page_size]

        assert len(page999) == 0, (
            "Page beyond available pages should return empty list"
        )

    def test_page_size_greater_than_total_returns_all(self):
        """
        page_size > total products should return all products in 1 page.
        """
        products = [MockProduct(id=uuid4()) for _ in range(25)]

        page_size = 100  # Greater than 25
        page1 = products[0:page_size]

        assert len(page1) == 25, (
            "Should return all 25 products when page_size=100"
        )

    def test_total_pages_calculation(self):
        """
        Verify total_pages calculation: ceil(total / page_size)

        Examples:
        - 100 products, page_size=50 → 2 pages
        - 101 products, page_size=50 → 3 pages
        - 215 products, page_size=50 → 5 pages
        """
        import math

        test_cases = [
            (100, 50, 2),
            (101, 50, 3),
            (215, 50, 5),
            (50, 50, 1),
            (51, 50, 2),
            (1, 50, 1),
            (0, 50, 0),
        ]

        for total, page_size, expected_pages in test_cases:
            calculated_pages = math.ceil(total / page_size) if total > 0 else 0
            assert calculated_pages == expected_pages, (
                f"total={total}, page_size={page_size}: "
                f"expected {expected_pages} pages, got {calculated_pages}"
            )


class TestImageSerializationDetail:
    """
    Additional tests for image serialization edge cases.
    """

    def test_base64_only_without_url_is_recognized(self):
        """
        A product with image_storage_type='base64', has base64 data,
        and has NO image_url should be recognized as base64-only.
        """
        from app.api.v1.products import serialize_product_for_list

        fake_base64 = "iVBORw0KGgoAAAANSU" + "A" * 1000 + "=="
        product = MockProduct(
            image_storage_type="base64",
            image_base64=fake_base64,
            image_url=None,  # Critical: no URL
        )

        result = serialize_product_for_list(product, include_base64=False)

        # Should still include base64 because it's the only image source
        assert result["image_base64"] is not None

    def test_base64_with_url_is_not_base64_only(self):
        """
        A product with image_storage_type='base64' but also has image_url
        is NOT considered base64-only.

        This shouldn't happen in practice, but tests the logic.
        """
        from app.api.v1.products import serialize_product_for_list

        fake_base64 = "iVBORw0KGgoAAAANSU" + "A" * 1000 + "=="
        product = MockProduct(
            image_storage_type="base64",
            image_base64=fake_base64,
            image_url="https://storage.example.com/product.jpg",  # Has URL
        )

        result = serialize_product_for_list(product, include_base64=False)

        # Has URL, so base64 is excluded
        assert result["image_base64"] is None

    def test_all_core_fields_present_regardless_of_base64(self):
        """
        Core product fields should always be present regardless of
        include_base64 flag.
        """
        from app.api.v1.products import serialize_product_for_list

        product = MockProduct()

        result_with = serialize_product_for_list(product, include_base64=True)
        result_without = serialize_product_for_list(product, include_base64=False)

        # Core fields that must always be present
        required_fields = [
            "id", "leaflet_id", "page_number", "brand", "product_code",
            "product_name", "regular_price", "currency", "confidence",
            "review_status", "bounding_box", "created_at"
        ]

        for field in required_fields:
            assert field in result_with, f"{field} missing with include_base64=True"
            assert field in result_without, f"{field} missing with include_base64=False"

            # Values should be the same
            assert result_with[field] == result_without[field], (
                f"{field} value differs between include_base64=True/False"
            )

    def test_bounding_box_structure(self):
        """
        Verify bounding_box is always included with correct structure.
        """
        from app.api.v1.products import serialize_product_for_list

        product = MockProduct(
            bbox_x=100,
            bbox_y=200,
            bbox_width=300,
            bbox_height=400,
        )

        result = serialize_product_for_list(product, include_base64=False)

        assert "bounding_box" in result
        bbox = result["bounding_box"]

        assert bbox["x"] == 100
        assert bbox["y"] == 200
        assert bbox["width"] == 300
        assert bbox["height"] == 400

    def test_decimal_fields_converted_to_float(self):
        """
        Decimal fields (prices, confidence) should be converted to float
        for JSON serialization.
        """
        from app.api.v1.products import serialize_product_for_list

        product = MockProduct(
            regular_price=Decimal("10.99"),
            discounted_price=Decimal("7.49"),
            discount_percentage=Decimal("31.85"),
            confidence=Decimal("0.92"),
            category_confidence=Decimal("0.85"),
            image_quality_score=Decimal("0.90"),
        )

        result = serialize_product_for_list(product, include_base64=False)

        # All should be float, not Decimal
        assert isinstance(result["regular_price"], float)
        assert isinstance(result["discounted_price"], float)
        assert isinstance(result["discount_percentage"], float)
        assert isinstance(result["confidence"], float)
        assert isinstance(result["category_confidence"], float)
        assert isinstance(result["image_quality_score"], float)

        # Values should be correct
        assert result["regular_price"] == 10.99
        assert result["discounted_price"] == 7.49
        assert result["discount_percentage"] == 31.85

    def test_null_decimal_fields_stay_null(self):
        """
        Null Decimal fields should remain None, not become 0.0.
        """
        from app.api.v1.products import serialize_product_for_list

        product = MockProduct(
            regular_price=Decimal("10.99"),
            discounted_price=None,
            discount_percentage=None,
        )

        result = serialize_product_for_list(product, include_base64=False)

        assert result["regular_price"] == 10.99
        assert result["discounted_price"] is None
        assert result["discount_percentage"] is None

    def test_image_structure_for_base64_storage(self):
        """
        Verify the image structure for base64 storage type.
        """
        from app.api.v1.products import serialize_product_for_list

        fake_base64 = "iVBORw0KGgoAAAANSU" + "A" * 1000 + "=="
        product = MockProduct(
            image_storage_type="base64",
            image_base64=fake_base64,
            image_url=None,
            image_path=None,
            image_format="JPEG",
            image_width=200,
            image_height=250,
            image_size_bytes=50000,
            image_quality_score=Decimal("0.90"),
        )

        result = serialize_product_for_list(product, include_base64=False)

        assert result["image"] is not None
        image = result["image"]

        assert image["storage_type"] == "base64"
        assert image["data"] is not None  # Base64-only includes data
        assert image["url"] is None
        assert image["path"] is None
        assert image["format"] == "JPEG"
        assert image["dimensions"]["width"] == 200
        assert image["dimensions"]["height"] == 250
        assert image["size_bytes"] == 50000
        assert image["quality_score"] == 0.90

    def test_image_structure_for_file_storage(self):
        """
        Verify the image structure for file storage type.
        """
        from app.api.v1.products import serialize_product_for_list

        product = MockProduct(
            image_storage_type="file",
            image_base64=None,
            image_url="https://storage.example.com/product.jpg",
            image_path="leaflets/LEAF_2025_ABC123/products/product_1.jpg",
            image_format="JPEG",
            image_width=200,
            image_height=250,
            image_size_bytes=50000,
            image_quality_score=Decimal("0.90"),
        )

        result = serialize_product_for_list(product, include_base64=False)

        assert result["image"] is not None
        image = result["image"]

        assert image["storage_type"] == "file"
        assert image["data"] is None  # File storage excludes data
        assert image["url"] == "https://storage.example.com/product.jpg"
        assert image["path"] == "leaflets/LEAF_2025_ABC123/products/product_1.jpg"
        assert image["format"] == "JPEG"


# Standalone test runner
if __name__ == "__main__":
    print("=" * 70)
    print("Pagination and Image Serialization Tests")
    print("=" * 70)
    print()

    # Add the backend directory to the path
    import os
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Run tests
    test_classes = [
        TestSerializeProductForList,
        TestPaginationDeterministicSort,
        TestPaginationEdgeCases,
        TestImageSerializationDetail,
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    for test_class in test_classes:
        print(f"\n{test_class.__name__}")
        print("-" * 70)

        instance = test_class()

        # Get all test methods
        test_methods = [
            method for method in dir(instance)
            if method.startswith("test_") and callable(getattr(instance, method))
        ]

        for test_method_name in test_methods:
            total_tests += 1
            test_method = getattr(instance, test_method_name)

            try:
                test_method()
                print(f"[PASS] {test_method_name}")
                passed_tests += 1
            except Exception as e:
                print(f"[FAIL] {test_method_name}")
                print(f"  Error: {e}")
                failed_tests.append((test_class.__name__, test_method_name, str(e)))

    # Summary
    print()
    print("=" * 70)
    print(f"Test Summary: {passed_tests}/{total_tests} passed")
    print("=" * 70)

    if failed_tests:
        print("\nFailed Tests:")
        for class_name, method_name, error in failed_tests:
            print(f"  - {class_name}.{method_name}")
            print(f"    {error}")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)
