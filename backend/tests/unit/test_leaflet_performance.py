"""
Unit Tests for Leaflet Performance Optimizations.

Tests verifying that the performance fixes for large leaflets (50 pages,
150+ products) work correctly:
1. Product list endpoint excludes base64 image data by default
2. Product list page_size is capped at 100
3. Single product detail includes base64 image data
4. Leaflet detail includes products_count from COUNT query
5. Leaflet list includes batch-fetched product counts
6. serialize_product_for_list respects include_base64 flag
"""

import pytest
from datetime import datetime
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leaflet import Leaflet, LeafletPage, LeafletStatus
from app.models.product import Product, ReviewStatus
from app.models.organization import Organization
from app.models.user import User
from app.api.v1.products import serialize_product_for_list


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def perf_leaflet(
    db_session: AsyncSession,
    test_organization: Organization,
) -> Leaflet:
    """Create a test leaflet with multiple pages for performance tests."""
    leaflet = Leaflet(
        id=uuid4(),
        organization_id=test_organization.id,
        leaflet_id=f"LEAF_2025_{uuid4().hex[:6].upper()}",
        filename="large_leaflet.pdf",
        status=LeafletStatus.COMPLETED,
        page_count=5,
    )

    db_session.add(leaflet)
    await db_session.commit()
    await db_session.refresh(leaflet)

    # Create 5 pages for the leaflet
    for page_num in range(1, 6):
        page = LeafletPage(
            id=uuid4(),
            leaflet_id=leaflet.id,
            page_number=page_num,
            image_path=f"leaflets/{leaflet.leaflet_id}/pages/page_{page_num:03d}.png",
            thumbnail_path=f"leaflets/{leaflet.leaflet_id}/thumbnails/page_{page_num:03d}_thumb.jpg",
            width=2480,
            height=3508,
        )
        db_session.add(page)

    await db_session.commit()
    return leaflet


