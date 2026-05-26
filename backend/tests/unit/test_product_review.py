"""
Unit Tests for Product Review Endpoint.

Tests the product review API endpoint (/api/v1/products/{id}/review)
including approval, rejection (with/without notes), and correction workflows.

Critical areas tested:
1. Review endpoint accepts rejection with notes
2. Review endpoint accepts rejection without notes (backward compat)
3. Review endpoint accepts approval
4. Review endpoint accepts corrected status
5. Notes are properly stored in product_reviews table
6. Product review_status changes correctly based on action
7. ProductReview records are created with correct data
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leaflet import Leaflet, LeafletStatus, LeafletPage
from app.models.product import Product, ProductReview, ReviewStatus
from app.models.organization import Organization
from app.models.user import User


@pytest.fixture
async def test_leaflet(
    db_session: AsyncSession,
    test_organization: Organization,
) -> Leaflet:
    """Create a test leaflet for product review tests."""
    leaflet = Leaflet(
        id=uuid4(),
        organization_id=test_organization.id,
        leaflet_id=f"LEAF_2025_{uuid4().hex[:6].upper()}",
        filename="test_leaflet.pdf",
        status=LeafletStatus.COMPLETED,
        page_count=1,
    )

    db_session.add(leaflet)
    await db_session.commit()
    await db_session.refresh(leaflet)

    # Create a page for the leaflet
    page = LeafletPage(
        id=uuid4(),
        leaflet_id=leaflet.id,
        page_number=1,
        image_path=f"leaflets/{leaflet.leaflet_id}/pages/page_001.png",
        thumbnail_path=f"leaflets/{leaflet.leaflet_id}/thumbnails/page_001_thumb.jpg",
    )
    db_session.add(page)
    await db_session.commit()

    return leaflet


@pytest.fixture
async def test_product(
    db_session: AsyncSession,
    test_leaflet: Leaflet,
    test_organization: Organization,
) -> Product:
    """Create a test product for review tests."""
    product = Product(
        id=uuid4(),
        leaflet_id=test_leaflet.id,
        organization_id=test_organization.id,
        page_number=1,
        product_name="Test Product",
        brand="Test Brand",
        product_code="TEST-001",
        regular_price=9.99,
        discounted_price=None,
        discount_percentage=None,
        currency="EUR",
        confidence=0.85,
        review_status=ReviewStatus.PENDING,
        bbox_x=100,
        bbox_y=100,
        bbox_width=200,
        bbox_height=200,
    )

    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    return product


class TestProductReview:
    """Tests for product review endpoint."""

    @pytest.mark.asyncio
    async def test_review_rejection_with_notes(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that review endpoint accepts rejection with notes.

        This verifies that when a user clicks "Reject" and provides a reason,
        the product is marked as REJECTED and the notes are stored.
        """
        # Submit rejection with notes
        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "rejected",
                "notes": "Duplicate product - same as page 3",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response
        assert data["id"] == str(test_product.id)
        assert data["review_status"] == "rejected"

        # Verify product updated in database
        await db_session.refresh(test_product)
        assert test_product.review_status == ReviewStatus.REJECTED
        assert test_product.review_notes == "Duplicate product - same as page 3"
        assert test_product.reviewed_by is not None
        assert test_product.reviewed_at is not None

        # Verify ProductReview record created
        result = await db_session.execute(
            select(ProductReview).where(ProductReview.product_id == test_product.id)
        )
        review = result.scalar_one_or_none()

        assert review is not None
        assert review.action == "rejected"
        assert review.notes == "Duplicate product - same as page 3"
        assert review.reviewer_id is not None

    @pytest.mark.asyncio
    async def test_review_rejection_without_notes(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that review endpoint accepts rejection without notes (backward compatibility).

        This ensures that rejection still works even if no notes are provided,
        maintaining backward compatibility with older frontend code.
        """
        # Submit rejection without notes
        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "rejected",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response
        assert data["id"] == str(test_product.id)
        assert data["review_status"] == "rejected"

        # Verify product updated in database
        await db_session.refresh(test_product)
        assert test_product.review_status == ReviewStatus.REJECTED
        assert test_product.review_notes is None
        assert test_product.reviewed_by is not None
        assert test_product.reviewed_at is not None

        # Verify ProductReview record created
        result = await db_session.execute(
            select(ProductReview).where(ProductReview.product_id == test_product.id)
        )
        review = result.scalar_one_or_none()

        assert review is not None
        assert review.action == "rejected"
        assert review.notes is None

    @pytest.mark.asyncio
    async def test_review_approval(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that review endpoint accepts approval.

        Verifies the approval workflow sets status to APPROVED
        and creates appropriate review record.
        """
        # Submit approval
        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "approved",
                "notes": "All data verified correct",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response
        assert data["id"] == str(test_product.id)
        assert data["review_status"] == "approved"

        # Verify product updated in database
        await db_session.refresh(test_product)
        assert test_product.review_status == ReviewStatus.APPROVED
        assert test_product.review_notes == "All data verified correct"
        assert test_product.reviewed_by is not None
        assert test_product.reviewed_at is not None

        # Verify ProductReview record created
        result = await db_session.execute(
            select(ProductReview).where(ProductReview.product_id == test_product.id)
        )
        review = result.scalar_one_or_none()

        assert review is not None
        assert review.action == "approved"
        assert review.notes == "All data verified correct"

    @pytest.mark.asyncio
    async def test_review_corrected(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that review endpoint accepts corrected status.

        Verifies that when user makes corrections and submits,
        the product is marked as APPROVED (corrected = approved with changes)
        and is_corrected flag is set.
        """
        # Submit with corrections
        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "corrected",
                "corrections": {
                    "regular_price": 12.99,
                },
                "notes": "Fixed price - was $9.99, should be $12.99",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response
        assert data["id"] == str(test_product.id)
        assert data["review_status"] == "approved"  # corrected = approved
        assert data["is_corrected"] is True

        # Verify product updated in database
        await db_session.refresh(test_product)
        assert test_product.review_status == ReviewStatus.APPROVED
        assert test_product.is_corrected is True
        assert test_product.regular_price == 12.99
        assert test_product.review_notes == "Fixed price - was $9.99, should be $12.99"

        # Verify ProductReview record created
        result = await db_session.execute(
            select(ProductReview).where(ProductReview.product_id == test_product.id)
        )
        review = result.scalar_one_or_none()

        assert review is not None
        assert review.action == "corrected"
        assert review.notes == "Fixed price - was $9.99, should be $12.99"
        assert "regular_price" in review.changed_fields

    @pytest.mark.asyncio
    async def test_review_approval_without_notes(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that approval works without notes.

        Notes should be optional for all review actions.
        """
        # Submit approval without notes
        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "approved",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response
        assert data["id"] == str(test_product.id)
        assert data["review_status"] == "approved"

        # Verify product updated in database
        await db_session.refresh(test_product)
        assert test_product.review_status == ReviewStatus.APPROVED
        assert test_product.review_notes is None

    @pytest.mark.asyncio
    async def test_review_with_bounding_box_correction(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that review accepts bounding box corrections.

        Verifies that bounding box adjustments are applied
        and tracked in the review record.
        """
        # Submit with bounding box correction
        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "corrected",
                "bounding_box": {
                    "x": 150,
                    "y": 150,
                    "width": 250,
                    "height": 250,
                },
                "notes": "Adjusted bounding box to include full product image",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify bounding box updated
        await db_session.refresh(test_product)
        assert test_product.bbox_x == 150
        assert test_product.bbox_y == 150
        assert test_product.bbox_width == 250
        assert test_product.bbox_height == 250

        # Verify review record includes bbox changes
        result = await db_session.execute(
            select(ProductReview).where(ProductReview.product_id == test_product.id)
        )
        review = result.scalar_one_or_none()

        assert review is not None
        assert "bbox_x" in review.changed_fields
        assert "bbox_y" in review.changed_fields
        assert "bbox_width" in review.changed_fields
        assert "bbox_height" in review.changed_fields

    @pytest.mark.asyncio
    async def test_review_invalid_action(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
    ):
        """
        Test that invalid review actions are rejected.

        Ensures schema validation catches invalid action values.
        """
        # Submit with invalid action
        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "invalid_action",
            },
        )

        # Should fail validation
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_review_nonexistent_product(
        self,
        client: AsyncClient,
        valid_token: str,
    ):
        """
        Test that reviewing non-existent product returns 404.

        Ensures proper error handling for invalid product IDs.
        """
        fake_product_id = uuid4()

        response = await client.post(
            f"/api/v1/products/{fake_product_id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "approved",
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_review_unauthorized(
        self,
        client: AsyncClient,
        test_product: Product,
    ):
        """
        Test that review requires authentication.

        Ensures unauthenticated requests are rejected.
        """
        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            json={
                "action": "approved",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_review_with_time_tracking(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that review time tracking is recorded.

        Verifies time_spent_seconds is stored in ProductReview record.
        """
        # Submit with time tracking
        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "approved",
                "time_spent_seconds": 45,
            },
        )

        assert response.status_code == 200

        # Verify time tracking in review record
        result = await db_session.execute(
            select(ProductReview).where(ProductReview.product_id == test_product.id)
        )
        review = result.scalar_one_or_none()

        assert review is not None
        assert review.time_spent_seconds == 45

    @pytest.mark.asyncio
    async def test_review_rejection_with_long_notes(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that rejection accepts long notes (>500 chars).

        Ensures the notes field can handle detailed rejection reasons.
        """
        long_notes = (
            "This product appears to be a duplicate of the item on page 3. "
            "The product code TEST-001 matches exactly, and the price is identical. "
            "The image also looks very similar. I checked both images side-by-side "
            "and confirmed they are the same product. This is likely a scanning artifact "
            "or a layout issue in the original PDF. Recommend removing this duplicate "
            "to avoid confusion in the final product database. The version on page 3 "
            "has a clearer image and should be the one retained."
        )

        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "rejected",
                "notes": long_notes,
            },
        )

        assert response.status_code == 200

        # Verify long notes stored correctly
        await db_session.refresh(test_product)
        assert test_product.review_notes == long_notes

        # Verify in review record
        result = await db_session.execute(
            select(ProductReview).where(ProductReview.product_id == test_product.id)
        )
        review = result.scalar_one_or_none()

        assert review is not None
        assert review.notes == long_notes
        assert len(review.notes) > 500

    @pytest.mark.asyncio
    async def test_review_needs_correction_status(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that review accepts needs_correction action.

        Verifies the needs_correction status is applied correctly
        (used for flagging products that need more work).
        """
        response = await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "needs_correction",
                "notes": "Price looks incorrect - please verify with original PDF",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify status
        assert data["review_status"] == "needs_correction"

        # Verify in database
        await db_session.refresh(test_product)
        assert test_product.review_status == ReviewStatus.NEEDS_CORRECTION


class TestProductReviewHistory:
    """Tests for product review history tracking."""

    @pytest.mark.asyncio
    async def test_review_creates_history_record(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that each review creates a ProductReview history record.

        Ensures audit trail is maintained for all review actions.
        """
        # First review - rejection
        await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "rejected",
                "notes": "Duplicate",
            },
        )

        # Check history
        result = await db_session.execute(
            select(ProductReview)
            .where(ProductReview.product_id == test_product.id)
            .order_by(ProductReview.created_at.desc())
        )
        reviews = result.scalars().all()

        assert len(reviews) == 1
        assert reviews[0].action == "rejected"
        assert reviews[0].notes == "Duplicate"

    @pytest.mark.asyncio
    async def test_review_stores_previous_data(
        self,
        client: AsyncClient,
        test_product: Product,
        valid_token: str,
        db_session: AsyncSession,
    ):
        """
        Test that review stores previous product data.

        Verifies that before/after data is captured for audit purposes.
        """
        original_price = test_product.regular_price

        # Submit correction
        await client.post(
            f"/api/v1/products/{test_product.id}/review",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={
                "action": "corrected",
                "corrections": {
                    "regular_price": 15.99,
                },
                "notes": "Price correction",
            },
        )

        # Check review record has previous data
        result = await db_session.execute(
            select(ProductReview).where(ProductReview.product_id == test_product.id)
        )
        review = result.scalar_one()

        assert review.previous_data is not None
        assert "regular_price" in review.previous_data
        # The previous_data stores prices as float for JSON compatibility
        assert float(review.previous_data["regular_price"]) == float(original_price)

        # Check new data
        assert review.new_data is not None
        assert review.new_data["regular_price"] == 15.99
