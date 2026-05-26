"""
Cross-Page Reconciliation Module.

This module handles detection and reconciliation of products that span
multiple pages, merging split products and resolving ambiguities.

Example Usage:
    from app.core.extraction.reconciliation import ProductReconciler
    
    reconciler = ProductReconciler()
    reconciled_products = reconciler.reconcile(page_results)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from app.core.extraction.schemas import (
    BoundingBox,
    ExtractedProduct,
    FieldConfidence,
    PageExtractionResult,
)

logger = logging.getLogger(__name__)


@dataclass
class SplitProductCandidate:
    """Represents a potential split product across pages."""
    
    first_product: ExtractedProduct
    first_page: int
    second_product: ExtractedProduct
    second_page: int
    confidence: float
    merge_reason: str
    

@dataclass
class ReconciliationResult:
    """Result of cross-page reconciliation."""
    
    products: List[ExtractedProduct] = field(default_factory=list)
    merged_products: List[Tuple[ExtractedProduct, ExtractedProduct, ExtractedProduct]] = field(
        default_factory=list
    )  # (first, second, merged)
    removed_duplicates: List[ExtractedProduct] = field(default_factory=list)
    split_candidates_rejected: List[SplitProductCandidate] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def merge_count(self) -> int:
        return len(self.merged_products)
    
    @property
    def duplicate_count(self) -> int:
        return len(self.removed_duplicates)


class ProductReconciler:
    """
    Reconciles products across pages.
    
    Handles:
    - Split product detection and merging
    - Duplicate detection
    - Continuation product handling
    - Cross-page validation
    
    Attributes:
        merge_confidence_threshold: Min confidence to auto-merge
        name_similarity_threshold: Min similarity for name matching
        position_tolerance: Position tolerance for boundary products
    """
    
    def __init__(
        self,
        merge_confidence_threshold: float = 0.75,
        name_similarity_threshold: float = 0.70,
        position_tolerance: int = 50,
    ):
        """
        Initialize reconciler.
        
        Args:
            merge_confidence_threshold: Confidence threshold for merging
            name_similarity_threshold: Name similarity threshold
            position_tolerance: Pixel tolerance for position matching
        """
        self.merge_confidence_threshold = merge_confidence_threshold
        self.name_similarity_threshold = name_similarity_threshold
        self.position_tolerance = position_tolerance
    
    def reconcile(
        self,
        page_results: List[PageExtractionResult],
        page_height: int = 3508,
    ) -> ReconciliationResult:
        """
        Reconcile products across all pages.
        
        Args:
            page_results: Extraction results for each page
            page_height: Height of pages in pixels
            
        Returns:
            ReconciliationResult with reconciled products
        """
        result = ReconciliationResult()
        
        if not page_results:
            return result
        
        # Collect all products with page context
        all_products: List[Tuple[ExtractedProduct, int]] = []  # (product, page_number)
        
        for page_result in page_results:
            for product in page_result.products:
                all_products.append((product, page_result.page_number))
        
        # Detect split products (products at page boundaries)
        split_candidates = self._detect_split_products(
            page_results, page_height
        )
        
        # Merge confirmed split products
        merged_pairs: Set[Tuple[int, int]] = set()  # (page1_idx, page2_idx)
        
        for candidate in split_candidates:
            if candidate.confidence >= self.merge_confidence_threshold:
                merged_product = self._merge_products(
                    candidate.first_product,
                    candidate.second_product,
                )
                result.merged_products.append((
                    candidate.first_product,
                    candidate.second_product,
                    merged_product,
                ))
                # Track which products were merged
                for idx, (prod, page) in enumerate(all_products):
                    if (prod == candidate.first_product and 
                        page == candidate.first_page):
                        merged_pairs.add((idx, -1))
                    elif (prod == candidate.second_product and 
                          page == candidate.second_page):
                        merged_pairs.add((-1, idx))
                
                logger.info(
                    f"Merged split product: {merged_product.product_name} "
                    f"(pages {candidate.first_page}-{candidate.second_page})"
                )
            else:
                result.split_candidates_rejected.append(candidate)
                result.warnings.append(
                    f"Possible split product rejected: "
                    f"'{candidate.first_product.product_name}' (page {candidate.first_page}) "
                    f"and '{candidate.second_product.product_name}' (page {candidate.second_page}) "
                    f"- confidence {candidate.confidence:.2f}"
                )
        
        # Build final product list
        merged_indices = {idx for idx, _ in merged_pairs} | {idx for _, idx in merged_pairs}
        
        for idx, (product, page) in enumerate(all_products):
            if idx not in merged_indices:
                result.products.append(product)
        
        # Add merged products
        for _, _, merged in result.merged_products:
            result.products.append(merged)
        
        # Remove same-page duplicates (products extracted twice from fragmented grid)
        result.products, same_page_dupes = self._remove_same_page_duplicates(result.products)
        result.removed_duplicates.extend(same_page_dupes)

        # Detect and remove cross-page duplicates
        result.products, duplicates = self._remove_duplicates(result.products)
        result.removed_duplicates.extend(duplicates)

        logger.info(
            f"Reconciliation complete: {len(result.products)} products, "
            f"{result.merge_count} merged, {result.duplicate_count} duplicates removed "
            f"({len(same_page_dupes)} same-page, {len(duplicates)} cross-page)"
        )
        
        return result
    
    def _detect_split_products(
        self,
        page_results: List[PageExtractionResult],
        page_height: int,
    ) -> List[SplitProductCandidate]:
        """
        Detect products that might be split across pages.
        
        A product might be split if:
        - It's at the bottom of one page and top of the next
        - Product names are similar or appear to be continuations
        - Missing price/other info on one part
        
        Args:
            page_results: Page extraction results
            page_height: Page height in pixels
            
        Returns:
            List of split product candidates
        """
        candidates = []
        boundary_threshold = page_height * 0.1  # 10% of page height
        
        for i in range(len(page_results) - 1):
            current_page = page_results[i]
            next_page = page_results[i + 1]
            
            # Check if continuation was detected
            if current_page.continuation_detected:
                logger.debug(f"Page {current_page.page_number} has continuation flag")
            
            # Find products at bottom of current page (skip products without bounding boxes)
            bottom_products = [
                p for p in current_page.products
                if p.bounding_box and (p.bounding_box.y + p.bounding_box.height) > (page_height - boundary_threshold)
            ]

            # Find products at top of next page (skip products without bounding boxes)
            top_products = [
                p for p in next_page.products
                if p.bounding_box and p.bounding_box.y < boundary_threshold
            ]
            
            # Check for potential matches
            for bottom_prod in bottom_products:
                for top_prod in top_products:
                    confidence, reason = self._calculate_split_confidence(
                        bottom_prod, top_prod
                    )
                    
                    if confidence > 0.5:  # Basic threshold for candidate
                        candidates.append(SplitProductCandidate(
                            first_product=bottom_prod,
                            first_page=current_page.page_number,
                            second_product=top_prod,
                            second_page=next_page.page_number,
                            confidence=confidence,
                            merge_reason=reason,
                        ))
        
        return candidates
    
    def _calculate_split_confidence(
        self,
        first: ExtractedProduct,
        second: ExtractedProduct,
    ) -> Tuple[float, str]:
        """
        Calculate confidence that two products are parts of a split.
        
        Args:
            first: Product at bottom of first page
            second: Product at top of second page
            
        Returns:
            Tuple of (confidence score, reason)
        """
        confidence = 0.0
        reasons = []
        
        # Check name similarity
        name_sim = self._name_similarity(
            first.product_name, second.product_name
        )
        if name_sim > self.name_similarity_threshold:
            confidence += 0.3
            reasons.append(f"similar_names({name_sim:.2f})")
        
        # Check if one has info the other lacks
        if first.discounted_price is None and second.discounted_price is not None:
            confidence += 0.2
            reasons.append("first_missing_price")
        elif second.discounted_price is None and first.discounted_price is not None:
            confidence += 0.2
            reasons.append("second_missing_price")
        
        # Check brand match
        if first.brand and second.brand:
            if first.brand.lower() == second.brand.lower():
                confidence += 0.15
                reasons.append("brand_match")
        elif first.brand is None and second.brand:
            confidence += 0.1
            reasons.append("first_missing_brand")
        elif second.brand is None and first.brand:
            confidence += 0.1
            reasons.append("second_missing_brand")
        
        # Check horizontal alignment (same column) - skip if no bounding boxes
        if first.bounding_box and second.bounding_box:
            x_diff = abs(first.bounding_box.x - second.bounding_box.x)
        else:
            x_diff = self.position_tolerance + 1  # Skip alignment check
        if x_diff < self.position_tolerance:
            confidence += 0.15
            reasons.append("aligned_horizontally")
        
        # Check for complementary uncertainty flags
        first_flags = set(first.uncertainty_flags or [])
        second_flags = set(second.uncertainty_flags or [])
        
        if "partial_product" in first_flags or "partial_product" in second_flags:
            confidence += 0.2
            reasons.append("partial_flag")
        
        if "continues_on_next_page" in first_flags:
            confidence += 0.25
            reasons.append("continuation_flag")
        
        if "continued_from_previous" in second_flags:
            confidence += 0.25
            reasons.append("continuation_flag")
        
        # Cap at 1.0
        confidence = min(confidence, 1.0)
        
        return confidence, "+".join(reasons) if reasons else "unknown"
    
    def _name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two product names.
        
        Uses a combination of:
        - Word overlap
        - Substring matching
        - Edit distance approximation
        
        Args:
            name1: First product name
            name2: Second product name
            
        Returns:
            Similarity score between 0 and 1
        """
        if not name1 or not name2:
            return 0.0
        
        # Normalize names
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        
        # Exact match
        if n1 == n2:
            return 1.0
        
        # One is substring of other
        if n1 in n2 or n2 in n1:
            return 0.9
        
        # Word overlap
        words1 = set(n1.split())
        words2 = set(n2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        jaccard = len(intersection) / len(union)
        
        # Boost if significant words match
        significant_words = intersection - {"the", "a", "an", "and", "or", "for", "with"}
        if significant_words:
            jaccard += 0.1 * len(significant_words)
        
        return min(jaccard, 1.0)
    
    def _merge_products(
        self,
        first: ExtractedProduct,
        second: ExtractedProduct,
    ) -> ExtractedProduct:
        """
        Merge two split products into one.
        
        Strategy:
        - Prefer non-null values
        - Combine bounding boxes
        - Average confidence scores
        - Merge uncertainty flags
        
        Args:
            first: First product part
            second: Second product part
            
        Returns:
            Merged product
        """
        # Combine bounding boxes (spanning both) - handle None cases
        merged_bbox = None
        if first.bounding_box and second.bounding_box:
            merged_bbox = BoundingBox(
                x=min(first.bounding_box.x, second.bounding_box.x),
                y=first.bounding_box.y,  # Use first product's y (top of first)
                width=max(
                    first.bounding_box.x + first.bounding_box.width,
                    second.bounding_box.x + second.bounding_box.width,
                ) - min(first.bounding_box.x, second.bounding_box.x),
                height=first.bounding_box.height + second.bounding_box.height,
            )
        elif first.bounding_box:
            merged_bbox = first.bounding_box
        elif second.bounding_box:
            merged_bbox = second.bounding_box
        
        # Merge field confidence
        merged_confidence = None
        if first.field_confidence or second.field_confidence:
            fc1 = first.field_confidence or FieldConfidence()
            fc2 = second.field_confidence or FieldConfidence()
            
            merged_confidence = FieldConfidence(
                brand=max(fc1.brand or 0, fc2.brand or 0) if (fc1.brand or fc2.brand) else None,
                product_code=max(fc1.product_code or 0, fc2.product_code or 0) if (fc1.product_code or fc2.product_code) else None,
                product_name=max(fc1.product_name or 0, fc2.product_name or 0) if (fc1.product_name or fc2.product_name) else None,
                quantity=max(fc1.quantity or 0, fc2.quantity or 0) if (fc1.quantity or fc2.quantity) else None,
                units=max(fc1.units or 0, fc2.units or 0) if (fc1.units or fc2.units) else None,
                regular_price=max(fc1.regular_price or 0, fc2.regular_price or 0) if (fc1.regular_price or fc2.regular_price) else None,
                discounted_price=max(fc1.discounted_price or 0, fc2.discounted_price or 0) if (fc1.discounted_price or fc2.discounted_price) else None,
                discount_percentage=max(fc1.discount_percentage or 0, fc2.discount_percentage or 0) if (fc1.discount_percentage or fc2.discount_percentage) else None,
                currency=max(fc1.currency or 0, fc2.currency or 0) if (fc1.currency or fc2.currency) else None,
                product_id=max(fc1.product_id or 0, fc2.product_id or 0) if (fc1.product_id or fc2.product_id) else None,
            )
        
        # Merge names (combine if different)
        merged_name = first.product_name
        if second.product_name and second.product_name != first.product_name:
            # Check if second is continuation
            if not second.product_name.lower().startswith(first.product_name.lower()[:10]):
                merged_name = f"{first.product_name} {second.product_name}".strip()
        
        # Merge uncertainty flags
        merged_flags = list(set(
            (first.uncertainty_flags or []) + (second.uncertainty_flags or [])
        ))
        # Add merged flag
        merged_flags.append("merged_from_split")
        # Remove split-related flags
        merged_flags = [
            f for f in merged_flags 
            if f not in ("partial_product", "continues_on_next_page", "continued_from_previous")
        ]
        
        # Merge category alternatives
        if first.category_alternatives is not None and second.category_alternatives is not None:
            seen = {alt.get("category") for alt in first.category_alternatives}
            extras = [a for a in second.category_alternatives if a.get("category") not in seen]
            merged_category_alternatives = first.category_alternatives + extras
        else:
            merged_category_alternatives = first.category_alternatives if first.category_alternatives is not None else second.category_alternatives

        # Merge category confidence: take the max of non-None values
        merged_category_confidence = None
        if first.category_confidence is not None and second.category_confidence is not None:
            merged_category_confidence = max(first.category_confidence, second.category_confidence)
        elif first.category_confidence is not None:
            merged_category_confidence = first.category_confidence
        elif second.category_confidence is not None:
            merged_category_confidence = second.category_confidence

        return ExtractedProduct(
            bounding_box=merged_bbox,
            brand=first.brand or second.brand,
            product_code=first.product_code or second.product_code,
            product_name=merged_name,
            quantity=first.quantity or second.quantity,
            units=first.units or second.units,
            size=first.size or second.size,
            regular_price=first.regular_price or second.regular_price,
            discounted_price=first.discounted_price or second.discounted_price,
            discount_percentage=first.discount_percentage or second.discount_percentage,
            currency=first.currency or second.currency,
            product_id=first.product_id or second.product_id,
            promotional_info=first.promotional_info or second.promotional_info,
            suggested_category=first.suggested_category or second.suggested_category,
            category_confidence=merged_category_confidence,
            category_alternatives=merged_category_alternatives,
            confidence_score=(
                (first.confidence_score + second.confidence_score) / 2
                if first.confidence_score and second.confidence_score
                else first.confidence_score or second.confidence_score
            ),
            field_confidence=merged_confidence,
            uncertainty_flags=merged_flags,
            is_split_product=True,
            merged_from_pages=[first.bounding_box, second.bounding_box],
        )
    
    def _remove_same_page_duplicates(
        self,
        products: List[ExtractedProduct],
    ) -> Tuple[List[ExtractedProduct], List[ExtractedProduct]]:
        """
        Remove duplicate products on the same page.

        When grid regions fragment a product card, the VLM may extract it
        multiple times from different region groups. These duplicates share
        the same page number, very similar names, and identical prices,
        but have different bounding boxes.

        Args:
            products: List of products

        Returns:
            Tuple of (unique products, removed duplicates)
        """
        if not products:
            return [], []

        # Group by page
        by_page: Dict[Optional[int], List[ExtractedProduct]] = {}
        for p in products:
            page = p.source_page
            if page not in by_page:
                by_page[page] = []
            by_page[page].append(p)

        unique = []
        duplicates = []

        for page, page_products in by_page.items():
            seen_sigs: Dict[str, ExtractedProduct] = {}
            for product in page_products:
                # Signature based on name + price only (ignoring position)
                name = (product.product_name or "").lower().strip()
                # Normalize whitespace
                name = " ".join(name.split())
                price_key = product.discounted_price or product.regular_price or 0
                sig = f"{name}|{price_key}"

                if sig in seen_sigs:
                    existing = seen_sigs[sig]
                    # Keep the one with higher confidence or more complete data
                    existing_score = (existing.confidence_score or 0) + (
                        1 if existing.product_code else 0
                    )
                    product_score = (product.confidence_score or 0) + (
                        1 if product.product_code else 0
                    )
                    if product_score > existing_score:
                        # Replace with better version
                        duplicates.append(existing)
                        seen_sigs[sig] = product
                        logger.debug(
                            f"Same-page dedup (page {page}): replaced "
                            f"'{existing.product_name[:40]}' with better copy"
                        )
                    else:
                        duplicates.append(product)
                        logger.debug(
                            f"Same-page dedup (page {page}): removed duplicate "
                            f"'{product.product_name[:40]}'"
                        )
                else:
                    seen_sigs[sig] = product

            unique.extend(seen_sigs.values())

        if duplicates:
            logger.info(
                f"Same-page dedup: removed {len(duplicates)} duplicates"
            )

        return unique, duplicates

    def _remove_duplicates(
        self,
        products: List[ExtractedProduct],
    ) -> Tuple[List[ExtractedProduct], List[ExtractedProduct]]:
        """
        Remove duplicate products.
        
        Duplicates are detected by:
        - Same product name and price
        - Very similar bounding boxes
        
        Args:
            products: List of products
            
        Returns:
            Tuple of (unique products, removed duplicates)
        """
        if not products:
            return [], []
        
        unique = []
        duplicates = []
        seen_signatures: Set[str] = set()
        
        for product in products:
            # Create signature
            signature = self._product_signature(product)
            
            if signature in seen_signatures:
                duplicates.append(product)
                logger.debug(f"Duplicate found: {product.product_name}")
            else:
                seen_signatures.add(signature)
                unique.append(product)
        
        return unique, duplicates
    
    def _product_signature(self, product: ExtractedProduct) -> str:
        """
        Create a signature for duplicate detection.
        
        Args:
            product: Product to create signature for
            
        Returns:
            Signature string
        """
        # Normalize name
        name = (product.product_name or "").lower().strip()[:50]

        # Price for dedup key
        price = product.discounted_price or product.regular_price or 0

        # Position bucket (50px buckets) - handle None bounding_box
        if product.bounding_box:
            x_bucket = product.bounding_box.x // 50
            y_bucket = product.bounding_box.y // 50
        else:
            # Use page number and index for uniqueness when no bbox
            x_bucket = product.source_page or 0
            y_bucket = hash(product.product_name or "") % 1000

        return f"{name}|{price}|{x_bucket}|{y_bucket}"


def reconcile_page_results(
    page_results: List[PageExtractionResult],
    page_height: int = 3508,
    merge_confidence_threshold: float = 0.75,
) -> ReconciliationResult:
    """
    Convenience function to reconcile page results.

    Args:
        page_results: Page extraction results
        page_height: Page height in pixels
        merge_confidence_threshold: Confidence threshold for merging

    Returns:
        ReconciliationResult
    """
    reconciler = ProductReconciler(
        merge_confidence_threshold=merge_confidence_threshold
    )
    return reconciler.reconcile(page_results, page_height)


def sanitize_products(products: List[ExtractedProduct]) -> List[ExtractedProduct]:
    """
    Post-extraction data sanitization.

    Fixes common VLM extraction errors before validation:
    1. Moves misplaced discounted_price to regular_price when no discount exists
    2. Computes regular_price from discounted_price + discount_percentage when missing
    3. Fixes identical regular/discounted prices when discount_percentage is set
    4. Filters out category headers that aren't real products

    Args:
        products: List of extracted products from reconciliation

    Returns:
        Sanitized list of products
    """
    sanitized = []
    filtered_count = 0

    for product in products:
        # --- Fix 1: Misplaced price (discounted_price set, no regular_price, no discount) ---
        if (
            product.regular_price is None
            and product.discounted_price is not None
            and product.discount_percentage is None
        ):
            product.regular_price = product.discounted_price
            product.discounted_price = None
            if "price_field_corrected" not in product.uncertainty_flags:
                product.uncertainty_flags.append("price_field_corrected")
            logger.debug(
                f"Sanitize: moved discounted_price to regular_price for "
                f"'{product.product_name[:40]}' (no discount present)"
            )

        # --- Fix 2: Missing regular_price but have discounted_price + discount_percentage ---
        if (
            product.regular_price is None
            and product.discounted_price is not None
            and product.discount_percentage is not None
            and 0 < product.discount_percentage < 100
        ):
            computed_regular = product.discounted_price / (
                1 - product.discount_percentage / 100
            )
            product.regular_price = round(computed_regular, 2)
            if "regular_price_computed" not in product.uncertainty_flags:
                product.uncertainty_flags.append("regular_price_computed")
            logger.debug(
                f"Sanitize: computed regular_price={product.regular_price} from "
                f"discounted={product.discounted_price}, discount={product.discount_percentage}% "
                f"for '{product.product_name[:40]}'"
            )

        # --- Fix 3: Identical prices with non-zero discount ---
        if (
            product.regular_price is not None
            and product.discounted_price is not None
            and product.regular_price == product.discounted_price
            and product.discount_percentage is not None
            and product.discount_percentage > 0
        ):
            if product.discount_percentage < 100:
                computed_regular = product.discounted_price / (
                    1 - product.discount_percentage / 100
                )
                product.regular_price = round(computed_regular, 2)
                if "regular_price_computed" not in product.uncertainty_flags:
                    product.uncertainty_flags.append("regular_price_computed")
                logger.debug(
                    f"Sanitize: recomputed regular_price={product.regular_price} "
                    f"(was equal to discounted={product.discounted_price}) "
                    f"for '{product.product_name[:40]}'"
                )
            else:
                product.discounted_price = None
                product.discount_percentage = None
                if "discount_cleared" not in product.uncertainty_flags:
                    product.uncertainty_flags.append("discount_cleared")

        # --- Fix 4: Discount mismatch correction ---
        # When both prices are present, trust prices over badge text for discount
        if (
            product.regular_price is not None
            and product.discounted_price is not None
            and product.regular_price > 0
            and product.regular_price > product.discounted_price
            and product.discount_percentage is not None
        ):
            calculated = (
                (product.regular_price - product.discounted_price)
                / product.regular_price
                * 100
            )
            diff = abs(product.discount_percentage - calculated)
            if diff > 5:
                logger.debug(
                    f"Sanitize: discount mismatch for '{product.product_name[:40]}': "
                    f"stated={product.discount_percentage}%, calculated={calculated:.1f}% "
                    f"(diff={diff:.1f}%). Using calculated value."
                )
                product.discount_percentage = calculated
                if "discount_recalculated" not in product.uncertainty_flags:
                    product.uncertainty_flags.append("discount_recalculated")

        # --- Fix 5: Filter out category headers ---
        if (
            product.regular_price is None
            and product.discounted_price is None
            and _looks_like_category_header(product)
        ):
            filtered_count += 1
            logger.info(
                f"Sanitize: filtered category header '{product.product_name}'"
            )
            continue

        sanitized.append(product)

    if filtered_count > 0:
        logger.info(f"Sanitize: filtered {filtered_count} category headers")

    logger.info(
        f"Product sanitization complete: {len(sanitized)} products "
        f"({filtered_count} headers filtered)"
    )
    return sanitized


def _looks_like_category_header(product: ExtractedProduct) -> bool:
    """
    Check if a product looks like a category/section header rather than
    a real product. Only called when the product has no prices at all.
    """
    name = product.product_name.strip()

    # All uppercase name longer than 3 chars (typical header: "KAVE IN KAVNE KAPSULE")
    if name == name.upper() and len(name) > 5:
        return True

    # Known header patterns (Slovenian, Croatian, Serbian)
    header_prefixes = [
        "vsi izdelki",
        "vse ",
        "vsi ",
        "izbrani izdelki",
        "all products",
        "selected products",
        "svi proizvodi",
        "svi artikli",
        "izabrani proizvodi",
    ]
    name_lower = name.lower()
    for prefix in header_prefixes:
        if name_lower.startswith(prefix):
            return True

    return False