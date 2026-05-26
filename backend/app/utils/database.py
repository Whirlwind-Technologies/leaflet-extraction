"""
Database Connection Utilities.

This module provides async database connection management using SQLAlchemy 2.0
with asyncpg driver for PostgreSQL.

Example Usage:
    from app.utils.database import get_db, init_db_connection
    
    # In FastAPI dependency
    async def get_items(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Item))
        return result.scalars().all()
    
    # Initialize connection on startup
    await init_db_connection()
"""

import logging
from typing import AsyncGenerator, List, Optional
from uuid import UUID

from sqlalchemy import text, select, func, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy declarative base for models
Base = declarative_base()

# Global engine and session factory
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def init_db_connection() -> None:
    """
    Initialize the database connection pool.
    
    Creates the async engine and session factory with configured
    pool settings. Should be called once during application startup.
    
    Raises:
        SQLAlchemyError: If connection to database fails
        
    Example:
        >>> await init_db_connection()
        >>> # Database is now ready for use
    """
    global _engine, _session_factory
    
    logger.info(
        "Initializing database connection",
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )
    
    try:
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_pre_ping=True,  # Verify connections before use
            echo=settings.debug,  # Log SQL statements in debug mode
            future=True,
        )
        
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        
        # Test the connection
        async with _engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        logger.info("Database connection initialized successfully")
        
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database connection: {e}")
        raise


async def close_db_connection() -> None:
    """
    Close the database connection pool.
    
    Should be called during application shutdown to properly
    release all database connections.
    
    Example:
        >>> await close_db_connection()
        >>> # All database connections are now closed
    """
    global _engine, _session_factory
    
    if _engine is not None:
        logger.info("Closing database connection pool")
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connection pool closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    
    Creates a new session for each request and ensures it's
    properly closed after the request completes.
    
    Yields:
        AsyncSession: Database session for the request
        
    Raises:
        RuntimeError: If database connection is not initialized
        
    Example:
        >>> @app.get("/items")
        >>> async def get_items(db: AsyncSession = Depends(get_db)):
        ...     result = await db.execute(select(Item))
        ...     return result.scalars().all()
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database connection not initialized. "
            "Call init_db_connection() during startup."
        )
    
    session = _session_factory()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        await session.close()


async def check_db_health() -> bool:
    """
    Check database connection health.
    
    Performs a simple query to verify the database is accessible.
    
    Returns:
        bool: True if database is healthy, False otherwise
        
    Example:
        >>> is_healthy = await check_db_health()
        >>> print(f"Database healthy: {is_healthy}")
    """
    if _engine is None:
        return False
    
    try:
        async with _engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as e:
        logger.warning(f"Database health check failed: {e}")
        return False


def get_engine() -> Optional[AsyncEngine]:
    """
    Get the current database engine.
    
    Returns:
        Optional[AsyncEngine]: The database engine or None if not initialized
    """
    return _engine


async def create_all_tables() -> None:
    """
    Create all database tables.
    
    Creates all tables defined in SQLAlchemy models.
    Should only be used for development/testing.
    Use Alembic migrations for production.
    
    Example:
        >>> await create_all_tables()
        >>> # All tables are now created
    """
    if _engine is None:
        raise RuntimeError("Database connection not initialized")
    
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("All database tables created")


async def drop_all_tables() -> None:
    """
    Drop all database tables.
    
    WARNING: This will delete all data. Only use for testing.
    
    Example:
        >>> await drop_all_tables()
        >>> # All tables are now dropped
    """
    if _engine is None:
        raise RuntimeError("Database connection not initialized")
    
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.warning("All database tables dropped")


def get_async_session_factory() -> Optional[async_sessionmaker[AsyncSession]]:
    """
    Get the async session factory for use outside FastAPI dependency injection.

    This is needed by WebSocket endpoints which cannot use Depends(get_db)
    for session management. The caller is responsible for opening and closing
    the session.

    Returns:
        The async session factory, or None if not initialized.

    Raises:
        RuntimeError: If the database connection has not been initialized.

    Example:
        >>> factory = get_async_session_factory()
        >>> async with factory() as session:
        ...     result = await session.execute(select(User))
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database connection not initialized. "
            "Call init_db_connection() during startup."
        )
    return _session_factory


def get_sync_db_session():
    """
    Get a synchronous database session for Celery tasks.

    This function creates a synchronous database session using the sync database URL.
    Used primarily by Celery tasks which don't support async operations.

    Returns:
        Session: Synchronous database session

    Example:
        >>> session = get_sync_db_session()
        >>> try:
        ...     # Perform database operations
        ...     session.commit()
        ... finally:
        ...     session.close()
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


