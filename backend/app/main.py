"""
Main FastAPI Application Entry Point.

This module initializes the FastAPI application with all middleware,
routes, exception handlers, and event handlers.

Example Usage:
    # Run with uvicorn
    uvicorn app.main:app --reload
    
    # Or programmatically
    import uvicorn
    from app.main import app
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

import csv
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Callable

import structlog
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as api_v1_router
from app.config import settings
from app.middleware.tenant_scope import TenantScopeMiddleware
from app.utils.database import close_db_connection, init_db_connection
from app.utils.cache import close_redis_connection, init_redis_connection

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.
    
    Handles startup and shutdown events for the application.
    Initializes database connections, Redis, and other services.
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None
    """
    # Startup
    logger.info(
        "Starting application",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    
    try:
        # Initialize database connection
        await init_db_connection()
        logger.info("Database connection initialized")
        
        # Initialize Redis connection
        await init_redis_connection()
        logger.info("Redis connection initialized")
        
        # Create storage directories
        settings.storage_base_path.mkdir(parents=True, exist_ok=True)
        (settings.storage_base_path / "uploads").mkdir(exist_ok=True)
        (settings.storage_base_path / "pages").mkdir(exist_ok=True)
        (settings.storage_base_path / "products").mkdir(exist_ok=True)
        (settings.storage_base_path / "thumbnails").mkdir(exist_ok=True)
        logger.info("Storage directories created", path=str(settings.storage_base_path))

        # Seed product categories if table is empty
        await _seed_categories_if_empty()

        logger.info("Application startup complete")
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down application")
        
        await close_db_connection()
        logger.info("Database connection closed")
        
        await close_redis_connection()
        logger.info("Redis connection closed")
        
        logger.info("Application shutdown complete")


async def _seed_categories_if_empty() -> None:
    """Seed product categories from CSV if the table is empty.

    This is an idempotent startup hook that only inserts categories when
    the ``product_categories`` table has zero rows.  Failures are logged
    but never block application startup.
    """
    from sqlalchemy import func, select as sa_select
    from sqlalchemy.exc import IntegrityError

    from app.models.product_category import ProductCategory
    from app.utils.database import get_async_session_factory

    try:
        session_factory = get_async_session_factory()
        async with session_factory() as db:
            try:
                # Check current row count
                result = await db.execute(
                    sa_select(func.count()).select_from(ProductCategory)
                )
                count = result.scalar_one()

                if count > 0:
                    logger.info(
                        "Categories already present, skipping seed",
                        categories_count=count,
                    )
                    return

                # Resolve the CSV path relative to this file (app/ directory)
                csv_path = Path(__file__).resolve().parent / "product_categories.csv"
                if not csv_path.exists():
                    logger.warning(
                        "Category CSV not found, skipping seed",
                        expected_path=str(csv_path),
                    )
                    return

                logger.info("Seeding product categories from CSV", csv_path=str(csv_path))

                # Read CSV and bulk-insert
                categories_to_add: list[ProductCategory] = []
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for idx, row in enumerate(reader):
                        name = row.get("Category", "").strip()
                        description = row.get("Description", "").strip()
                        if not name:
                            continue

                        is_fallback = (
                            "fallback category" in description.lower()
                            or "fallback —" in description.lower()
                        ) if description else False

                        categories_to_add.append(
                            ProductCategory(
                                name=name,
                                description=description,
                                is_fallback=is_fallback,
                                is_active=True,
                                sort_order=idx,
                            )
                        )

                db.add_all(categories_to_add)
                await db.commit()

                logger.info(
                    "Seeded product categories from CSV",
                    categories_seeded=len(categories_to_add),
                )

                # Reload the CategoryLoader singleton so the first VLM request
                # picks up the freshly seeded categories without a lazy DB hit.
                # Use a fresh session for reload to avoid detached ORM objects
                # from the seeding session above.
                from app.core.categories.category_loader import get_category_loader
                loader = get_category_loader()
                async with session_factory() as reload_db:
                    await loader.reload_async(reload_db)
            except IntegrityError:
                await db.rollback()
                logger.info("Categories already seeded by another worker, skipping")
    except Exception:
        logger.exception("Failed to seed product categories — startup continues")


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application instance
        
    Example:
        >>> app = create_application()
        >>> assert app.title == settings.app_name
    """
    app = FastAPI(
        title=settings.app_name,
        description=(
            "AI-Powered Leaflet Data Extraction Platform - "
            "Extract structured product data from promotional PDF leaflets "
            "using advanced vision-language models."
        ),
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )
    
    # Add middleware
    configure_middleware(app)
    
    # Add exception handlers
    configure_exception_handlers(app)
    
    # Include routers
    configure_routes(app)
    
    return app


def configure_middleware(app: FastAPI) -> None:
    """
    Configure application middleware.

    Args:
        app: FastAPI application instance
    """
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time", "X-Current-Organization"],
    )

    # Tenant scope middleware (for multi-tenant organization context)
    app.add_middleware(TenantScopeMiddleware)

    # GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Request logging and timing middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable) -> Response:
        """Log all incoming requests with timing information."""
        request_id = request.headers.get("X-Request-ID", str(time.time()))
        start_time = time.time()
        
        # Add request ID to state for access in routes
        request.state.request_id = request_id
        
        # Log incoming request
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Add headers to response
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"
            
            # Log completed request
            logger.info(
                "Request completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                process_time=process_time,
            )
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "Request failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                process_time=process_time,
            )
            raise


def configure_exception_handlers(app: FastAPI) -> None:
    """
    Configure global exception handlers.
    
    Args:
        app: FastAPI application instance
    """
    from app.utils.exceptions import (
        APIException,
        ValidationException,
        NotFoundError,
        AuthenticationError,
        AuthorizationError,
        RateLimitError,
    )
    
    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
        """Handle custom API exceptions."""
        logger.warning(
            "API exception",
            request_id=getattr(request.state, "request_id", "unknown"),
            error_code=exc.error_code,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
    
    @app.exception_handler(ValidationException)
    async def validation_exception_handler(
        request: Request, exc: ValidationException
    ) -> JSONResponse:
        """Handle validation exceptions."""
        logger.warning(
            "Validation error",
            request_id=getattr(request.state, "request_id", "unknown"),
            errors=exc.errors,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Validation failed",
                    "details": exc.errors,
                }
            },
        )
    
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        """Handle not found exceptions."""
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": exc.message,
                }
            },
        )
    
    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        """Handle authentication exceptions."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": exc.message,
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    @app.exception_handler(AuthorizationError)
    async def authz_error_handler(
        request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        """Handle authorization exceptions."""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": exc.message,
                }
            },
        )
    
    @app.exception_handler(RateLimitError)
    async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
        """Handle rate limit exceptions."""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": exc.message,
                    "retry_after": exc.retry_after,
                }
            },
            headers={"Retry-After": str(exc.retry_after)},
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.exception(
            "Unexpected error",
            request_id=getattr(request.state, "request_id", "unknown"),
            error=str(exc),
        )
        
        # In production, don't expose internal error details
        if settings.is_production:
            message = "An internal error occurred"
        else:
            message = str(exc)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": message,
                }
            },
        )


