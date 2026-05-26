#!/usr/bin/env python3
"""
Seed Product Categories Script

Imports product categories from CSV file into the database.
Detects fallback categories and sets up hierarchical relationships.

Usage:
    python scripts/seed_categories.py

Or via Docker:
    docker-compose exec backend python scripts/seed_categories.py

Options:
    --clear     Clear existing categories before seeding
    --csv PATH  Path to CSV file (default: /app/product_categories.csv)
"""

import argparse
import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.models.product_category import ProductCategory


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Seed product categories from CSV")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing categories before seeding",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="/app/product_categories.csv",
        help="Path to CSV file",
    )
    return parser.parse_args()


def is_fallback_category(description: str) -> bool:
    """Check if category is a fallback category based on description."""
    if not description:
        return False
    desc_lower = description.lower()
    return "fallback category" in desc_lower or "fallback —" in desc_lower


async def seed_categories(csv_path: str, clear: bool = False) -> None:
    """
    Seed categories from CSV file.

    Args:
        csv_path: Path to the CSV file
        clear: If True, delete existing categories first
    """
    print("=" * 60)
    print("LeafXtract - Seed Product Categories")
    print("=" * 60)
    print()

    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"Error: CSV file not found at {csv_path}")
        sys.exit(1)

    print(f"Reading categories from: {csv_path}")

    # Read CSV file
    categories_data = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Category", "").strip()
            description = row.get("Description", "").strip()

            if not name:
                continue

            categories_data.append({
                "name": name,
                "description": description,
                "is_fallback": is_fallback_category(description),
            })

    print(f"Found {len(categories_data)} categories in CSV")

    # Count fallback categories
    fallback_count = sum(1 for c in categories_data if c["is_fallback"])
    specific_count = len(categories_data) - fallback_count
    print(f"  - Specific categories: {specific_count}")
    print(f"  - Fallback categories: {fallback_count}")
    print()

    # Create database engine and session
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as db:
        # Clear existing categories if requested
        if clear:
            print("Clearing existing categories...")
            await db.execute(delete(ProductCategory))
            await db.commit()
            print("  Done.")
            print()

        # Check for existing categories
        result = await db.execute(select(ProductCategory.name))
        existing_names = {row[0] for row in result.fetchall()}

        if existing_names:
            print(f"Found {len(existing_names)} existing categories in database")

        # Insert new categories
        inserted = 0
        skipped = 0

        for idx, cat_data in enumerate(categories_data):
            if cat_data["name"] in existing_names:
                skipped += 1
                continue

            category = ProductCategory(
                name=cat_data["name"],
                description=cat_data["description"],
                is_fallback=cat_data["is_fallback"],
                is_active=True,
                sort_order=idx,
            )
            db.add(category)
            inserted += 1

        await db.commit()

        print(f"Inserted {inserted} new categories")
        if skipped > 0:
            print(f"Skipped {skipped} existing categories")

        # Verify count
        result = await db.execute(select(ProductCategory))
        all_categories = result.scalars().all()

        print()
        print("=" * 60)
        print(f"Total categories in database: {len(all_categories)}")
        print("=" * 60)
        print()

        # Show sample categories
        print("Sample categories:")
        for cat in all_categories[:5]:
            fallback_marker = " [FALLBACK]" if cat.is_fallback else ""
            print(f"  - {cat.name}{fallback_marker}")
        if len(all_categories) > 5:
            print(f"  ... and {len(all_categories) - 5} more")
        print()


if __name__ == "__main__":
    args = parse_args()

    try:
        asyncio.run(seed_categories(args.csv, args.clear))
    except KeyboardInterrupt:
        print("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
