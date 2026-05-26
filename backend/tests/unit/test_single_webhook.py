"""Debug single failing test."""

import sys
sys.path.insert(0, '.')

from app.utils.url_validation import validate_webhook_url
from app.utils.exceptions import ValidationException

print("Testing validate_webhook_url with private IP...")

try:
    validate_webhook_url("http://127.0.0.1/hook")
    print("ERROR: No exception was raised!")
except ValidationException as exc:
    print(f"SUCCESS: ValidationException raised")
    print(f"  Message: {exc.message}")
    print(f"  Errors: {exc.errors}")
    assert "private or internal ip" in str(exc.message).lower()
    assert exc.errors[0]["field"] == "url"
    print("Test PASSED!")
except Exception as exc:
    print(f"ERROR: Wrong exception type: {type(exc).__name__}")
    print(f"  Message: {exc}")
    import traceback
    traceback.print_exc()
