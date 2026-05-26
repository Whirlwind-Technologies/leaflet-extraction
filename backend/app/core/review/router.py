"""
Review Router Module.

Determines the review path for extracted products based on
confidence scores, validation results, and quality metrics.

Example Usage:
    from app.core.review.router import ReviewRouter
    
    router = ReviewRouter()
    decision = router.route_product(product, validation_result, quality_report)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from app.core.extraction.schemas import ExtractedProduct, ValidationResult
from app.core.image_processing.quality import QualityReport

logger = logging.getLogger(__name__)


class ReviewPath(str, Enum):
    """
    Review paths for products.
    
    Attributes:
        AUTO_APPROVE: Automatically approved, no review needed
        QUICK_REVIEW: Fast review for minor issues
        DETAILED_REVIEW: Full review for significant issues
        PRIORITY_REVIEW: Urgent review for critical issues
        REJECTED: Automatically rejected
    """
    AUTO_APPROVE = "auto_approve"
    QUICK_REVIEW = "quick_review"
    DETAILED_REVIEW = "detailed_review"
    PRIORITY_REVIEW = "priority_review"
    REJECTED = "rejected"


@dataclass
class ReviewDecision:
    """
    Review routing decision for a product.
    
    Attributes:
        path: Assigned review path
        priority: Review priority (0-100, higher = more urgent)
        reasons: Reasons for the decision
        auto_approved: Whether product was auto-approved
        flagged_fields: Fields requiring attention
        estimated_review_time: Estimated seconds for review
        confidence_factors: Breakdown of confidence factors
    """
    path: ReviewPath
    priority: int = 50
    reasons: List[str] = field(default_factory=list)
    auto_approved: bool = False
    flagged_fields: List[str] = field(default_factory=list)
    estimated_review_time: int = 0
    confidence_factors: Dict[str, float] = field(default_factory=dict)


class ReviewRouter:
    """
    Routes products to appropriate review paths.
    
    Uses a multi-factor decision algorithm considering:
    - VLM confidence scores
    - Validation results
    - Image quality metrics
    - Field-specific confidence
    - Uncertainty flags
    
    Attributes:
        auto_approve_threshold: Min confidence for auto-approval
        quick_review_threshold: Min confidence for quick review
        min_image_quality: Minimum acceptable image quality
        strict_mode: Whether to be more conservative
        
    Example:
        >>> router = ReviewRouter(auto_approve_threshold=0.90)
        >>> decision = router.route_product(product, validation_result)
        >>> if decision.auto_approved:
        ...     print("Product auto-approved!")
        >>> else:
        ...     print(f"Review path: {decision.path.value}")
    """
    
    # Default thresholds
    DEFAULT_AUTO_APPROVE = 0.90
    DEFAULT_QUICK_REVIEW = 0.75
    DEFAULT_MIN_IMAGE_QUALITY = 0.70
    
    # Field importance weights for priority calculation
    FIELD_WEIGHTS = {
        "product_name": 3.0,
        "discounted_price": 2.5,
        "regular_price": 2.0,
        "brand": 1.5,
        "quantity": 1.5,
        "units": 1.0,
        "product_code": 1.0,
        "discount_percentage": 1.0,
    }
    
    # Critical uncertainty flags
    CRITICAL_FLAGS = {
        "price_unclear",
        "prices_swapped",
        "multiple_prices",
        "product_name_unclear",
        "bounding_box_uncertain",
    }
    
    def __init__(
        self,
        auto_approve_threshold: float = DEFAULT_AUTO_APPROVE,
        quick_review_threshold: float = DEFAULT_QUICK_REVIEW,
        min_image_quality: float = DEFAULT_MIN_IMAGE_QUALITY,
        strict_mode: bool = False,
    ):
        """
        Initialize the review router.
        
        Args:
            auto_approve_threshold: Min confidence for auto-approval
            quick_review_threshold: Min confidence for quick review
            min_image_quality: Min image quality for auto-approval
            strict_mode: More conservative routing
        """
        self.auto_approve_threshold = auto_approve_threshold
        self.quick_review_threshold = quick_review_threshold
        self.min_image_quality = min_image_quality
        self.strict_mode = strict_mode
        
        if strict_mode:
            self.auto_approve_threshold = min(0.95, auto_approve_threshold + 0.05)
            self.quick_review_threshold = min(0.85, quick_review_threshold + 0.10)
    
    def route_product(
        self,
        product: ExtractedProduct,
        validation_result: Optional[ValidationResult] = None,
        quality_report: Optional[QualityReport] = None,
    ) -> ReviewDecision:
        """
        Determine the review path for a product.
        
        Args:
            product: Extracted product to route
            validation_result: Validation results (optional)
            quality_report: Image quality report (optional)
            
        Returns:
            ReviewDecision with routing details
        """
        reasons = []
        flagged_fields = []
        confidence_factors = {}
        
        # Collect all factors
        confidence_factors["vlm_confidence"] = product.confidence_score
        
        # Check validation results
        validation_passed = True
        if validation_result:
            validation_passed = validation_result.is_valid
            if not validation_passed:
                reasons.append(f"{len(validation_result.errors)} validation errors")
                flagged_fields.extend([e.field for e in validation_result.errors])
            
            if validation_result.warnings:
                reasons.append(f"{len(validation_result.warnings)} validation warnings")
                flagged_fields.extend([w.field for w in validation_result.warnings])
        
        # Check image quality
        image_quality_ok = True
        if quality_report:
            confidence_factors["image_quality"] = quality_report.overall_score
            if quality_report.overall_score < self.min_image_quality:
                image_quality_ok = False
                reasons.append(f"Low image quality ({quality_report.overall_score:.2f})")
            if quality_report.issues:
                reasons.extend(quality_report.issues[:2])  # Include top 2 issues
        
        # Check field confidence
        low_confidence_fields = self._check_field_confidence(product)
        if low_confidence_fields:
            flagged_fields.extend(low_confidence_fields)
            reasons.append(f"Low confidence: {', '.join(low_confidence_fields)}")
        
        # Check uncertainty flags
        critical_flags = self._check_uncertainty_flags(product)
        if critical_flags:
            reasons.append(f"Uncertainty flags: {', '.join(critical_flags)}")
        
        # Calculate effective confidence
        effective_confidence = self._calculate_effective_confidence(
            product.confidence_score,
            validation_result,
            quality_report,
        )
        confidence_factors["effective"] = effective_confidence
        
        # Make routing decision
        path, priority = self._determine_path(
            effective_confidence=effective_confidence,
            validation_passed=validation_passed,
            image_quality_ok=image_quality_ok,
            has_critical_flags=len(critical_flags) > 0,
            error_count=len(validation_result.errors) if validation_result else 0,
            warning_count=len(validation_result.warnings) if validation_result else 0,
        )
        
        # Calculate estimated review time
        review_time = self._estimate_review_time(path, len(flagged_fields))
        
        auto_approved = path == ReviewPath.AUTO_APPROVE
        
        logger.debug(
            f"Routing decision: path={path.value}, priority={priority}, "
            f"auto_approved={auto_approved}, confidence={effective_confidence:.2f}"
        )
        
        return ReviewDecision(
            path=path,
            priority=priority,
            reasons=reasons,
            auto_approved=auto_approved,
            flagged_fields=list(set(flagged_fields)),
            estimated_review_time=review_time,
            confidence_factors=confidence_factors,
        )
    
    def route_batch(
        self,
        products: List[ExtractedProduct],
        validation_results: Optional[List[ValidationResult]] = None,
        quality_reports: Optional[List[QualityReport]] = None,
    ) -> List[ReviewDecision]:
        """
        Route a batch of products.
        
        Args:
            products: List of products to route
            validation_results: Corresponding validation results
            quality_reports: Corresponding quality reports
            
        Returns:
            List of ReviewDecisions
        """
        decisions = []
        
        for i, product in enumerate(products):
            validation = validation_results[i] if validation_results and i < len(validation_results) else None
            quality = quality_reports[i] if quality_reports and i < len(quality_reports) else None
            
            decision = self.route_product(product, validation, quality)
            decisions.append(decision)
        
        return decisions
    
    def _check_field_confidence(
        self,
        product: ExtractedProduct,
    ) -> List[str]:
        """Check for low-confidence fields."""
        low_confidence = []
        
        if not product.field_confidence:
            return low_confidence
        
        fc = product.field_confidence
        threshold = 0.75 if self.strict_mode else 0.70
        
        # Check each important field
        field_mapping = {
            "brand": fc.brand,
            "product_name": fc.product_name,
            "quantity": fc.quantity,
            "regular_price": fc.regular_price,
            "discounted_price": fc.discounted_price,
            "discount_percentage": fc.discount_percentage,
            "product_code": fc.product_code,
        }
        
        for field_name, score in field_mapping.items():
            if score is not None and score < threshold:
                low_confidence.append(field_name)
        
        return low_confidence
    
    def _check_uncertainty_flags(
        self,
        product: ExtractedProduct,
    ) -> List[str]:
        """Check for critical uncertainty flags."""
        critical = []
        
        for flag in product.uncertainty_flags:
            if flag in self.CRITICAL_FLAGS:
                critical.append(flag)
        
        return critical
    
    def _calculate_effective_confidence(
        self,
        base_confidence: float,
        validation_result: Optional[ValidationResult],
        quality_report: Optional[QualityReport],
    ) -> float:
        """
        Calculate effective confidence score.
        
        Combines VLM confidence with validation and quality factors.
        """
        effective = base_confidence
        
        # Penalize for validation issues
        if validation_result:
            # Each error reduces confidence by 0.05 (max -0.20)
            error_penalty = min(0.20, len(validation_result.errors) * 0.05)
            # Each warning reduces confidence by 0.02 (max -0.10)
            warning_penalty = min(0.10, len(validation_result.warnings) * 0.02)
            effective -= (error_penalty + warning_penalty)
        
        # Factor in image quality
        if quality_report:
            # Blend with image quality (20% weight)
            effective = effective * 0.8 + quality_report.overall_score * 0.2
        
        return max(0, min(1, effective))
    
    def _determine_path(
        self,
        effective_confidence: float,
        validation_passed: bool,
        image_quality_ok: bool,
        has_critical_flags: bool,
        error_count: int,
        warning_count: int,
    ) -> tuple:
        """
        Determine review path and priority.
        
        Returns:
            Tuple of (ReviewPath, priority)
        """
        # Priority review for critical issues
        if has_critical_flags or error_count >= 3:
            priority = min(100, 70 + error_count * 10)
            return ReviewPath.PRIORITY_REVIEW, priority
        
        # Auto-reject for severe validation failures
        if error_count >= 5:
            return ReviewPath.REJECTED, 100
        
        # Check for auto-approval
        if (effective_confidence >= self.auto_approve_threshold and
            validation_passed and
            image_quality_ok and
            not has_critical_flags and
            error_count == 0 and
            warning_count <= 1):
            return ReviewPath.AUTO_APPROVE, 0
        
        # Quick review for minor issues
        if (effective_confidence >= self.quick_review_threshold and
            error_count <= 1 and
            warning_count <= 3):
            priority = 30 + (1 - effective_confidence) * 40
            return ReviewPath.QUICK_REVIEW, int(priority)
        
        # Detailed review for everything else
        priority = 50 + error_count * 5 + warning_count * 2 + (1 - effective_confidence) * 30
        return ReviewPath.DETAILED_REVIEW, min(100, int(priority))
    
    def _estimate_review_time(
        self,
        path: ReviewPath,
        flagged_field_count: int,
    ) -> int:
        """Estimate review time in seconds."""
        base_times = {
            ReviewPath.AUTO_APPROVE: 0,
            ReviewPath.QUICK_REVIEW: 5,
            ReviewPath.DETAILED_REVIEW: 30,
            ReviewPath.PRIORITY_REVIEW: 60,
            ReviewPath.REJECTED: 0,
        }
        
        base = base_times.get(path, 30)
        # Add time for each flagged field
        return base + flagged_field_count * 3


def calculate_auto_approval_rate(
    decisions: List[ReviewDecision],
) -> Dict[str, float]:
    """
    Calculate auto-approval statistics from decisions.
    
    Args:
        decisions: List of review decisions
        
    Returns:
        Dict with statistics
    """
    if not decisions:
        return {"auto_approval_rate": 0, "path_distribution": {}}
    
    total = len(decisions)
    auto_approved = sum(1 for d in decisions if d.auto_approved)
    
    path_counts = {}
    for decision in decisions:
        path = decision.path.value
        path_counts[path] = path_counts.get(path, 0) + 1
    
    path_distribution = {k: v / total for k, v in path_counts.items()}
    
    return {
        "total_products": total,
        "auto_approved_count": auto_approved,
        "auto_approval_rate": auto_approved / total,
        "path_distribution": path_distribution,
        "average_priority": sum(d.priority for d in decisions) / total,
    }