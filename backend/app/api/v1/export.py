"""
Export API Endpoints.

This module provides endpoints for exporting leaflet data
in various formats (JSON, CSV, Excel).

Example Usage:
    GET /api/v1/export/{leaflet_id} - Export leaflet data
    GET /api/v1/export/{leaflet_id}/csv - Export as CSV
    GET /api/v1/export/{leaflet_id}/json - Export as JSON
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_export, get_current_organization, get_db
from app.models.leaflet import Leaflet
from app.models.organization import Organization
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductExportParams
from app.utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/{leaflet_id}",
    summary="Export leaflet data",
    description="Export leaflet data for the current organization in the specified format.",
)
async def export_leaflet(
    leaflet_id: str,
    format: str = Query("json", pattern="^(json|csv)$", description="Export format"),
    image_storage: str = Query(
        "url",
        pattern="^(base64|url|both|none)$",
        description="Image storage preference"
    ),
    include_product_codes: bool = Query(True, description="Include product codes"),
    current_user: User = Depends(require_export),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """
    Export leaflet data for the current organization.

    Args:
        leaflet_id: Leaflet ID (human-readable or UUID)
        format: Export format (json or csv)
        image_storage: How to include images
        include_product_codes: Include product codes
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Exported data in requested format

    Raises:
        NotFoundError: If leaflet not found or not accessible
    """
    # Find leaflet - filter by organization for data isolation
    # Super users can access all leaflets across all organizations
    if current_user.is_superuser:
        query = select(Leaflet)
    else:
        query = select(Leaflet).where(Leaflet.organization_id == current_org.id)

    try:
        uuid_id = UUID(leaflet_id)
        query = query.where(Leaflet.id == uuid_id)
    except ValueError:
        query = query.where(Leaflet.leaflet_id == leaflet_id)
    
    result = await db.execute(query)
    leaflet = result.scalar_one_or_none()
    
    if leaflet is None:
        raise NotFoundError("Leaflet", leaflet_id)
    
    # Get products
    products_result = await db.execute(
        select(Product)
        .where(Product.leaflet_id == leaflet.id)
        .order_by(Product.page_number, Product.bbox_y)
    )
    products = products_result.scalars().all()
    
    # Export based on format
    if format == "json":
        return await _export_json(leaflet, products, image_storage, include_product_codes)
    elif format == "csv":
        return await _export_csv(leaflet, products, image_storage, include_product_codes)


async def _export_json(
    leaflet: Leaflet,
    products: list,
    image_storage: str,
    include_product_codes: bool,
) -> dict:
    """Export as JSON."""
    export_data = {
        "leaflet_id": leaflet.leaflet_id,
        "processed_date": datetime.utcnow().isoformat(),
        "total_pages": leaflet.page_count,
        "total_products": len(products),
        "retailer": leaflet.retailer,
        "country": leaflet.country,
        "language": leaflet.language,
        "currency": leaflet.currency,
        "products": [],
        "quality_metrics": {
            "overall_confidence": leaflet.overall_confidence,
            "auto_approved": leaflet.auto_approved_count,
            "human_reviewed": leaflet.review_required_count,
        }
    }
    
    for product in products:
        product_data = {
            "page": product.page_number,
            "brand": product.brand,
            "product_name": product.product_name,
            "quantity": product.quantity,
            "units": product.units,
            "regular_price": product.regular_price,
            "discounted_price": product.discounted_price,
            "discount_percentage": product.discount_percentage,
            "currency": product.currency,
            "product_id": product.product_id,
            "promotional_info": product.promotional_info,
            "bounding_box": {
                "x": product.bbox_x,
                "y": product.bbox_y,
                "width": product.bbox_width,
                "height": product.bbox_height,
            },
            "confidence": product.confidence,
        }
        
        if include_product_codes:
            product_data["product_code"] = product.product_code
        
        # Handle image storage
        if image_storage == "base64" and product.image_base64:
            product_data["image"] = {
                "storage_type": "base64",
                "data": product.image_base64,
                "format": product.image_format,
                "dimensions": {
                    "width": product.image_width,
                    "height": product.image_height,
                },
            }
        elif image_storage == "url" and product.image_url:
            product_data["image"] = {
                "storage_type": "url",
                "url": product.image_url,
                "format": product.image_format,
                "dimensions": {
                    "width": product.image_width,
                    "height": product.image_height,
                },
            }
        elif image_storage == "both":
            product_data["image"] = {
                "storage_type": "both",
                "data": product.image_base64,
                "url": product.image_url,
                "format": product.image_format,
                "dimensions": {
                    "width": product.image_width,
                    "height": product.image_height,
                },
            }
        
        export_data["products"].append(product_data)
    
    return export_data


async def _export_csv(
    leaflet: Leaflet,
    products: list,
    image_storage: str,
    include_product_codes: bool,
) -> StreamingResponse:
    """Export as CSV."""
    output = io.StringIO()
    
    # Define columns
    columns = [
        "Leaflet_ID", "Page", "Brand", "Product_Name", "Quantity", "Units",
        "Regular_Price", "Discounted_Price", "Discount_Percentage", "Currency",
        "Product_ID", "Promotional_Info", "BoundingBox_X", "BoundingBox_Y",
        "BoundingBox_Width", "BoundingBox_Height", "Confidence"
    ]
    
    if include_product_codes:
        columns.insert(3, "Product_Code")
    
    if image_storage in ["url", "both"]:
        columns.append("Image_URL")
    
    if image_storage in ["base64", "both"]:
        columns.append("Image_Base64")
    
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    
    for product in products:
        row = {
            "Leaflet_ID": leaflet.leaflet_id,
            "Page": product.page_number,
            "Brand": product.brand or "",
            "Product_Name": product.product_name,
            "Quantity": product.quantity or "",
            "Units": product.units or "",
            "Regular_Price": product.regular_price or "",
            "Discounted_Price": product.discounted_price or "",
            "Discount_Percentage": product.discount_percentage or "",
            "Currency": product.currency or "",
            "Product_ID": product.product_id or "",
            "Promotional_Info": product.promotional_info or "",
            "BoundingBox_X": product.bbox_x,
            "BoundingBox_Y": product.bbox_y,
            "BoundingBox_Width": product.bbox_width,
            "BoundingBox_Height": product.bbox_height,
            "Confidence": product.confidence or "",
        }
        
        if include_product_codes:
            row["Product_Code"] = product.product_code or ""
        
        if image_storage in ["url", "both"]:
            row["Image_URL"] = product.image_url or ""
        
        if image_storage in ["base64", "both"]:
            row["Image_Base64"] = product.image_base64 or ""
        
        writer.writerow(row)
    
    output.seek(0)
    
    filename = f"{leaflet.leaflet_id}_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get(
    "/{leaflet_id}/json",
    summary="Export as JSON",
    description="Export leaflet data as JSON.",
)
async def export_json(
    leaflet_id: str,
    image_storage: str = Query("url", pattern="^(base64|url|both|none)$"),
    include_product_codes: bool = Query(True),
    current_user: User = Depends(require_export),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Export leaflet as JSON."""
    return await export_leaflet(
        leaflet_id=leaflet_id,
        format="json",
        image_storage=image_storage,
        include_product_codes=include_product_codes,
        current_user=current_user,
        current_org=current_org,
        db=db,
    )


@router.get(
    "/{leaflet_id}/csv",
    summary="Export as CSV",
    description="Export leaflet data as CSV file.",
)
async def export_csv(
    leaflet_id: str,
    image_storage: str = Query("url", pattern="^(base64|url|both|none)$"),
    include_product_codes: bool = Query(True),
    current_user: User = Depends(require_export),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export leaflet as CSV."""
    return await export_leaflet(
        leaflet_id=leaflet_id,
        format="csv",
        image_storage=image_storage,
        include_product_codes=include_product_codes,
        current_user=current_user,
        current_org=current_org,
        db=db,
    )