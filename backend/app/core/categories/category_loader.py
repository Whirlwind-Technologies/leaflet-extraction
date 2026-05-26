"""
Category Loader Module.

Loads and manages product categories from the database with caching.
"""

import logging
from typing import List, Optional, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_category import ProductCategory

logger = logging.getLogger(__name__)


class CategoryLoader:
    """
    Loads and caches product categories from the database.

    Categories are loaded on first access and cached.
    Call reload() to refresh from database.
    """

    def __init__(self):
        self._categories: List[ProductCategory] = []
        self._category_map: Dict[str, ProductCategory] = {}
        self._loaded = False

    def _load_categories_sync(self) -> None:
        """Load categories synchronously (for use in sync contexts like Celery)."""
        from app.utils.database import get_sync_db_session

        self._categories = []
        self._category_map = {}

        try:
            session = get_sync_db_session()
            try:
                # Use text-based query for sync session
                from sqlalchemy import text
                result = session.execute(
                    text("""
                        SELECT id, name, description, is_fallback, is_active, sort_order
                        FROM product_categories
                        WHERE is_active = true
                        ORDER BY sort_order, name
                    """)
                )
                rows = result.fetchall()

                for row in rows:
                    # Create a simple object to hold the data
                    cat = _CategoryData(
                        id=row[0],
                        name=row[1],
                        description=row[2],
                        is_fallback=row[3],
                        is_active=row[4],
                        sort_order=row[5],
                    )
                    self._categories.append(cat)
                    self._category_map[cat.name] = cat

                self._loaded = True
                logger.info(f"Loaded {len(self._categories)} categories from database (sync)")
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Failed to load categories from database: {e}")
            self._loaded = True  # Mark as loaded to prevent repeated failures

    async def _load_categories_async(self, db: AsyncSession) -> None:
        """Load categories asynchronously."""
        self._categories = []
        self._category_map = {}

        try:
            result = await db.execute(
                select(ProductCategory)
                .where(ProductCategory.is_active == True)
                .order_by(ProductCategory.sort_order, ProductCategory.name)
            )
            categories = result.scalars().all()

            for cat in categories:
                self._categories.append(cat)
                self._category_map[cat.name] = cat

            self._loaded = True
            logger.info(f"Loaded {len(self._categories)} categories from database (async)")
        except Exception as e:
            logger.error(f"Failed to load categories from database: {e}")
            self._loaded = True

    def _ensure_loaded(self) -> None:
        """Ensure categories are loaded."""
        if not self._loaded:
            self._load_categories_sync()

    def reload(self) -> int:
        """Reload categories from database. Returns count of loaded categories."""
        self._loaded = False
        self._load_categories_sync()
        return len(self._categories)

    async def reload_async(self, db: AsyncSession) -> int:
        """Reload categories from database asynchronously."""
        self._loaded = False
        await self._load_categories_async(db)
        return len(self._categories)

    @property
    def categories(self) -> List:
        """Get all categories."""
        self._ensure_loaded()
        return self._categories

    @property
    def category_names(self) -> List[str]:
        """Get list of category names."""
        self._ensure_loaded()
        return [c.name for c in self._categories]

    @property
    def fallback_categories(self) -> List:
        """Get parent/fallback categories only."""
        self._ensure_loaded()
        return [c for c in self._categories if c.is_fallback]

    @property
    def specific_categories(self) -> List:
        """Get specific (non-fallback) categories."""
        self._ensure_loaded()
        return [c for c in self._categories if not c.is_fallback]

    def get_category(self, name: str):
        """Get category by name."""
        self._ensure_loaded()
        return self._category_map.get(name)

    def search(self, query: str, limit: int = 50) -> List:
        """Search categories by name or description (case-insensitive)."""
        self._ensure_loaded()

        if not query:
            return self._categories[:limit]

        query_lower = query.lower()
        matches = []

        # Prioritize name matches first
        for c in self._categories:
            if query_lower in c.name.lower():
                matches.append(c)

        # Then description matches (if not already in results)
        matched_names = {m.name for m in matches}
        for c in self._categories:
            if c.name not in matched_names:
                desc = c.description or ""
                if query_lower in desc.lower():
                    matches.append(c)

        return matches[:limit]

    def format_for_vlm_prompt(self, include_descriptions: bool = True, compact: bool = False) -> str:
        """
        Format categories for VLM prompt.

        Args:
            include_descriptions: If True, include full descriptions.
                                  If False, just list category names.
            compact: If True, use ultra-compact format (minimizes tokens).
                     Overrides include_descriptions.

        Returns:
            Formatted string for VLM prompt.
        """
        self._ensure_loaded()

        if not self._categories:
            return "No categories available"

        # Ultra-compact format for token optimization
        if compact:
            # Group categories by type, comma-separated
            specific = [c.name for c in self._categories if not c.is_fallback]
            fallback = [c.name for c in self._categories if c.is_fallback]

            lines = []
            if specific:
                # Split into chunks of ~20 categories per line for readability
                for i in range(0, len(specific), 20):
                    chunk = specific[i:i+20]
                    lines.append(", ".join(chunk))

            if fallback:
                lines.append("")
                lines.append(f"FALLBACK (if nothing else fits): {', '.join(fallback)}")

            return "\n".join(lines)

        if include_descriptions:
            # Separate specific and fallback categories for clearer guidance
            specific = [c for c in self._categories if not c.is_fallback]
            fallback = [c for c in self._categories if c.is_fallback]

            lines = []

            if specific:
                lines.append("SPECIFIC CATEGORIES (prefer these):")
                for cat in specific:
                    lines.append(f"  - {cat.name}: {cat.description or ''}")

            if fallback:
                lines.append("")
                lines.append("FALLBACK CATEGORIES (use only when no specific category matches):")
                for cat in fallback:
                    lines.append(f"  - {cat.name}: {cat.description or ''}")

            lines.append("")
            lines.append("IMPORTANT: Return ONLY the category name (e.g., \"Table Salt\"), not the description or any labels.")

            return "\n".join(lines)
        else:
            return ", ".join(self.category_names)

    def __len__(self) -> int:
        self._ensure_loaded()
        return len(self._categories)


class _CategoryData:
    """Simple data class for category data when loaded via raw SQL."""

    def __init__(self, id, name, description, is_fallback, is_active, sort_order):
        self.id = id
        self.name = name
        self.description = description
        self.is_fallback = is_fallback
        self.is_active = is_active
        self.sort_order = sort_order

    @property
    def vlm_format(self) -> str:
        """Format for VLM prompt with guidance."""
        return f"  - {self.name}: {self.description or ''}"


# Cached singleton instance
_category_loader: Optional[CategoryLoader] = None


def get_category_loader() -> CategoryLoader:
    """Get cached category loader instance."""
    global _category_loader
    if _category_loader is None:
        _category_loader = CategoryLoader()
    return _category_loader


def reload_category_loader() -> int:
    """Reload the category loader. Returns count of loaded categories."""
    global _category_loader
    if _category_loader is not None:
        return _category_loader.reload()
    else:
        _category_loader = CategoryLoader()
        return len(_category_loader)
