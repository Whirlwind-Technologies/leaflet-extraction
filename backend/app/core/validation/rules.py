"""
Validation Rules Module.

This module provides individual validation rules for product fields.
Each rule returns a tuple of (is_valid, error_message).

Example Usage:
    from app.core.validation.rules import validate_price
    
    is_valid, error = validate_price(2.99, "EUR")
    if not is_valid:
        print(f"Price validation failed: {error}")
"""

import re
from typing import Optional, Tuple

from app.core.extraction.schemas import BoundingBox


# Price ranges by currency (min, max)
PRICE_RANGES = {
    "EUR": (0.01, 10000),
    "USD": (0.01, 10000),
    "GBP": (0.01, 10000),
    "CHF": (0.01, 10000),
    "PLN": (0.01, 50000),
    "CZK": (0.10, 500000),
    "SEK": (0.10, 100000),
    "NOK": (0.10, 100000),
    "DKK": (0.10, 100000),
    "HUF": (1, 5000000),
    "RON": (0.10, 50000),
    "BGN": (0.10, 20000),
    "HRK": (0.10, 100000),
    # Balkan/Adriatic currencies
    "RSD": (1, 1000000),  # Serbian Dinar
    "BAM": (0.10, 50000),  # Bosnian Mark
    "MKD": (1, 500000),   # Macedonian Denar
    "ALL": (1, 1000000),   # Albanian Lek
    "default": (0.01, 1000000),  # Increased default max for non-Euro countries
}

# Common unit patterns
VALID_UNITS = {
    # Weight
    "g", "gr", "gram", "grams",
    "kg", "kilo", "kilos", "kilogram", "kilograms",
    "mg", "milligram", "milligrams",
    "lb", "lbs", "pound", "pounds",
    "oz", "ounce", "ounces",
    "dag", "dkg", "dekagram",  # Common in Balkans (10g)
    # Volume
    "ml", "milliliter", "milliliters", "millilitre", "millilitres",
    "l", "lt", "ltr", "liter", "liters", "litre", "litres",
    "cl", "centiliter", "centiliters",
    "dl", "deciliter", "deciliters",
    "fl oz", "fluid oz",
    "gal", "gallon", "gallons",
    "pt", "pint", "pints",
    # Count
    "pc", "pcs", "piece", "pieces",
    "pk", "pack", "packs", "packet", "packets",
    "box", "boxes",
    "can", "cans",
    "bottle", "bottles",
    "jar", "jars",
    "bag", "bags",
    "roll", "rolls",
    "sheet", "sheets",
    "tablet", "tablets",
    "capsule", "capsules",
    "dose", "doses",
    "serving", "servings",
    "portion", "portions",
    "pair", "pairs",
    "set", "sets",
    "unit", "units",
    "each",
    "x",  # For multipacks like "6x"
    "stk", "stück",  # German
    "szt", "sztuk",  # Polish
    "ks", "kus",  # Czech
    "db", "darab",  # Hungarian
    # Balkan/Serbian units
    "kom", "komad", "komada",  # Serbian/Croatian pieces
    "par", "para",  # Pair
    "pakovanje", "pak",  # Package
    "flaša", "flasa",  # Bottle (Serbian)
    "limenka",  # Can (Serbian)
    "pranja",  # Washes (for detergent)
    "led",  # LED (for lights)
    "cm",  # Centimeters (for decorations)
    "m",  # Meters
}

# Product code patterns
PRODUCT_CODE_PATTERNS = [
    r'^[A-Z]{2,4}-[A-Z0-9]{2,10}$',  # XX-XXXXX
    r'^[A-Z0-9]{4,20}$',  # Alphanumeric
    r'^\d{4,13}$',  # Numeric (UPC, EAN)
    r'^[A-Z]{1,3}\d{4,10}$',  # Letter prefix + numbers
    r'^\d{1,5}[A-Z]{1,3}\d{1,5}$',  # Mixed format
]


def validate_price(
    price: Optional[float],
    currency: Optional[str] = None,
    field_name: str = "price",
) -> Tuple[bool, Optional[str]]:
    """
    Validate a price value.
    
    Args:
        price: Price to validate
        currency: Currency code for range checking
        field_name: Name of field for error messages
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if price is None:
        return True, None  # None is valid (field may be optional)
    
    # Check for negative
    if price < 0:
        return False, f"{field_name} cannot be negative"
    
    # Get price range for currency
    currency_upper = (currency or "default").upper()
    min_price, max_price = PRICE_RANGES.get(
        currency_upper,
        PRICE_RANGES["default"]
    )
    
    # Check range
    if price < min_price:
        return False, f"{field_name} ({price}) is below minimum ({min_price})"
    
    if price > max_price:
        return False, f"{field_name} ({price}) exceeds maximum ({max_price})"
    
    return True, None


def validate_discount(
    regular_price: Optional[float],
    discounted_price: Optional[float],
    discount_percentage: Optional[float],
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate discount-related fields.
    
    Args:
        regular_price: Original price
        discounted_price: Sale price
        discount_percentage: Stated discount
        
    Returns:
        Tuple of (is_valid, error_message, warning_message)
    """
    # Both prices needed for comparison
    if regular_price is None or discounted_price is None:
        return True, None, None
    
    # Regular should be >= discounted
    if regular_price < discounted_price:
        return False, "Regular price is less than discounted price", None
    
    # Calculate expected discount
    if regular_price > 0:
        calculated_discount = (
            (regular_price - discounted_price) / regular_price
        ) * 100
        
        # Check if discount percentage matches
        if discount_percentage is not None:
            difference = abs(discount_percentage - calculated_discount)
            
            # Allow 2% tolerance
            if difference > 2:
                warning = (
                    f"Stated discount ({discount_percentage}%) differs from "
                    f"calculated ({calculated_discount:.1f}%)"
                )
                return True, None, warning
        
        # Warn about very high discounts
        if calculated_discount > 90:
            warning = f"Very high discount ({calculated_discount:.1f}%) - please verify"
            return True, None, warning
    
    return True, None, None