def configure_routes(app: FastAPI) -> None:
    """
    Configure application routes.
    
    Args:
        app: FastAPI application instance
    """
    # Health check endpoint
    @app.get(
        "/health",
        tags=["Health"],
        summary="Health Check",
        description="Check application health status",
    )
    async def health_check() -> dict:
        """
        Health check endpoint.
        
        Returns application health status including database
        and Redis connectivity.
        """
        from app.utils.database import check_db_health
        from app.utils.cache import check_redis_health
        
        db_healthy = await check_db_health()
        redis_healthy = await check_redis_health()
        
        status = "healthy" if (db_healthy and redis_healthy) else "degraded"
        
        return {
            "status": status,
            "version": settings.app_version,
            "environment": settings.environment,
            "database": "connected" if db_healthy else "disconnected",
            "redis": "connected" if redis_healthy else "disconnected",
            "timestamp": time.time(),
        }
    
    # Root endpoint
    @app.get(
        "/",
        tags=["Root"],
        summary="API Root",
        description="API information and available endpoints",
    )
    async def root() -> dict:
        """Root endpoint with API information."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "description": "AI-Powered Leaflet Data Extraction Platform",
            "documentation": "/docs" if settings.debug else "Contact support for API documentation",
            "health": "/health",
            "api": "/api/v1",
        }
    
    # Include API v1 router
    app.include_router(api_v1_router, prefix="/api/v1")


# Create application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=1 if settings.reload else settings.workers,
        log_level=settings.log_level.lower(),
    )