@pytest.fixture
async def perf_products(
    db_session: AsyncSession,
    perf_leaflet: Leaflet,
    test_organization: Organization,
) -> list[Product]:
    """Create 30 test products across 5 pages with base64 image data.

    This fixture creates products with realistic base64 blobs (~1 KB each,
    enough to verify the exclusion logic) distributed across pages 1-5.
    """
    # A small but non-trivial base64 string (~1 KB) to simulate image data.
    fake_base64 = "iVBORw0KGgoAAAANSU" + "A" * 1000 + "=="

    products = []
    for i in range(30):
        page_num = (i % 5) + 1
        product = Product(
            id=uuid4(),
            leaflet_id=perf_leaflet.id,
            organization_id=test_organization.id,
            page_number=page_num,
            product_name=f"Test Product {i + 1}",
            brand=f"Brand {(i % 3) + 1}",
            product_code=f"SKU-{i + 1:04d}",
            regular_price=round(1.99 + i * 0.5, 2),
            discounted_price=round(1.49 + i * 0.4, 2) if i % 3 == 0 else None,
            currency="EUR",
            confidence=0.85 + (i % 10) * 0.015,
            review_status=ReviewStatus.AUTO_APPROVED if i % 4 != 0 else ReviewStatus.PENDING,
            validation_passed=True,
            image_storage_type="base64",
            image_base64=fake_base64,
            image_format="JPEG",
            image_width=200,
            image_height=250,
            image_size_bytes=len(fake_base64),
            bbox_x=50 + (i % 3) * 300,
            bbox_y=50 + (i // 3) * 400,
            bbox_width=280,
            bbox_height=380,
        )
        products.append(product)

    db_session.add_all(products)
    await db_session.commit()

    # Refresh to get any server-set defaults
    for p in products:
        await db_session.refresh(p)

    return products


# ---------------------------------------------------------------------------
# Tests: serialize_product_for_list
# ---------------------------------------------------------------------------


class TestSerializeProductForList:
    """Tests for the serialize_product_for_list helper function."""

    async def test_excludes_base64_by_default(
        self, perf_products: list[Product]
    ) -> None:
        """Base64 image data is excluded when include_base64 is False (default)."""
        product = perf_products[0]
        result = serialize_product_for_list(product)

        # image_base64 should be None
        assert result["image_base64"] is None, (
            "image_base64 must be None in list serialization"
        )

        # image.data should also be None
        assert result["image"] is not None
        assert result["image"]["data"] is None, (
            "image.data must be None in list serialization"
        )

    async def test_includes_base64_when_requested(
        self, perf_products: list[Product]
    ) -> None:
        """Base64 image data is included when include_base64=True."""
        product = perf_products[0]
        result = serialize_product_for_list(product, include_base64=True)

        # image_base64 should contain the actual data
        assert result["image_base64"] is not None
        assert len(result["image_base64"]) > 100, (
            "image_base64 should contain actual base64 data"
        )

        # image.data should also contain the data
        assert result["image"]["data"] is not None
        assert len(result["image"]["data"]) > 100

    async def test_url_always_present(
        self, perf_products: list[Product]
    ) -> None:
        """image_url is always included regardless of include_base64 flag."""
        product = perf_products[0]

        result_no_base64 = serialize_product_for_list(product, include_base64=False)
        result_with_base64 = serialize_product_for_list(product, include_base64=True)

        # Both should have the same image_url
        assert result_no_base64["image_url"] == result_with_base64["image_url"]

    async def test_core_fields_always_present(
        self, perf_products: list[Product]
    ) -> None:
        """Core product fields are always present regardless of include_base64."""
        product = perf_products[0]
        result = serialize_product_for_list(product)

        # Verify essential fields
        assert result["id"] is not None
        assert result["product_name"] == product.product_name
        assert result["brand"] == product.brand
        assert result["product_code"] == product.product_code
        assert result["page_number"] == product.page_number
        assert result["regular_price"] is not None
        assert result["currency"] == "EUR"
        assert result["confidence"] is not None
        assert "bounding_box" in result
        assert result["bounding_box"]["width"] > 0

    async def test_payload_size_reduction(
        self, perf_products: list[Product]
    ) -> None:
        """Excluding base64 significantly reduces serialized payload size."""
        import json

        product = perf_products[0]
        result_slim = serialize_product_for_list(product, include_base64=False)
        result_full = serialize_product_for_list(product, include_base64=True)

        slim_size = len(json.dumps(result_slim, default=str))
        full_size = len(json.dumps(result_full, default=str))

        # The full payload should be substantially larger due to base64
        assert full_size > slim_size * 1.5, (
            f"Full payload ({full_size}) should be at least 50% larger than "
            f"slim payload ({slim_size})"
        )


# ---------------------------------------------------------------------------
# Tests: Product list endpoint
# ---------------------------------------------------------------------------


class TestProductListPerformance:
    """Tests for the product list endpoint performance optimizations."""

    async def test_list_products_excludes_base64(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """GET /products should not include base64 image data."""
        response = await client.get(
            f"/api/v1/products?leaflet_id={perf_leaflet.id}&page_size=10",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        assert len(items) > 0

        for item in items:
            assert item["image_base64"] is None, (
                f"Product {item['id']} should not have image_base64 in list response"
            )
            if item.get("image"):
                assert item["image"]["data"] is None, (
                    f"Product {item['id']} should not have image.data in list response"
                )

    async def test_page_size_cap_at_100(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """Requesting page_size > 100 should be rejected."""
        response = await client.get(
            f"/api/v1/products?leaflet_id={perf_leaflet.id}&page_size=500",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        # FastAPI Query validation should reject page_size > 100
        assert response.status_code == 422, (
            "page_size=500 should be rejected with 422 Validation Error"
        )

    async def test_pagination_works_with_small_pages(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """Products can be paginated in small pages."""
        response = await client.get(
            f"/api/v1/products?leaflet_id={perf_leaflet.id}&page=1&page_size=10",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 30
        assert len(data["items"]) == 10
        assert data["page"] == 1

        # Fetch page 2
        response2 = await client.get(
            f"/api/v1/products?leaflet_id={perf_leaflet.id}&page=2&page_size=10",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["items"]) == 10
        assert data2["page"] == 2

        # Verify no overlap between pages
        page1_ids = {item["id"] for item in data["items"]}
        page2_ids = {item["id"] for item in data2["items"]}
        assert page1_ids.isdisjoint(page2_ids), "Pages should have no overlapping products"

    async def test_page_number_filter(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """Products can be filtered by page_number."""
        response = await client.get(
            f"/api/v1/products?leaflet_id={perf_leaflet.id}&page_number=1&page_size=50",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        items = data["items"]

        # 30 products spread across 5 pages = 6 per page
        assert len(items) == 6
        for item in items:
            assert item["page_number"] == 1, (
                f"Product should be on page 1, got page {item['page_number']}"
            )


# ---------------------------------------------------------------------------
# Tests: Single product detail endpoint
# ---------------------------------------------------------------------------


class TestProductDetailPerformance:
    """Tests for the single product detail endpoint."""

    async def test_single_product_includes_base64(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_products: list[Product],
    ) -> None:
        """GET /products/{id} should include base64 image data."""
        product_id = str(perf_products[0].id)

        response = await client.get(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Single product detail should have base64 data
        assert data["image_base64"] is not None, (
            "Single product detail must include image_base64"
        )
        assert len(data["image_base64"]) > 100

        if data.get("image"):
            assert data["image"]["data"] is not None, (
                "Single product detail must include image.data"
            )


# ---------------------------------------------------------------------------
# Tests: Leaflet detail endpoint
# ---------------------------------------------------------------------------


class TestLeafletDetailPerformance:
    """Tests for the leaflet detail endpoint performance optimizations."""

    async def test_leaflet_detail_includes_products_count(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """GET /leaflets/{id} should include products_count from COUNT query."""
        response = await client.get(
            f"/api/v1/leaflets/{perf_leaflet.id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "products_count" in data
        assert data["products_count"] == 30, (
            f"Expected 30 products, got {data['products_count']}"
        )

    async def test_leaflet_detail_includes_pages(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """GET /leaflets/{id} should include page data."""
        response = await client.get(
            f"/api/v1/leaflets/{perf_leaflet.id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "pages" in data
        assert len(data["pages"]) == 5

        # Pages should be ordered by page_number
        page_numbers = [p["page_number"] for p in data["pages"]]
        assert page_numbers == sorted(page_numbers)

    async def test_leaflet_detail_does_not_include_products(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """GET /leaflets/{id} should NOT embed full product list."""
        response = await client.get(
            f"/api/v1/leaflets/{perf_leaflet.id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # The leaflet detail should NOT have a "products" key with product data.
        # Products are fetched separately via /products?leaflet_id=...
        assert "products" not in data or data.get("products") is None, (
            "Leaflet detail must not embed full products list"
        )


# ---------------------------------------------------------------------------
# Tests: Leaflet list endpoint
# ---------------------------------------------------------------------------


class TestLeafletListPerformance:
    """Tests for the leaflet list endpoint performance optimizations."""

    async def test_leaflet_list_includes_products_count(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """GET /leaflets should include products_count for each leaflet."""
        response = await client.get(
            "/api/v1/leaflets",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        items = data.get("items", [])
        assert len(items) >= 1

        # Find our test leaflet in the list
        target = next(
            (item for item in items if str(item["id"]) == str(perf_leaflet.id)),
            None,
        )

        assert target is not None, "Test leaflet not found in list"
        assert "products_count" in target
        assert target["products_count"] == 30


# ---------------------------------------------------------------------------
# Tests: Review queue endpoint
# ---------------------------------------------------------------------------


class TestReviewQueuePerformance:
    """Tests for the review queue endpoint page_size cap."""

    async def test_review_queue_page_size_cap(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_products: list[Product],
    ) -> None:
        """Review queue should reject page_size > 100."""
        response = await client.get(
            "/api/v1/products/review-queue?page_size=500",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422, (
            "Review queue page_size=500 should be rejected with 422"
        )


# ---------------------------------------------------------------------------
# Tests: Pagination defaults and edge cases
# ---------------------------------------------------------------------------


class TestPaginationDefaults:
    """Tests for pagination defaults and edge cases."""

    async def test_default_page_size_is_20(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """Default page_size should be 20 when not specified."""
        response = await client.get(
            f"/api/v1/products?leaflet_id={perf_leaflet.id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should return 20 items (out of 30 total)
        assert len(data["items"]) == 20, (
            f"Default page_size should be 20, got {len(data['items'])}"
        )
        assert data["total"] == 30
        assert data["page_size"] == 20

    async def test_out_of_range_page_returns_empty_list(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """Requesting page beyond available pages returns empty list, not error."""
        response = await client.get(
            f"/api/v1/products?leaflet_id={perf_leaflet.id}&page=999&page_size=10",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200, (
            "Out-of-range page should return 200, not error"
        )
        data = response.json()
        assert data["total"] == 30
        assert len(data["items"]) == 0, (
            "Out-of-range page should return empty items list"
        )
        assert data["page"] == 999

    async def test_pagination_metadata_accuracy(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """Pagination metadata (total_pages, has_next) should be accurate."""
        # Page 1 of 3 (30 items, 10 per page)
        response1 = await client.get(
            f"/api/v1/products?leaflet_id={perf_leaflet.id}&page=1&page_size=10",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["total"] == 30
        assert data1["page"] == 1
        assert data1["page_size"] == 10

        # Calculate expected total_pages: ceil(30 / 10) = 3
        expected_total_pages = 3
        if "total_pages" in data1:
            assert data1["total_pages"] == expected_total_pages, (
                f"Expected {expected_total_pages} total pages, got {data1['total_pages']}"
            )

        # has_next should be True on page 1
        if "has_next" in data1:
            assert data1["has_next"] is True, (
                "Page 1 of 3 should have has_next=True"
            )

        # Page 3 of 3 (last page)
        response3 = await client.get(
            f"/api/v1/products?leaflet_id={perf_leaflet.id}&page=3&page_size=10",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response3.status_code == 200
        data3 = response3.json()

        # Last page should have remaining items (30 - 20 = 10)
        assert len(data3["items"]) == 10

        # has_next should be False on last page
        if "has_next" in data3:
            assert data3["has_next"] is False, (
                "Last page should have has_next=False"
            )


# ---------------------------------------------------------------------------
# Tests: Product count consistency
# ---------------------------------------------------------------------------


class TestProductCountConsistency:
    """Tests for product count consistency across endpoints."""

    async def test_leaflet_detail_count_matches_db(
        self,
        client: AsyncClient,
        valid_token: str,
        db_session: AsyncSession,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """Leaflet detail products_count should match actual COUNT from database."""
        # Get actual count from database
        count_result = await db_session.execute(
            select(func.count(Product.id)).where(Product.leaflet_id == perf_leaflet.id)
        )
        actual_count = count_result.scalar()
        assert actual_count == 30, "Test setup should have 30 products"

        # Get count from API
        response = await client.get(
            f"/api/v1/leaflets/{perf_leaflet.id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["products_count"] == actual_count, (
            f"API products_count ({data['products_count']}) "
            f"should match database count ({actual_count})"
        )

    async def test_leaflet_list_batch_counts_match_individual(
        self,
        client: AsyncClient,
        valid_token: str,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
    ) -> None:
        """Batch product counts in leaflet list should match individual leaflet counts."""
        # Get count from leaflet list (uses batch query)
        list_response = await client.get(
            "/api/v1/leaflets",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert list_response.status_code == 200
        list_data = list_response.json()

        # Find our test leaflet in the list
        target_leaflet = next(
            (item for item in list_data["items"] if str(item["id"]) == str(perf_leaflet.id)),
            None,
        )
        assert target_leaflet is not None, "Test leaflet should be in list"
        list_count = target_leaflet["products_count"]

        # Get count from leaflet detail (uses single COUNT query)
        detail_response = await client.get(
            f"/api/v1/leaflets/{perf_leaflet.id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert detail_response.status_code == 200
        detail_data = detail_response.json()
        detail_count = detail_data["products_count"]

        assert list_count == detail_count, (
            f"Batch count from list ({list_count}) should match "
            f"individual count from detail ({detail_count})"
        )


# ---------------------------------------------------------------------------
# Tests: Organization scoping
# ---------------------------------------------------------------------------


class TestOrganizationScoping:
    """Tests for organization-level data isolation."""

    async def test_product_counts_only_include_org_products(
        self,
        client: AsyncClient,
        valid_token: str,
        db_session: AsyncSession,
        perf_leaflet: Leaflet,
        perf_products: list[Product],
        test_organization: Organization,
    ) -> None:
        """Product counts should only include products from user's organization."""
        # Create a second organization with its own leaflet and products
        other_org = Organization(
            id=uuid4(),
            name="Other Organization",
            slug="other-org",
        )
        db_session.add(other_org)
        await db_session.commit()

        other_leaflet = Leaflet(
            id=uuid4(),
            organization_id=other_org.id,
            leaflet_id=f"LEAF_2025_{uuid4().hex[:6].upper()}",
            filename="other_leaflet.pdf",
            status=LeafletStatus.COMPLETED,
            page_count=1,
        )
        db_session.add(other_leaflet)
        await db_session.commit()

        # Add 5 products to the other org's leaflet
        other_products = []
        for i in range(5):
            product = Product(
                id=uuid4(),
                leaflet_id=other_leaflet.id,
                organization_id=other_org.id,
                page_number=1,
                product_name=f"Other Org Product {i}",
                brand="Other Brand",
                regular_price=9.99,
                currency="EUR",
                confidence=0.9,
                review_status=ReviewStatus.PENDING,
                validation_passed=True,
            )
            other_products.append(product)

        db_session.add_all(other_products)
        await db_session.commit()

        # Get our org's leaflet detail - should only count our products (30)
        response = await client.get(
            f"/api/v1/leaflets/{perf_leaflet.id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["products_count"] == 30, (
            f"Should only count test org's products (30), "
            f"not include other org's products (5)"
        )

        # Verify our org can't access the other org's leaflet
        response_other = await client.get(
            f"/api/v1/leaflets/{other_leaflet.id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response_other.status_code == 404, (
            "User should not be able to access other organization's leaflet"
        )
