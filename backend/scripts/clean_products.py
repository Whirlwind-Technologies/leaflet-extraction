#!/usr/bin/env python3
"""
Clean all products from the database.
Use this script during development to reset product data.
"""
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.product import Product
from app.models.leaflet import Leaflet


def get_db_session():
    """Get a database session."""
    engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def clean_products():
    """Delete all products and reset leaflet counters."""
    db = get_db_session()
    try:
        # Delete all products
        deleted_count = db.query(Product).delete()
        print(f"Deleted {deleted_count} products")

        # Reset leaflet product counts
        db.execute(
            text("""
                UPDATE leaflets
                SET products_count = 0,
                    auto_approved_count = 0,
                    review_required_count = 0,
                    overall_confidence = NULL
            """)
        )

        # Reset leaflet page product counts
        db.execute(
            text("""
                UPDATE leaflet_pages
                SET products_count = 0,
                    is_processed = FALSE
            """)
        )

        db.commit()
        print("✓ Successfully cleaned all products and reset leaflet counters")

    except Exception as e:
        db.rollback()
        print(f"✗ Error cleaning products: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("CLEANING ALL PRODUCTS FROM DATABASE")
    print("=" * 60)

    response = input("This will delete ALL products. Continue? (yes/no): ")
    if response.lower() == "yes":
        clean_products()
    else:
        print("Cancelled.")