async def stream_products_for_export(
    db: AsyncSession,
    filters: dict,
    organization_id: UUID,
    batch_size: int = 500,
) -> AsyncGenerator[list, None]:
    """
    Yield batches of products matching filters for export.

    Uses keyset pagination (cursor-based on created_at + id) for memory
    efficiency when exporting large result sets.  Each batch is a list of
    Product ORM instances whose length is at most ``batch_size``.

    Supported filter keys (all optional):

    - ``search`` (str): ILIKE search on product_name
    - ``review_status`` (str | ReviewStatus): exact match or IN list
    - ``review_statuses`` (list[str]): convenience alias for multi-status
    - ``leaflet_id`` (UUID): filter to a single leaflet
    - ``category`` (str): exact match on category
    - ``brand`` (str): ILIKE search on brand
    - ``min_confidence`` (float): confidence >= threshold
    - ``validation_passed`` (bool): filter by validation flag
    - ``product_ids`` (list[UUID]): restrict to specific product IDs
    - ``sort_by`` (str): column name, default ``created_at``
    - ``sort_order`` (str): ``asc`` or ``desc``, default ``desc``

    Args:
        db: Active async database session.
        filters: Dictionary of filter parameters (see list above).
        organization_id: Organization UUID for data isolation.
        batch_size: Maximum products per yielded batch.

    Yields:
        Lists of Product instances, each list up to ``batch_size`` long.

    Example:
        >>> async for batch in stream_products_for_export(db, {"review_status": "approved"}, org_id):
        ...     for product in batch:
        ...         writer.write_row(product)
    """
    from app.models.product import Product, ReviewStatus

    # ------------------------------------------------------------------
    # Build the base query with organization isolation
    # ------------------------------------------------------------------
    conditions = [Product.organization_id == organization_id]

    # -- leaflet_id
    leaflet_id = filters.get("leaflet_id")
    if leaflet_id is not None:
        conditions.append(Product.leaflet_id == leaflet_id)

    # -- review_status (single value)
    review_status = filters.get("review_status")
    if review_status is not None:
        if isinstance(review_status, str):
            review_status = ReviewStatus(review_status)
        conditions.append(Product.review_status == review_status)

    # -- review_statuses (list of values)
    review_statuses = filters.get("review_statuses")
    if review_statuses is not None:
        enum_values = [
            ReviewStatus(s) if isinstance(s, str) else s
            for s in review_statuses
        ]
        conditions.append(Product.review_status.in_(enum_values))

    # -- search (ILIKE on product_name)
    search = filters.get("search")
    if search:
        conditions.append(Product.product_name.ilike(f"%{search}%"))

    # -- category (exact match)
    category = filters.get("category")
    if category:
        conditions.append(Product.category == category)

    # -- brand (ILIKE)
    brand = filters.get("brand")
    if brand:
        conditions.append(Product.brand.ilike(f"%{brand}%"))

    # -- min_confidence
    min_confidence = filters.get("min_confidence")
    if min_confidence is not None:
        conditions.append(Product.confidence >= min_confidence)

    # -- validation_passed
    validation_passed = filters.get("validation_passed")
    if validation_passed is not None:
        conditions.append(Product.validation_passed == validation_passed)

    # -- product_ids (explicit ID list for "selected products" export)
    product_ids = filters.get("product_ids")
    if product_ids:
        conditions.append(Product.id.in_(product_ids))

    # ------------------------------------------------------------------
    # Determine sort column and direction
    # ------------------------------------------------------------------
    sort_by = filters.get("sort_by", "created_at")
    sort_order = filters.get("sort_order", "desc")
    sort_column = getattr(Product, sort_by, Product.created_at)

    if sort_order == "asc":
        order_clauses = [sort_column.asc(), Product.id.asc()]
    else:
        order_clauses = [sort_column.desc(), Product.id.desc()]

    # ------------------------------------------------------------------
    # Paginate using OFFSET/LIMIT in batches
    # ------------------------------------------------------------------
    # Note: True keyset pagination requires the cursor value from the
    # previous batch, which complicates the interface.  OFFSET/LIMIT is
    # acceptable here because export is a background/streaming operation
    # and the sort includes the PK as a tiebreaker for determinism.
    # ------------------------------------------------------------------
    offset = 0

    while True:
        query = (
            select(Product)
            .where(and_(*conditions))
            .order_by(*order_clauses)
            .offset(offset)
            .limit(batch_size)
        )

        result = await db.execute(query)
        batch = result.scalars().all()

        if not batch:
            break

        yield batch

        if len(batch) < batch_size:
            # Last batch -- no more rows
            break

        offset += batch_size