def validate_quantity(
    quantity: Optional[float],
    units: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """
    Validate quantity and units.
    
    Args:
        quantity: Numeric quantity
        units: Unit of measurement
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if quantity is None:
        return True, None
    
    # Quantity must be positive
    if quantity <= 0:
        return False, "Quantity must be positive"
    
    # Check for unreasonably large quantities
    if quantity > 10000:
        return False, f"Quantity ({quantity}) seems unreasonably large"
    
    # Validate units if provided
    if units:
        units_lower = units.lower().strip()
        if units_lower not in VALID_UNITS:
            # Check for unit with number prefix (e.g., "6x", "12pk")
            if not re.match(r'^\d+\s*(x|pk|pcs?|pc)$', units_lower, re.IGNORECASE):
                return True, None  # Unknown unit, but not an error
    
    return True, None


def validate_bounding_box(
    bbox: Optional[BoundingBox],
    page_width: int,
    page_height: int,
) -> Tuple[bool, Optional[str]]:
    """
    Validate bounding box coordinates.

    Args:
        bbox: Bounding box to validate (may be None if detected via OCR post-processing)
        page_width: Page width in pixels
        page_height: Page height in pixels

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Handle None bounding box (will be filled by OCR or has fallback)
    if bbox is None:
        return True, None  # Allow None - OCR will fill it in or fallback was used

    # Check within page bounds
    if bbox.x < 0 or bbox.y < 0:
        return False, "Bounding box has negative coordinates"
    
    if bbox.x + bbox.width > page_width:
        return False, f"Bounding box extends beyond page width ({page_width}px)"
    
    if bbox.y + bbox.height > page_height:
        return False, f"Bounding box extends beyond page height ({page_height}px)"
    
    # Check minimum size (50x50 pixels - absolute minimum)
    if bbox.width < 50 or bbox.height < 50:
        return False, "Bounding box is too small (minimum 50x50 pixels)"
    
    # Check for suspiciously small product cards (typical product cards are at least 150x200)
    # These are valid but should be flagged for review
    if bbox.width < 150 or bbox.height < 200:
        # This is a warning case - product card seems small
        # We return True (valid) but the caller should consider flagging for review
        pass
    
    # Check maximum size (shouldn't be larger than 90% of the page)
    if bbox.width > page_width * 0.9 or bbox.height > page_height * 0.9:
        return True, None  # Warning level, not error
    
    return True, None


def validate_product_code(
    code: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """
    Validate product code format.
    
    Args:
        code: Product code to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if code is None:
        return True, None
    
    code = code.strip()
    
    # Check length
    if len(code) < 3:
        return False, "Product code is too short (minimum 3 characters)"
    
    if len(code) > 30:
        return False, "Product code is too long (maximum 30 characters)"
    
    # Check for suspicious patterns
    if code.lower() in ("n/a", "na", "none", "null", "-", "---"):
        return False, "Product code appears to be a placeholder"
    
    return True, None


def validate_product_name(
    name: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """
    Validate product name.
    
    Args:
        name: Product name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Product name is required"
    
    name = name.strip()
    
    # Check length
    if len(name) < 2:
        return False, "Product name is too short"
    
    if len(name) > 500:
        return False, "Product name is too long (maximum 500 characters)"
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'^[\d\s\.]+$',  # Only numbers
        r'^[^\w\s]+$',  # Only special characters
        r'^(test|sample|dummy|placeholder)',  # Test data
    ]
    
    for pattern in suspicious_patterns:
        if re.match(pattern, name, re.IGNORECASE):
            return False, "Product name appears to be invalid"
    
    return True, None


def validate_currency(
    currency: Optional[str],
    expected_currency: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate currency code.
    
    Args:
        currency: Currency to validate
        expected_currency: Expected currency for the leaflet
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not currency:
        return True, None
    
    # Normalize currency
    currency_normalized = currency.upper().strip()
    
    # Map symbols to codes
    symbol_map = {
        "€": "EUR",
        "$": "USD",
        "£": "GBP",
        "CHF": "CHF",
        "ZŁ": "PLN",
        "KČ": "CZK",
        "KR": "SEK",  # Could also be NOK/DKK
        "FT": "HUF",
        "LEI": "RON",
    }
    
    if currency_normalized in symbol_map:
        currency_normalized = symbol_map[currency_normalized]
    
    # Check if valid currency code
    valid_currencies = set(PRICE_RANGES.keys()) - {"default"}
    if currency_normalized not in valid_currencies:
        # Not necessarily an error, could be a valid but unknown currency
        return True, None
    
    # Check if matches expected
    if expected_currency and currency_normalized != expected_currency.upper():
        return True, None  # Warning level - mixed currencies might be valid
    
    return True, None