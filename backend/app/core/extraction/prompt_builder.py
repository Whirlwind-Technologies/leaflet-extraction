"""
Prompt Builder Module.

This module builds optimized prompts for Claude VLM extraction,
including context-aware prompts and structured output formatting.

Two-pass extraction with visual verification:
- Pass 1: Extract product data WITH bounding boxes
- Pass 2: Verify bounding boxes visually (boxes drawn on image)

Example Usage:
    from app.core.extraction.prompt_builder import PromptBuilder

    builder = PromptBuilder()
    prompt = builder.build_extraction_prompt(
        page_number=3,
        total_pages=12,
        context=ExtractionContext(leaflet_id="LEAF_001")
    )
"""

import json
import logging
from typing import Optional

from app.core.extraction.schemas import ExtractionContext
from app.core.categories import get_category_loader

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Builds extraction prompts for Claude VLM.

    Creates context-aware prompts optimized for product extraction
    from retail promotional leaflets using a two-pass approach:
    - Pass 1: Extract product data WITH bounding boxes
    - Pass 2: Visual verification with boxes drawn on image

    Attributes:
        include_examples: Whether to include example output
        language: Target language for extraction

    Example:
        >>> builder = PromptBuilder()
        >>> prompt = builder.build_extraction_prompt(3, 12)
    """

    # Example product for few-shot learning (includes bounding box)
    EXAMPLE_PRODUCT = {
        "bounding_box": {"x": 50, "y": 120, "width": 280, "height": 350},
        "brand": "DESPAR",
        "product_code": None,
        "product_name": "ČRNE OLIVE brez koščic",
        "quantity": 125,
        "units": "g",
        "size": None,
        "regular_price": 1.59,
        "discounted_price": 1.25,
        "discount_percentage": 21,
        "currency": None,
        "product_id": None,
        "promotional_info": "CENEJE 21%, s SPAR plus kartico",
        "suggested_category": "Olives",
        "category_confidence": 0.94,
        "category_alternatives": None,
        "confidence_score": 0.95,
        "field_confidence": {
            "brand": 0.98,
            "product_code": None,
            "product_name": 0.96,
            "quantity": 0.95,
            "regular_price": 0.92,
            "discounted_price": 0.98,
            "discount_percentage": 0.99,
            "suggested_category": 0.94
        },
        "uncertainty_flags": []
    }
    
    def __init__(
        self,
        include_examples: bool = True,
        language: Optional[str] = None,
    ):
        """
        Initialize the prompt builder.
        
        Args:
            include_examples: Whether to include example output
            language: Target language (auto-detected if None)
        """
        self.include_examples = include_examples
        self.language = language
    
    def build_extraction_prompt(
        self,
        page_number: int,
        total_pages: int,
        context: Optional[ExtractionContext] = None,
    ) -> str:
        """
        Build the main extraction prompt for product data extraction.

        This prompt extracts product data WITH bounding boxes.
        A verification pass will follow to confirm bounding box accuracy.

        Args:
            page_number: Current page number (1-indexed)
            total_pages: Total pages in leaflet
            context: Optional extraction context

        Returns:
            Complete prompt string for VLM
        """
        # Build context section
        context_section = self._build_context_section(context)
        currency = context.currency if context and context.currency else "EUR"
        pricing_rules = self._build_pricing_rules_section(currency)

        # Compute dynamic bounding box hints based on actual image dimensions
        img_w = context.image_width if context and context.image_width else 2480
        img_h = context.image_height if context and context.image_height else 3508
        min_w = max(50, int(img_w * 0.05))
        min_h = max(70, int(img_h * 0.05))
        max_w = int(img_w * 0.55)
        max_h = int(img_h * 0.45)
        col2_w = img_w // 2
        col3_w = img_w // 3
        col4_w = img_w // 4
        height_lo = int(img_h * 0.10)
        height_hi = int(img_h * 0.25)

        # Build the prompt with bounding box extraction
        prompt = f"""You are a PRODUCT EXTRACTION SYSTEM for retail catalog pages.

Your task is to IDENTIFY, LOCATE, and EXTRACT DATA for each individual product on the page.

CRITICAL REQUIREMENTS:
- Extract COMPLETE bounding box coordinates for each product
- Extract ALL product information accurately
- DO NOT extract partial products
- DO NOT merge information from multiple products
- DO NOT include page-level headers or section titles as products

