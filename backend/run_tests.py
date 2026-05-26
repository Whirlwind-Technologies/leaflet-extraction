"""
Quick test runner that sets up environment before importing conftest.
"""
import os
import sys

# Set required environment variables BEFORE any imports
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-12345678"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "postgres"
os.environ["POSTGRES_DB"] = "leaflet_db"
os.environ["CORS_ORIGINS"] = "http://localhost:3000,http://localhost:8000"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["ANTHROPIC_API_KEY"] = "test-key-12345678901234567890"

# Now run pytest
import pytest

sys.exit(pytest.main([
    "tests/unit/test_leaflet_performance.py",
    "-v",
    "--tb=short",
    "-x",  # Stop on first failure
]))
