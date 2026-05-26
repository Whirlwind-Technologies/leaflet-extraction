"""
Product Validator Module.

This module provides comprehensive validation for extracted products,
orchestrating all validation rules and determining review routing.

Example Usage:
    from app.core.validation.validator import ProductValidator
    
    validator = ProductValidator()
    result = validator.validate(product, page_width=2304, page_height=3508)
    
    if result.auto_approve:
        print("Product can be auto-approved")
    elif not result.is_valid:
        print(f"Errors: {result.errors}")
"""

import logging
from typing import List, Optional

from app.config import settings

from app.core.extraction.schemas import (
    ExtractedProduct,
    ValidationError,
    ValidationResult,
)
from app.core.validation.rules import (
    validate_price,
    validate_discount,
    validate_quantity,
    validate_bounding_box,
    validate_product_code,
    validate_product_name,
    validate_currency,
)

logger = logging.getLogger(__name__)


class ProductValidator:
    """
    Comprehensive product validator.

    Orchestrates all validation rules and determines whether
    a product should be auto-approved, needs review, or has errors.

    Attributes:
        auto_approve_threshold: Minimum confidence for auto-approval
        strict_mode: Whether to treat warnings as errors
        category_confidence_threshold: Minimum category confidence for auto-approval

    Example:
        >>> validator = ProductValidator(auto_approve_threshold=0.90)
        >>> result = validator.validate(product)
        >>> print(result.auto_approve)  # True/False
    """

    # Default thresholds
    DEFAULT_AUTO_APPROVE_THRESHOLD = 0.90
    DEFAULT_MIN_CONFIDENCE = 0.50
    DEFAULT_CATEGORY_CONFIDENCE_THRESHOLD = 0.80

    def __init__(
        self,
        auto_approve_threshold: float = DEFAULT_AUTO_APPROVE_THRESHOLD,
        strict_mode: bool = False,
        expected_currency: Optional[str] = None,
        category_confidence_threshold: float = DEFAULT_CATEGORY_CONFIDENCE_THRESHOLD,
    ):
        """
        Initialize the validator.

        Args:
            auto_approve_threshold: Min confidence for auto-approval
            strict_mode: Treat warnings as errors
            expected_currency: Expected currency for leaflet
            category_confidence_threshold: Min category confidence for auto-approval
        """
        self.auto_approve_threshold = auto_approve_threshold
        self.strict_mode = strict_mode
        self.expected_currency = expected_currency
        self.category_confidence_threshold = category_confidence_threshold
    
    def validate(
        self,
        product: ExtractedProduct,
        page_width: int = 2304,
        page_height: int = 3508,
    ) -> ValidationResult:
        """
        Validate a single extracted product.
        
        Args:
            product: Product to validate
            page_width: Page width in pixels
            page_height: Page height in pixels
            
        Returns:
            ValidationResult with errors, warnings, and auto-approve flag
        """
        result = ValidationResult()
        
        # Run all validations
        self._validate_product_name(product, result)
        self._validate_prices(product, result)
        self._validate_discount(product, result)
        self._validate_quantity(product, result)
        self._validate_bounding_box(product, result, page_width, page_height)
        self._validate_product_code(product, result)
        self._validate_currency(product, result)
        self._validate_confidence(product, result)
        self._validate_category(product, result)
        self._check_uncertainty_flags(product, result)

        # Determine auto-approve status based on feature flag
        if settings.feature_auto_approval and result.is_valid and not result.warnings:
            if product.confidence_score >= self.auto_approve_threshold:
                # Also require category confidence >= threshold for auto-approval
                category_ok = (
                    product.category_confidence is None or  # No category = OK (backward compat)
                    product.category_confidence >= self.category_confidence_threshold
                )
                if category_ok:
                    result.auto_approve = True
        else:
            # Auto-approval disabled via feature flag or validation failed
            result.auto_approve = False

        return result
    
    def validate_batch(
        self,
        products: List[ExtractedProduct],
        page_width: int = 2304,
        page_height: int = 3508,
    ) -> List[ValidationResult]:
        """
        Validate a batch of products.
        
        Also checks for overlapping bounding boxes.
        
        Args:
            products: List of products to validate
            page_width: Page width in pixels
            page_height: Page height in pixels
            
        Returns:
            List of ValidationResults
        """
        results = []
        
        # Validate each product
        for product in products:
            result = self.validate(product, page_width, page_height)
            results.append(result)
        
        # Check for overlapping bounding boxes
        self._check_overlapping_boxes(products, results)
        
        # Check for duplicate products
        self._check_duplicates(products, results)
        
        return results
    
    def _validate_product_name(
        self,
        product: ExtractedProduct,
        result: ValidationResult,
    ):
        """Validate product name."""
        is_valid, error = validate_product_name(product.product_name)
        if not is_valid:
            result.add_error("product_name", "invalid", error, "high")
    
    def _validate_prices(
        self,
        product: ExtractedProduct,
        result: ValidationResult,
    ):
        """Validate price fields."""
        # Validate regular price
        is_valid, error = validate_price(
            product.regular_price,
            product.currency,
            "regular_price"
        )
        if not is_valid:
            result.add_error("regular_price", "invalid", error, "medium")
        
        # Validate discounted price
        is_valid, error = validate_price(
            product.discounted_price,
            product.currency,
            "discounted_price"
        )
        if not is_valid:
            result.add_error("discounted_price", "invalid", error, "medium")
        
        # Check that at least one price is present
        if product.regular_price is None and product.discounted_price is None:
            result.add_warning(
                "prices",
                "missing",
                "No price information found"
            )
    
    def _validate_discount(
        self,
        product: ExtractedProduct,
        result: ValidationResult,
    ):
        """Validate discount fields."""
        is_valid, error, warning = validate_discount(
            product.regular_price,
            product.discounted_price,
            product.discount_percentage,
        )
        
        if not is_valid:
            result.add_error("discount", "invalid", error, "medium")
        
        if warning:
            result.add_warning("discount", "mismatch", warning)
    
    def _validate_quantity(
        self,
        product: ExtractedProduct,
        result: ValidationResult,
    ):
        """Validate quantity and units."""
        is_valid, error = validate_quantity(product.quantity, product.units)
        if not is_valid:
            result.add_error("quantity", "invalid", error, "low")
    
    def _validate_bounding_box(
        self,
        product: ExtractedProduct,
        result: ValidationResult,
        page_width: int,
        page_height: int,
    ):
        """Validate bounding box."""
        is_valid, error = validate_bounding_box(
            product.bounding_box,
            page_width,
            page_height,
        )
        if not is_valid:
            result.add_error("bounding_box", "invalid", error, "medium")
    
    def _validate_product_code(
        self,
        product: ExtractedProduct,
        result: ValidationResult,
    ):
        """Validate product code."""
        is_valid, error = validate_product_code(product.product_code)
        if not is_valid:
            result.add_warning("product_code", "invalid", error)
    
    def _validate_currency(
        self,
        product: ExtractedProduct,
        result: ValidationResult,
    ):
        """Validate currency."""
        is_valid, error = validate_currency(
            product.currency,
            self.expected_currency,
        )
        if not is_valid:
            result.add_warning("currency", "invalid", error)
    
    def _validate_confidence(
        self,
        product: ExtractedProduct,
        result: ValidationResult,
    ):
        """Validate confidence scores."""
        if product.confidence_score < self.DEFAULT_MIN_CONFIDENCE:
            result.add_warning(
                "confidence",
                "low",
                f"Low confidence score ({product.confidence_score:.2f})"
            )
        
        # Check field confidence if available
        if product.field_confidence:
            fc = product.field_confidence
            
            # Flag very low field confidence
            low_confidence_fields = []
            for field_name in ["brand", "product_name", "discounted_price"]:
                score = getattr(fc, field_name, None)
                if score is not None and score < 0.70:
                    low_confidence_fields.append(f"{field_name} ({score:.2f})")
            
            if low_confidence_fields:
                result.add_warning(
                    "field_confidence",
                    "low",
                    f"Low confidence fields: {', '.join(low_confidence_fields)}"
                )
    
    def _validate_category(
        self,
        product: ExtractedProduct,
        result: ValidationResult,
    ):
        """Validate category confidence and add flags."""
        if product.category_confidence is not None:
            if product.category_confidence < self.category_confidence_threshold:
                result.add_warning(
                    "suggested_category",
                    "low_confidence",
                    f"Category confidence ({product.category_confidence:.2f}) below threshold ({self.category_confidence_threshold})"
                )
                # Add uncertainty flag for low category confidence
                if "CATEGORY_LOW_CONFIDENCE" not in product.uncertainty_flags:
                    product.uncertainty_flags.append("CATEGORY_LOW_CONFIDENCE")

    def _check_uncertainty_flags(
        self,
        product: ExtractedProduct,
        result: ValidationResult,
    ):
        """Check uncertainty flags from VLM."""
        critical_flags = [
            "price_unclear",
            "prices_swapped",
            "multiple_prices",
            "product_name_unclear",
            "CATEGORY_LOW_CONFIDENCE",
        ]

        for flag in product.uncertainty_flags:
            if flag in critical_flags:
                result.add_warning(
                    "uncertainty",
                    flag,
                    f"VLM flagged uncertainty: {flag}"
                )
            else:
                # Log but don't add warning for non-critical flags
                logger.debug(f"Uncertainty flag: {flag}")
    
    def _check_overlapping_boxes(
        self,
        products: List[ExtractedProduct],
        results: List[ValidationResult],
    ):
        """Check for overlapping bounding boxes between products."""
        for i, prod_i in enumerate(products):
            for j, prod_j in enumerate(products[i + 1:], i + 1):
                if prod_i.bounding_box.overlaps(prod_j.bounding_box):
                    # Calculate overlap percentage
                    overlap_warning = (
                        f"Bounding box overlaps with product "
                        f"'{prod_j.product_name[:30]}...'"
                    )
                    results[i].add_warning(
                        "bounding_box",
                        "overlap",
                        overlap_warning
                    )
    
    def _check_duplicates(
        self,
        products: List[ExtractedProduct],
        results: List[ValidationResult],
    ):
        """Check for potential duplicate products."""
        seen = {}
        
        for i, product in enumerate(products):
            # Create a key from product name and price
            key = (
                product.product_name.lower().strip()[:50],
                product.discounted_price,
            )
            
            if key in seen:
                results[i].add_warning(
                    "duplicate",
                    "potential_duplicate",
                    f"Potential duplicate of product at index {seen[key]}"
                )
            else:
                seen[key] = i


def determine_review_priority(
    product: ExtractedProduct,
    validation_result: ValidationResult,
) -> int:
    """
    Determine review priority for a product.
    
    Higher priority = more urgent review needed.
    
    Args:
        product: The product
        validation_result: Validation results
        
    Returns:
        Priority score (0-100, higher = more urgent)
    """
    priority = 0
    
    # Validation errors increase priority significantly
    priority += len(validation_result.errors) * 20
    
    # Warnings increase priority moderately
    priority += len(validation_result.warnings) * 5
    
    # Low confidence increases priority
    if product.confidence_score < 0.70:
        priority += 30
    elif product.confidence_score < 0.85:
        priority += 15
    
    # Uncertainty flags increase priority
    priority += len(product.uncertainty_flags) * 5
    
    # Missing important fields increase priority
    if product.discounted_price is None:
        priority += 10
    if not product.brand:
        priority += 5

    # Low category confidence increases priority
    if product.category_confidence is not None and product.category_confidence < 0.80:
        priority += 10

    # Cap at 100
    return min(priority, 100)