{context_section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOUNDING BOX INSTRUCTIONS (CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The image is {img_w}px wide × {img_h}px tall.
Coordinate system: Origin (0,0) is TOP-LEFT corner.

For EACH product, provide bounding_box with:
- x: Left edge X coordinate (pixels from left)
- y: Top edge Y coordinate (pixels from top)
- width: Box width in pixels
- height: Box height in pixels

BOUNDING BOX MUST INCLUDE:
✔ The product image/photo
✔ Brand name text
✔ Product name/description text
✔ ALL price elements (regular, discounted, unit price)
✔ Discount badges and promotional text
✔ Size/quantity information
✔ 10-15px padding around the complete product block

BOUNDING BOX MUST NOT:
✖ Extend into adjacent products
✖ Include page headers or section titles
✖ Be smaller than ~{min_w}×{min_h} pixels (minimum product size)
✖ Exceed ~{max_w}×{max_h} pixels (maximum reasonable size)

TIPS FOR ACCURATE BOXES:
- Products are typically arranged in a grid (2-4 columns)
- Estimate column positions: 2 cols → ~{col2_w}px each, 3 cols → ~{col3_w}px each, 4 cols → ~{col4_w}px each
- Product heights typically {height_lo}-{height_hi}px depending on content
- Look at visual boundaries and whitespace between products

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRODUCT IDENTIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A product is a distinct item for sale. Each product typically includes:
- Product image/photo
- Brand name
- Product name and description
- Price information
- Optional: discount badges, promotional offers, quantity/size info

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA TO EXTRACT FOR EACH PRODUCT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Required fields:
- bounding_box: {{x, y, width, height}} in pixels (REQUIRED - see instructions above)
- brand: Brand name (null if not visible)
- product_code: SKU/article number if visible (null if not visible)
- product_name: Full product description (IMPORTANT: be complete and accurate)
- quantity: Package size/weight as a number (e.g., 125 for "125g", 1.5 for "1.5L"). NOT the price! For products sold "per kg" without specific package weight, use null.
- units: Unit of measurement (g, kg, ml, L, pcs, pack)
- size: Size descriptor if shown separately (e.g., "family pack", "XL")
- regular_price: REQUIRED — the product's standard price. If discounted, the original higher price. If NO discount, the shown price. NEVER leave null if a price is visible.
- discounted_price: The sale/promotional price ONLY when a discount badge or crossed-out price is present (null if no discount)
- discount_percentage: From discount badge like "-50%" (null if none visible)
- currency: {currency}
- product_id: Barcode/EAN if visible
- promotional_info: Promo text, loyalty offers, multi-buy deals

Category fields:
- suggested_category: Most specific category from list below
- category_confidence: 0.0–1.0
- category_alternatives: Top 2-3 alternatives ONLY if confidence < 0.80

Quality fields:
- confidence_score: Overall extraction confidence (0.0–1.0)
- field_confidence: Per-field confidence scores (object with field names as keys)
- uncertainty_flags: List any issues (e.g., ["price_unclear", "bbox_estimated"])

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT TO EXTRACT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✔ Product brand and name
✔ ALL price elements:
   - Crossed-out original price (regular_price)
   - Main promotional price (discounted_price)
   - Unit price info in promotional_info
   - Loyalty price in promotional_info
✔ Weight/size/quantity (125g, 1L, 6 pcs)
✔ Discount percentage from badges ("-33%", "CENEJE 21%")
✔ Promotional text ("s SPAR plus kartico", "2 za €3", "3+1 GRATIS")
✔ Product codes/SKUs if visible
✔ Certification info (BIO, organic) in product name or promotional_info

STRICTLY EXCLUDE:
✖ Page headers and section titles (e.g., "SADJE IN ZELENJAVA", "VSE ZA PEKO")
✖ Large promotional banners spanning multiple products
✖ Content from adjacent products
✖ Page margins and footers

{pricing_rules}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE CATEGORIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{get_category_loader().format_for_vlm_prompt(include_descriptions=True)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — JSON ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY valid JSON. No explanations. No markdown.

{{
  "page_number": {page_number},
  "products": [
    {{
      "bounding_box": {{"x": 50, "y": 100, "width": 580, "height": 450}},
      "brand": "SPAR",
      "product_code": null,
      "product_name": "BIO BOROVNICE pakirano 125g",
      "quantity": 125,
      "units": "g",
      "size": null,
      "regular_price": 1.99,
      "discounted_price": 1.49,
      "discount_percentage": 33,
      "currency": "EUR",
      "product_id": null,
      "promotional_info": "33% CENEJE, s SPAR plus kartico €1.29",
      "suggested_category": "Fresh Fruit",
      "category_confidence": 0.95,
      "category_alternatives": null,
      "confidence_score": 0.94,
      "field_confidence": {{"brand": 0.95, "product_name": 0.96, "discounted_price": 0.98, "bounding_box": 0.85}},
      "uncertainty_flags": []
    }}
  ],
  "page_notes": "Grid layout with 4 products per row. All products have discount badges.",
  "continuation_detected": false
}}

Now extract ALL products from this page with ACCURATE bounding boxes.
"""
        return prompt
    
    def _build_context_section(
        self,
        context: Optional[ExtractionContext]
    ) -> str:
        """Build the context section of the prompt."""
        if not context:
            return ""
        
        parts = []
        
        if context.retailer:
            parts.append(f"- Retailer: {context.retailer}")
        
        if context.country:
            parts.append(f"- Country: {context.country}")
        
        if context.language:
            parts.append(f"- Expected language: {context.language}")
        
        if context.currency:
            parts.append(f"- Expected currency: {context.currency}")
        
        if context.has_previous_page:
            parts.append("- This page may continue products from the previous page")
        
        if context.has_next_page:
            parts.append("- Products may continue onto the next page")
        
        if context.previous_page_notes:
            parts.append(f"- Notes from previous page: {context.previous_page_notes}")
        
        if parts:
            return "\nADDITIONAL CONTEXT:\n" + "\n".join(parts)
        return ""
    
    def _build_pricing_rules_section(self, currency: Optional[str] = None) -> str:
        """
        Build currency-aware pricing rules section for VLM prompts.

        Includes superscript price format instructions and currency-specific
        guidance to prevent misinterpretation of prices.

        Args:
            currency: The expected currency code (e.g., "EUR", "RSD", "HRK")

        Returns:
            Pricing rules prompt section as a string
        """
        curr = currency or "EUR"

        # Currency-specific price range guidance
        currency_ranges = {
            "RSD": ("50", "50000", "Serbian Dinar"),
            "HRK": ("5", "5000", "Croatian Kuna"),
            "BAM": ("1", "2000", "Bosnian Mark"),
            "ALL": ("50", "50000", "Albanian Lek"),
            "MKD": ("20", "30000", "Macedonian Denar"),
            "RUB": ("20", "50000", "Russian Ruble"),
            "HUF": ("100", "500000", "Hungarian Forint"),
            "BGN": ("1", "5000", "Bulgarian Lev"),
            "RON": ("1", "5000", "Romanian Leu"),
        }

        range_info = currency_ranges.get(curr)

        section = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRICING RULES (CRITICAL - READ CAREFULLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FIELD ASSIGNMENT RULE (MOST IMPORTANT):
- regular_price MUST ALWAYS be populated for every product that has a visible price.
- regular_price is the product's STANDARD price — the price a customer would pay normally.
- discounted_price is ONLY used when there is a CLEAR discount indicator (badge, crossed-out price, "AKCIJA", etc.).

SCENARIO 1 — DISCOUNT BADGE PRESENT (e.g., "-25%", "-20%", "AKCIJA", crossed-out price):
- regular_price: The ORIGINAL/HIGHER price (often crossed out or in smaller text)
- discounted_price: The PROMOTIONAL/LOWER price (usually large/bold — what customer pays NOW)
- discount_percentage: The number from the badge (e.g., "-25%" → 25)

SCENARIO 2 — NO DISCOUNT BADGE (just a single price shown):
- regular_price: The shown price (THIS IS REQUIRED — never leave it null)
- discounted_price: null
- discount_percentage: null

SCENARIO 3 — CATEGORY-LEVEL PROMOTION (e.g., "25% off all coffees", no individual prices):
- Do NOT extract these as standalone products. Only extract items with individual prices visible.
- If a section header says "25% off" and individual products below have prices, apply the discount to each individual product.

SUPERSCRIPT PRICE FORMAT (VERY IMPORTANT):
Many leaflets display prices with LARGE digits for the main amount and SMALL
superscript digits for the decimal/cents portion. You MUST read BOTH parts:
- Large "499" with small superscript "99" = 499.99 (NOT 4.99)
- Large "129" with small superscript "99" = 129.99 (NOT 1.29)
- Large "49" with small superscript "99" = 49.99 (NOT 0.49)
- Large "2399" with small superscript "99" = 2399.99 (NOT 23.99)
The large digits are the WHOLE NUMBER part. The small superscript is the DECIMAL part.
Do NOT insert a decimal point within the large digits.

PRICE FORMAT RULES:
- European format uses COMMA for decimals: "5,99" means 5.99
- Convert comma to decimal point in output: "5,99" → 5.99
- Do NOT round any price. Return the exact value as shown (e.g., 1.49, not 1.5 or 1)
- Expected currency for this leaflet: {curr}
- Ignore unit prices like "1 kg = 47,92" (these go in promotional_info)
- Loyalty prices go in promotional_info"""

        # Add currency-specific range guidance (soft hint, never override actual displayed value)
        if range_info:
            lo, hi, name = range_info
            section += f"""

PRICE RANGE CONTEXT ({curr} - {name}):
Typical product prices in {curr} range from {lo} to {hi}.
IMPORTANT: Always report the EXACT value as displayed on the leaflet.
If a price seems unusually low (below {lo} {curr}), add "price_suspicious" to
uncertainty_flags but still report the exact displayed value — do NOT change it."""

        section += """

WHAT NOT TO EXTRACT:
- Section/category headers (e.g., "COFFEES AND CAPSULES", "ALL DUEL PRODUCTS")
- Category-level discount banners without individual product prices
- Only extract actual products with at least one visible price

COMMON MISTAKES TO AVOID:
- Do NOT put the only visible price in discounted_price — if there is NO discount badge, the price goes in regular_price
- Do NOT misread superscript prices (large "499" + small "99" = 499.99, NOT 4.99)
- Do NOT confuse unit price (per kg) with the actual product price
- Do NOT leave discount_percentage null when a "-XX%" badge is clearly visible
- Do NOT swap regular_price and discounted_price (regular is ALWAYS >= discounted)
- Do NOT round any amounts — return exact values as displayed
- Do NOT report a product with regular_price == discounted_price — if both prices are the same, there is no discount
- Do NOT assign a neighboring product's price or discount to the wrong product — each product card has its OWN prices
- Do NOT extract the same product twice — each physical product card should produce exactly ONE product entry
"""
        return section

    def _build_example_section(self) -> str:
        """Build the example output section."""
        example_output = {
            "page_number": 3,
            "products": [self.EXAMPLE_PRODUCT],
            "page_notes": "Standard grid layout, 4 products per row",
            "continuation_detected": False
        }
        
        return f"""
EXAMPLE OUTPUT:
```json
{json.dumps(example_output, indent=2)}
```
"""
    
    def build_validation_prompt(
        self,
        product_data: dict,
        page_image_context: bool = True
    ) -> str:
        """
        Build a prompt to validate/verify extracted data.
        
        Used for double-checking low-confidence extractions.
        
        Args:
            product_data: The extracted product data to validate
            page_image_context: Whether page image will be provided
            
        Returns:
            Validation prompt string
        """
        prompt = f"""Please verify the following extracted product data against the image.

EXTRACTED DATA:
```json
{json.dumps(product_data, indent=2)}
```

VERIFICATION TASKS:
1. Check if the bounding box correctly encompasses the entire product
2. Verify all text fields match what's visible in the image
3. Confirm prices are correctly identified (regular vs discounted)
4. Validate that the discount percentage is calculated correctly
5. Check for any missing information that should be extracted

OUTPUT FORMAT:
Respond with a JSON object:
{{
  "is_correct": true/false,
  "corrections": {{
    // Only include fields that need correction
    "field_name": "corrected_value"
  }},
  "missing_fields": ["list", "of", "missing", "fields"],
  "notes": "Any additional observations"
}}

Output ONLY valid JSON, no additional text.
"""
        return prompt

    def build_bbox_verification_prompt(
        self,
        products: list[dict],
        page_width: int = 2480,
        page_height: int = 3508,
    ) -> str:
        """
        Build a prompt for Pass 2: Visual verification of bounding boxes.

        This prompt is used with an image that has colored bounding boxes
        drawn on it, allowing the model to visually verify accuracy.

        Args:
            products: List of extracted products with bounding boxes
            page_width: Page width in pixels
            page_height: Page height in pixels

        Returns:
            Verification prompt string
        """
        # Build product list with box colors
        colors = ["RED", "BLUE", "GREEN", "YELLOW", "PURPLE", "ORANGE", "CYAN", "MAGENTA"]
        product_list = []
        for i, product in enumerate(products):
            color = colors[i % len(colors)]
            name = product.get("product_name", "Unknown")[:50]
            bbox = product.get("bounding_box", {})
            product_list.append(
                f"{i+1}. {color} box: \"{name}\" at ({bbox.get('x', 0)}, {bbox.get('y', 0)}) "
                f"size {bbox.get('width', 0)}×{bbox.get('height', 0)}"
            )

        products_text = "\n".join(product_list)

        prompt = f"""You are a BOUNDING BOX VERIFICATION SYSTEM.

I have drawn colored rectangles on this catalog page image showing detected product locations.
Your task is to verify each bounding box and correct any that are wrong.

IMAGE DIMENSIONS: {page_width}px × {page_height}px
COORDINATE SYSTEM: Origin (0,0) is TOP-LEFT corner

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DETECTED PRODUCTS WITH BOUNDING BOXES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{products_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VERIFICATION INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For EACH colored box, verify:
1. Does the box fully contain the product image?
2. Does the box include all price information?
3. Does the box include the product name and brand?
4. Does the box include discount badges?
5. Does the box have appropriate padding (10-15px)?
6. Does the box avoid overlapping with adjacent products?

COMMON ISSUES TO CHECK:
- Box too small (cuts off product image or text)
- Box too large (includes adjacent products)
- Box position shifted (wrong x/y coordinates)
- Box missing entirely for a visible product

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — JSON ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY valid JSON with corrections:

{{
  "verifications": [
    {{
      "product_index": 1,
      "product_name": "BIO BOROVNICE pakirano 125g",
      "is_correct": true,
      "corrected_bbox": null,
      "issue": null
    }},
    {{
      "product_index": 2,
      "product_name": "Milk 1L",
      "is_correct": false,
      "corrected_bbox": {{"x": 650, "y": 100, "width": 550, "height": 480}},
      "issue": "Box was too small, didn't include price"
    }}
  ],
  "missed_products": [
    {{
      "description": "Product in bottom-right corner not detected",
      "suggested_bbox": {{"x": 1800, "y": 2800, "width": 600, "height": 500}},
      "product_name": "Butter 250g"
    }}
  ],
  "notes": "Overall good detection, minor adjustments needed"
}}

Now verify ALL bounding boxes and provide corrections.
"""
        return prompt

    def build_grid_extraction_prompt(
        self,
        page_number: int,
        total_pages: int,
        grid_columns: int = 4,
        grid_rows: int = 6,
        context: Optional[ExtractionContext] = None,
    ) -> str:
        """
        Build extraction prompt using grid-based location instead of pixel coordinates.

        VLMs are better at identifying grid cells than exact pixel coordinates.
        The image should have a labeled grid overlay (A1, B1, A2, B2, etc.).

        Args:
            page_number: Current page number (1-indexed)
            total_pages: Total pages in leaflet
            grid_columns: Number of grid columns (A, B, C, D...)
            grid_rows: Number of grid rows (1, 2, 3, 4...)
            context: Optional extraction context

        Returns:
            Complete prompt string for VLM
        """
        context_section = self._build_context_section(context)
        currency = context.currency if context and context.currency else "EUR"
        pricing_rules = self._build_pricing_rules_section(currency)

        # Generate column labels
        col_labels = [chr(ord('A') + i) for i in range(grid_columns)]
        row_labels = [str(i + 1) for i in range(grid_rows)]

        prompt = f"""You are a PRODUCT EXTRACTION SYSTEM for retail catalog pages.

The image has a RED GRID OVERLAY with labeled cells to help you identify product locations.

GRID LAYOUT:
- Columns: {', '.join(col_labels)} (left to right)
- Rows: {', '.join(row_labels)} (top to bottom)
- Cell format: Column + Row (e.g., A1 = top-left, {col_labels[-1]}{row_labels[-1]} = bottom-right)

{context_section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOCATION INSTRUCTIONS (CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For EACH product, identify ALL grid cells it occupies.

Example: A product in the top-left spanning 2 columns and 2 rows:
→ grid_cells: ["A1", "B1", "A2", "B2"]

RULES:
✔ Include ALL cells that contain ANY part of the product
✔ Include cells with product image, text, prices, badges
✔ A typical product spans 1-2 columns and 2-3 rows
✔ List cells in order: top-to-bottom, left-to-right

DO NOT:
✖ Skip cells that contain part of the product
✖ Include cells from adjacent products
✖ Include cells with only page headers or whitespace

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRODUCT IDENTIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A product is a distinct item for sale with:
- Product image/photo
- Brand name
- Product name and description
- Price information
- Optional: discount badges, promotional offers

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA TO EXTRACT FOR EACH PRODUCT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Required fields:
- grid_cells: List of ALL grid cells containing this product (REQUIRED)
- brand: Brand name (null if not visible)
- product_code: SKU/article number if visible (null if not visible)
- product_name: Full product description
- quantity: Package size/weight as a number (e.g., 125 for "125g", 1.5 for "1.5L"). NOT the price! For products sold "per kg" without specific package weight, use null.
- units: Unit of measurement (g, kg, ml, L, pcs, pack)
- size: Size descriptor if shown separately (e.g., "family pack", "XL")
- regular_price: REQUIRED — the product's standard price. If discounted, the original higher price. If NO discount, the shown price. NEVER leave null if a price is visible.
- discounted_price: The sale/promotional price ONLY when a discount badge or crossed-out price is present (null if no discount)
- discount_percentage: From discount badge like "-50%" (null if none)
- currency: {currency}
- product_id: Barcode/EAN if visible
- promotional_info: Promo text, loyalty offers, multi-buy deals

Category fields:
- suggested_category: Most specific category from list below
- category_confidence: 0.0–1.0
- category_alternatives: Top 2-3 alternatives if confidence < 0.80

Quality fields:
- confidence_score: Overall extraction confidence (0.0–1.0)
- field_confidence: Per-field confidence scores
- uncertainty_flags: List any issues

{pricing_rules}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE CATEGORIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{get_category_loader().format_for_vlm_prompt(include_descriptions=True)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — JSON ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY valid JSON. No explanations. No markdown.

{{
  "page_number": {page_number},
  "products": [
    {{
      "grid_cells": ["A1", "B1", "A2", "B2"],
      "brand": "SPAR",
      "product_code": null,
      "product_name": "BIO BOROVNICE pakirano 125g",
      "quantity": 125,
      "units": "g",
      "size": null,
      "regular_price": 1.99,
      "discounted_price": 1.49,
      "discount_percentage": 33,
      "currency": "EUR",
      "product_id": null,
      "promotional_info": "33% CENEJE, s SPAR plus kartico €1.29",
      "suggested_category": "Fresh Fruit",
      "category_confidence": 0.95,
      "category_alternatives": null,
      "confidence_score": 0.94,
      "field_confidence": {{"brand": 0.95, "product_name": 0.96}},
      "uncertainty_flags": []
    }},
    {{
      "grid_cells": ["C1", "D1", "C2", "D2"],
      "brand": "MERCATOR",
      "product_name": "MLEKO 1L",
      ...
    }}
  ],
  "page_notes": "6 products found in grid layout",
  "continuation_detected": false
}}

IMPORTANT: Look at the RED grid lines and labels. Each product should span multiple cells.
Now extract ALL products with their EXACT grid cell locations.
"""
        return prompt

    def build_data_only_prompt(
        self,
        page_number: int,
        total_pages: int,
        context: Optional[ExtractionContext] = None,
    ) -> str:
        """
        Build extraction prompt for product DATA ONLY (no bounding boxes).

        Use this when bounding boxes will be detected via OCR (PaddleOCR).
        This reduces VLM cost by ~50% since no location detection is needed.

        Args:
            page_number: Current page number (1-indexed)
            total_pages: Total pages in leaflet
            context: Optional extraction context

        Returns:
            Complete prompt string for VLM
        """
        context_section = self._build_context_section(context)
        currency = context.currency if context and context.currency else "EUR"
        pricing_rules = self._build_pricing_rules_section(currency)

        prompt = f"""You are a PRODUCT DATA EXTRACTION SYSTEM for retail catalog pages.

Extract ALL product information from this page. Focus on DATA ACCURACY.
Bounding boxes will be detected separately - DO NOT provide location data.

{context_section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRODUCT IDENTIFICATION (CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT IS A PRODUCT?
Each product is displayed as a RECTANGULAR CARD containing:
- A product photo/image
- A bold price label (the main selling price)
- Product name and unit/size text
- Sometimes a discount badge (e.g., "-25%", "AKCIJA")

The card background is visually separated from neighboring products by
whitespace or borders and forms part of a GRID LAYOUT.

IMPORTANT RULES:
1. Each card = ONE sellable item = ONE product entry
2. If a design panel contains MULTIPLE products, treat each product
   offer as SEPARATE (they each have their own image + price + name)
3. Only group items together if they share ONE price as a bundle/pack
4. Look for visual boundaries: whitespace, borders, background color changes

WHAT DEFINES A PRODUCT OFFER:
- A product image PAIRED with its OWN price label
- Its OWN name/description text
- May share a promotional banner but has individual pricing

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA TO EXTRACT FOR EACH PRODUCT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Required fields:
- brand: Brand name (null if not visible)
- product_code: SKU/article number if visible (null if not visible)
- product_name: Full product description (IMPORTANT: be complete and accurate)
- quantity: Package size/weight as a number (e.g., 125 for "125g", 1.5 for "1.5L"). NOT the price! For products sold "per kg" without specific package weight, use null.
- units: Unit of measurement (g, kg, ml, L, pcs, pack)
- size: Size descriptor if shown separately (e.g., "family pack", "XL")
- regular_price: REQUIRED — the product's standard price. If discounted, the original higher price. If NO discount, the shown price. NEVER leave null if a price is visible.
- discounted_price: The sale/promotional price ONLY when a discount badge or crossed-out price is present (null if no discount)
- discount_percentage: From discount badge like "-50%" (null if none)
- currency: {currency}
- product_id: Barcode/EAN if visible
- promotional_info: Promo text, loyalty offers, multi-buy deals

Category fields:
- suggested_category: Most specific category from list below
- category_confidence: 0.0–1.0
- category_alternatives: Top 2-3 alternatives if confidence < 0.80

Quality fields:
- confidence_score: Overall extraction confidence (0.0–1.0)
- field_confidence: Per-field confidence scores
- uncertainty_flags: List any issues

{pricing_rules}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORIES (use most specific match)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{get_category_loader().format_for_vlm_prompt(compact=True)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT — JSON ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY valid JSON. No explanations.

{{
  "page_number": {page_number},
  "products": [
    {{
      "brand": "SPAR",
      "product_name": "BIO BOROVNICE 125g",
      "quantity": 125,
      "units": "g",
      "regular_price": 1.99,
      "discounted_price": 1.49,
      "discount_percentage": 33,
      "currency": "EUR",
      "promotional_info": "33% CENEJE",
      "suggested_category": "Fresh Fruit",
      "category_confidence": 0.95,
      "confidence_score": 0.94,
      "uncertainty_flags": []
    }}
  ],
  "page_notes": "8 products found",
  "continuation_detected": false
}}

Extract ALL products from this page.
"""
        return prompt

    def build_card_extraction_prompt(
        self,
        page_number: int,
        total_pages: int,
        num_regions: int,
        context: Optional[ExtractionContext] = None,
    ) -> str:
        """
        Build extraction prompt for card-first pipeline.

        The page image has been annotated with numbered colored boxes
        marking detected product card regions. The VLM should match
        each product to visible region number(s) instead of reporting
        pixel coordinates.

        Args:
            page_number: Current page number (1-indexed)
            total_pages: Total pages in leaflet
            num_regions: Number of annotated regions on the image
            context: Optional extraction context

        Returns:
            Complete prompt string for VLM
        """
        context_section = self._build_context_section(context)
        currency = context.currency if context and context.currency else "EUR"
        pricing_rules = self._build_pricing_rules_section(currency)

        prompt = f"""You are a PRODUCT EXTRACTION SYSTEM for retail catalog pages.

The image has NUMBERED COLORED BOXES drawn on it, marking detected product card regions.
Each box has a number label (1 through {num_regions}) in its top-left corner.

YOUR TASK: Extract product data and match each product to the numbered region(s) it appears in.

{context_section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGION MATCHING INSTRUCTIONS (CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For EACH product, identify which numbered region(s) contain it:
- "region_numbers": [3] — product is in region 3
- "region_numbers": [5, 6] — product spans regions 5 and 6
- "region_numbers": [] — product not covered by any numbered region

RULES:
✔ Look at the colored numbered boxes on the image
✔ Match each product to the box(es) that contain its image, name, and price
✔ A product spanning two adjacent regions should list both numbers
✔ Some regions may be empty (no product) — that's fine, just don't assign products to them
✔ Multiple products CAN share the same region number (if the grid cell contains more than one product)
✔ Report products NOT covered by any region in "unmatched_products"

DO NOT:
✖ Guess or fabricate pixel coordinates — use region numbers only
✖ Skip products just because they don't have a matching region

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRICE ISOLATION (CRITICAL — PREVENTS COMMON ERRORS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each product's price and discount belong ONLY to that product's visual card area.
Leaflet pages have a GRID of product cards. Each card is a distinct visual block
containing ONE product with its own image, name, price, and optional discount badge.

⚠ COMMON EXTRACTION ERROR — DO NOT MIX PRICES BETWEEN ADJACENT PRODUCTS:
- A price shown inside Product A's card belongs to Product A ONLY
- A discount badge inside Product B's card belongs to Product B ONLY
- NEVER assign a price from one product's card to a neighboring product
- If you are uncertain which card a price belongs to, add "price_uncertain" to uncertainty_flags

HOW TO VERIFY CORRECT PRICE ASSIGNMENT:
1. Locate each product's visual card boundary (its image, name text, price text)
2. The price closest to and visually grouped with the product name is that product's price
3. Discount badges (e.g., "-25%") apply ONLY to the product whose card they appear in
4. If a product card shows only ONE price and NO discount badge → that is regular_price, NOT discounted_price

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRODUCT IDENTIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A product is a distinct item for sale with:
- Product image/photo
- Brand name
- Product name and description
- Price information
- Optional: discount badges, promotional offers

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA TO EXTRACT FOR EACH PRODUCT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Required fields:
- region_numbers: List of region numbers this product occupies (REQUIRED)
- brand: Brand name (null if not visible)
- product_code: SKU/article number if visible (null if not visible)
- product_name: Full product description (IMPORTANT: be complete and accurate)
- quantity: Package size/weight as a number (e.g., 125 for "125g", 1.5 for "1.5L"). NOT the price! For products sold "per kg" without specific package weight, use null.
- units: Unit of measurement (g, kg, ml, L, pcs, pack)
- size: Size descriptor if shown separately (e.g., "family pack", "XL")
- regular_price: REQUIRED — the product's standard price. If discounted, the original higher price. If NO discount, the shown price. NEVER leave null if a price is visible.
- discounted_price: The sale/promotional price ONLY when a discount badge or crossed-out price is present (null if no discount)
- discount_percentage: From discount badge like "-50%" (null if none visible)
- currency: {currency}
- product_id: Barcode/EAN if visible
- promotional_info: Promo text, loyalty offers, multi-buy deals

Category fields:
- suggested_category: Most specific category from list below
- category_confidence: 0.0-1.0
- category_alternatives: Top 2-3 alternatives ONLY if confidence < 0.80

Quality fields:
- confidence_score: Overall extraction confidence (0.0-1.0)
- field_confidence: Per-field confidence scores (object with field names as keys)
- uncertainty_flags: List any issues (e.g., ["price_unclear", "region_uncertain"])

{pricing_rules}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE CATEGORIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{get_category_loader().format_for_vlm_prompt(include_descriptions=True)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT - JSON ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY valid JSON. No explanations. No markdown.

{{
  "page_number": {page_number},
  "products": [
    {{
      "region_numbers": [3],
      "brand": "SPAR",
      "product_code": null,
      "product_name": "BIO BOROVNICE pakirano 125g",
      "quantity": 125,
      "units": "g",
      "size": null,
      "regular_price": 1.99,
      "discounted_price": 1.49,
      "discount_percentage": 33,
      "currency": "EUR",
      "product_id": null,
      "promotional_info": "33% CENEJE, s SPAR plus kartico EUR1.29",
      "suggested_category": "Fresh Fruit",
      "category_confidence": 0.95,
      "category_alternatives": null,
      "confidence_score": 0.94,
      "field_confidence": {{"brand": 0.95, "product_name": 0.96, "discounted_price": 0.98}},
      "uncertainty_flags": []
    }},
    {{
      "region_numbers": [5, 6],
      "brand": "MERCATOR",
      "product_name": "Maslo 250g",
      "regular_price": 2.49,
      "discounted_price": null,
      "discount_percentage": null,
      "confidence_score": 0.90,
      "uncertainty_flags": ["spans_two_regions"]
    }}
  ],
  "unmatched_products": [
    {{
      "description": "Small product at page bottom not covered by any numbered region",
      "product_name": "Chewing gum",
      "regular_price": 0.99
    }}
  ],
  "page_notes": "Grid layout with numbered regions. Products matched to regions.",
  "continuation_detected": false
}}

Now look at the NUMBERED BOXES on the image and extract ALL products, matching each to its region number(s).
"""
        return prompt

    def build_count_products_prompt(self) -> str:
        """
        Build a prompt to count the total number of products on a page.

        This is the first step in count-first verification - establishing
        the expected product count before extraction.

        Returns:
            Count prompt string
        """
        return """Count the EXACT number of distinct PRODUCTS on this retail catalog page.

WHAT COUNTS AS A PRODUCT:
- Has a product name/description
- Has a visible price tag
- Is something a customer can purchase

WHAT DOES NOT COUNT:
- Section headers or category titles (e.g., "MEAT", "DAIRY")
- Promotional banners without specific products
- Store logos or decorative elements
- The same product shown twice (count once)

IMPORTANT:
- Count EVERY product, including small ones in corners
- Count products in promotional banners IF they have names and prices
- Be thorough - scan the entire page systematically

OUTPUT FORMAT (JSON only):
{
  "product_count": <exact number>,
  "confidence": "high" | "medium" | "low",
  "notes": "Any observations about the page layout"
}"""

    def build_find_missing_prompt(
        self,
        extracted_products: list[dict],
        expected_count: int,
        missing_count: int,
        context: Optional[ExtractionContext] = None,
    ) -> str:
        """
        Build a prompt to find specific missing products.

        Used when we know exactly how many products are missing based on
        the count-first verification.

        Args:
            extracted_products: Products already extracted
            expected_count: Total products expected on page
            missing_count: Number of products we're missing
            context: Optional extraction context

        Returns:
            Find-missing prompt string
        """
        extracted_summary = []
        for p in extracted_products:
            name = p.get("product_name", "Unknown")
            price = p.get("discounted_price") or p.get("regular_price") or "N/A"
            extracted_summary.append(f"- {name} ({price})")

        extracted_list = "\n".join(extracted_summary) if extracted_summary else "(none)"
        currency = context.currency if context and context.currency else "EUR"

        return f"""VERIFICATION SCAN: Look for ANY products we might have missed on this retail catalog page.

PRODUCTS ALREADY EXTRACTED ({expected_count - missing_count} total):
{extracted_list}

YOUR TASK:
Scan the ENTIRE page and find ANY products NOT in the list above. We estimate {missing_count} may be missing, but there could be more or fewer.

CRITICAL SEARCH AREAS (products are often missed here):
1. PAGE EDGES - Scan 2cm from all edges (top, bottom, left, right)
2. ALL FOUR CORNERS - Products are frequently cropped or small in corners
3. INSIDE PROMOTIONAL BANNERS - Red/yellow sales banners often contain products
4. HEADER/FOOTER AREAS - Special offers sometimes appear here
5. BETWEEN LARGER PRODUCTS - Small items squeezed between big ones
6. OVERLAPPING CONTENT - Products partially hidden behind graphics
7. SMALL TEXT AREAS - Products with small fonts or prices
8. CATEGORY DIVIDERS - Products on section boundary lines

LOOK FOR THESE COMMON MISSED PRODUCTS:
- Snacks (chips, peanuts, crackers) - often in corners
- Beverages - often in promotional strips
- Small grocery items (spices, soups, sauces)
- Products with multi-pack pricing
- Products with small discount badges

For EACH missing product you find, extract ALL available information.

OUTPUT FORMAT (JSON only):
{{
  "missing_products": [
    {{
      "product_name": "Full product name as shown on page",
      "brand": "Brand if visible (null if not)",
      "regular_price": <price as number>,
      "discounted_price": <sale price if discounted, null otherwise>,
      "discount_percentage": <percentage if shown, null otherwise>,
      "currency": "{currency}",
      "size": "Size/quantity if visible (e.g., '300g', '500ml')",
      "product_code": "SKU/barcode if visible (null if not)",
      "location_description": "Where on the page you found it (e.g., 'bottom right corner')"
    }}
  ],
  "areas_checked": ["list of areas you scanned"],
  "search_notes": "Any observations about the page layout or search difficulties"
}}

Return empty missing_products array if you find no additional products after thorough scanning."""

    def build_verification_prompt(
        self,
        page_number: int,
        extracted_products: list[dict],
        context: Optional[ExtractionContext] = None,
    ) -> str:
        """
        Build a prompt to verify extraction completeness (legacy method).

        This prompt asks the VLM to scan the ORIGINAL (non-annotated) image
        and list all products it sees, so we can identify any missed during
        the card-first extraction.

        Args:
            page_number: Current page number
            extracted_products: Products already extracted (for comparison)
            context: Optional extraction context

        Returns:
            Verification prompt
        """
        # Build list of already extracted products for reference
        extracted_summary = []
        for p in extracted_products:
            name = p.get("product_name", "Unknown")
            price = p.get("discounted_price") or p.get("regular_price") or "N/A"
            extracted_summary.append(f"- {name} ({price})")

        extracted_list = "\n".join(extracted_summary) if extracted_summary else "(none)"
        currency = context.currency if context and context.currency else "EUR"

        prompt = f"""You are verifying that ALL products were extracted from this retail catalog page.

ALREADY EXTRACTED PRODUCTS:
{extracted_list}

YOUR TASK:
Carefully scan the ENTIRE page and identify ANY products that are NOT in the list above.

A product is considered MISSING if:
- Its name is not in the extracted list (even with slight spelling variations)
- It has a visible price tag

CRITICAL RULES:
- Look at EVERY corner and edge of the page
- Check for small products that might be overlooked
- Check promotional banners that contain actual product offers
- Do NOT report section headers or decorative text as products

OUTPUT FORMAT (JSON only, no other text):
{{
  "verification_complete": true,
  "total_products_on_page": <number of products you see>,
  "already_extracted_count": {len(extracted_products)},
  "missing_products": [
    {{
      "product_name": "Full product name as shown",
      "brand": "Brand if visible (null if not)",
      "regular_price": <price as number>,
      "discounted_price": <sale price if discounted, null otherwise>,
      "discount_percentage": <percentage if shown, null otherwise>,
      "currency": "{currency}",
      "size": "Size/quantity if visible (e.g., '300g')",
      "location_hint": "Brief description of where on the page (e.g., 'bottom right corner')"
    }}
  ],
  "notes": "Any observations about the page layout or extraction quality"
}}

If no products are missing, return empty array for missing_products.
Look carefully - even one missed product is important!
"""
        return prompt

    def build_simple_listing_prompt(
        self,
        context: Optional[ExtractionContext] = None,
    ) -> str:
        """
        Build a simple prompt that just asks VLM to list all products.

        This is used for "fresh extraction" verification - a completely
        independent second pass that doesn't reference previous extractions.
        The goal is to catch products missed by the card-first approach.

        Args:
            context: Optional extraction context

        Returns:
            Simple listing prompt
        """
        currency = context.currency if context and context.currency else "EUR"

        return f"""List EVERY product you can see on this retail catalog/leaflet page.

WHAT TO LOOK FOR:
- Products with visible prices
- Products in promotional banners
- Products in corners and edges of the page
- Small products between larger ones
- Products with discount badges

For EACH product, extract:
- product_name: Full name as shown
- brand: Brand name if visible (null if not)
- regular_price: The price (original price if discounted)
- discounted_price: Sale price if there's a discount (null if no discount)
- discount_percentage: Percentage if shown (null if not)
- size: Size/weight/quantity (e.g., "300g", "1L")
- location: Where on page (e.g., "top left", "bottom right corner")

OUTPUT FORMAT (JSON only):
{{
  "products": [
    {{
      "product_name": "Example Product Name",
      "brand": "Brand",
      "regular_price": 2.99,
      "discounted_price": 1.99,
      "discount_percentage": 33,
      "currency": "{currency}",
      "size": "500g",
      "location": "center left"
    }}
  ],
  "total_count": <number of products found>
}}

Be thorough - scan the ENTIRE page including all corners and edges."""

    def build_continuation_prompt(
        self,
        previous_page_products: list[dict],
        current_page_number: int,
    ) -> str:
        """
        Build a prompt for handling products that span pages.

        Args:
            previous_page_products: Products from previous page
            current_page_number: Current page number

        Returns:
            Continuation detection prompt
        """
        prompt = f"""Analyzing page {current_page_number} for product continuations.

PRODUCTS FROM PREVIOUS PAGE (that may continue):
```json
{json.dumps(previous_page_products, indent=2)}
```

TASK:
1. Check if any products at the TOP of this page are continuations of products from the previous page
2. If a continuation is found, merge the information
3. Extract any NEW products on this page as separate entries

For continuations, include in uncertainty_flags: ["continuation_from_previous_page"]
For new products starting on this page, use normal extraction.

OUTPUT FORMAT:
Standard extraction JSON with continuation handling noted in uncertainty_flags.
"""
        return prompt


# Singleton instance for easy access
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    """Get or create the prompt builder singleton."""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder