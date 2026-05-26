"""
Test script for product extraction from sample leaflet images.
Uses VLM provider configured in the database.
Run from backend directory: python scripts/test_extraction.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add the backend root to the path so app.* imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load environment for database connection
from dotenv import load_dotenv
load_dotenv()

from PIL import Image
from io import BytesIO


def get_db_provider():
    """Get VLM provider from database."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    from app.models.platform_vlm_provider import PlatformVLMProvider
    from app.models.vlm_provider import VLMProvider

    # Create sync engine
    db_url = settings.database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # First try platform providers (admin-configured)
        result = session.execute(
            select(PlatformVLMProvider)
            .where(PlatformVLMProvider.is_active == True)
            .order_by(PlatformVLMProvider.priority)
            .limit(1)
        )
        provider = result.scalar_one_or_none()

        if provider:
            print(f"Using Platform Provider: {provider.name} ({provider.provider_type})")
            # Detach from session so it can be used outside
            session.expunge(provider)
            return provider

        # Fall back to user VLM providers
        result = session.execute(
            select(VLMProvider)
            .where(VLMProvider.is_active == True)
            .order_by(VLMProvider.priority)
            .limit(1)
        )
        provider = result.scalar_one_or_none()

        if provider:
            print(f"Using User Provider: {provider.name} ({provider.provider_type})")
            session.expunge(provider)
            return provider

        return None

    finally:
        session.close()


async def test_extraction():
    """Test extraction on sample images."""
    from app.core.extraction.prompt_builder import PromptBuilder
    from app.core.extraction.schemas import ExtractionContext
    from app.core.extraction.multi_provider_client import MultiProviderVLMClient

    # Get provider from database
    provider = get_db_provider()

    if not provider:
        print("ERROR: No active VLM provider found in database")
        print("Please configure a VLM provider in the Settings page or Admin panel")
        return

    print(f"Provider Type: {provider.provider_type}")
    print(f"Model: {provider.model_name}")
    print("=" * 60)

    # Initialize client with provider object
    client = MultiProviderVLMClient(provider)

    # Sample images directory
    leaflets_dir = Path(__file__).parent.parent / "leaflets"

    if not leaflets_dir.exists():
        print(f"ERROR: Leaflets directory not found: {leaflets_dir}")
        return

    # Get all PNG images
    images = list(leaflets_dir.glob("*.png"))
    if not images:
        print(f"ERROR: No PNG images found in {leaflets_dir}")
        return

    print(f"Found {len(images)} images to test")

    # Test first image only (to save API costs)
    test_image = images[0]
    print(f"\nTesting: {test_image.name}")
    print("-" * 40)

    # Load image and get dimensions
    with Image.open(test_image) as img:
        image_width, image_height = img.size
        print(f"Image dimensions: {image_width} x {image_height}")

        # Convert to bytes for API
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

    # Build context
    context = ExtractionContext(
        leaflet_id="TEST_001",
        retailer="SPAR",
        country="SI",
        currency="EUR",
        image_width=image_width,
        image_height=image_height
    )

    # Build prompt
    builder = PromptBuilder()
    prompt = builder.build_extraction_prompt(
        page_number=1,
        total_pages=1,
        context=context
    )

    print(f"Prompt length: {len(prompt)} characters")
    print("\nSending to VLM API...")

    try:
        # Call VLM
        result = await client.extract_from_image(
            image_data=image_bytes,
            prompt=prompt,
            media_type="image/png"
        )

        print(f"\nAPI Response received!")
        print(f"Input tokens: {result.input_tokens}")
        print(f"Output tokens: {result.output_tokens}")
        print(f"Cost: ${result.cost:.4f}")

        # Parse response
        response_text = result.content

        # Try to extract JSON from response
        try:
            # Find JSON in response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                print(f"\n{'=' * 60}")
                print("EXTRACTION RESULTS")
                print(f"{'=' * 60}")

                products = data.get("products", [])
                print(f"\nProducts found: {len(products)}")

                for i, product in enumerate(products, 1):
                    print(f"\n{'─' * 50}")
                    print(f"PRODUCT {i}")
                    print(f"{'─' * 50}")

                    bbox = product.get("bounding_box", {})
                    print(f"📦 Bounding Box:")
                    print(f"   x={bbox.get('x')}, y={bbox.get('y')}")
                    print(f"   width={bbox.get('width')}, height={bbox.get('height')}")

                    if product.get("bbox_reasoning"):
                        print(f"📝 BBox Reasoning: {product.get('bbox_reasoning')}")

                    print(f"🏷️  Brand: {product.get('brand')}")
                    print(f"📦 Product: {product.get('product_name')}")

                    if product.get('regular_price'):
                        print(f"💰 Regular Price: €{product.get('regular_price')}")
                    print(f"💵 Discounted Price: €{product.get('discounted_price')}")

                    if product.get('discount_percentage'):
                        print(f"🔖 Discount: {product.get('discount_percentage')}%")

                    print(f"📁 Category: {product.get('suggested_category')}")
                    print(f"✅ Confidence: {product.get('confidence_score')}")

                    # Validate bounding box size
                    min_width = image_width // 8
                    min_height = image_height // 10
                    bbox_width = bbox.get('width', 0)
                    bbox_height = bbox.get('height', 0)

                    if bbox_width < min_width or bbox_height < min_height:
                        print(f"⚠️  WARNING: Bounding box may be too small!")
                        print(f"   Got: {bbox_width}x{bbox_height}, Min: {min_width}x{min_height}")
                    else:
                        print(f"✓ Bounding box size OK ({bbox_width}x{bbox_height})")

                if data.get("page_notes"):
                    print(f"\n📋 Page Notes: {data.get('page_notes')}")

                # Summary
                print(f"\n{'=' * 60}")
                print("SUMMARY")
                print(f"{'=' * 60}")
                print(f"Total products extracted: {len(products)}")

                valid_boxes = sum(1 for p in products
                                  if p.get('bounding_box', {}).get('width', 0) >= min_width
                                  and p.get('bounding_box', {}).get('height', 0) >= min_height)
                print(f"Valid bounding boxes: {valid_boxes}/{len(products)}")

                avg_confidence = sum(p.get('confidence_score', 0) for p in products) / len(products) if products else 0
                print(f"Average confidence: {avg_confidence:.2f}")

            else:
                print("\nERROR: Could not find JSON in response")
                print(f"Response preview: {response_text[:500]}...")

        except json.JSONDecodeError as e:
            print(f"\nERROR: Failed to parse JSON: {e}")
            print(f"Response preview: {response_text[:500]}...")

    except Exception as e:
        print(f"\nERROR: API call failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_extraction())
