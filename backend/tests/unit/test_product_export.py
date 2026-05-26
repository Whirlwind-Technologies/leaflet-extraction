#!/usr/bin/env python
"""
Unit tests for product export feature.

Tests schema validation, export storage path generation, ExportJob model,
and export service pure functions without requiring database or pytest.

Run with: python tests/unit/test_product_export.py
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4, UUID
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError

# Import test subjects
from app.schemas.product_export import (
    ProductExportRequest,
    ProductExportFilters,
    ReviewQueueExportFilters,
    ExportMode,
    ExportFormat,
    ExportImageStorage,
)
from app.utils.export_storage import _export_path, _infer_content_type
from app.models.export_job import ExportJob
from app.services.export_service import (
    _format_file_size,
    estimate_export_size,
    SIZE_ESTIMATES_PER_PRODUCT,
)


def run_product_export_filters_tests():
    """Test ProductExportFilters validation."""
    print("\n" + "="*70)
    print("TESTING: ProductExportFilters Schema Validation")
    print("="*70)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Valid filter combinations
    try:
        filters = ProductExportFilters(
            search="Coca-Cola",
            review_status=["approved", "auto_approved"],
            min_confidence=0.8,
            category="Beverages",
            brand="Coca-Cola",
            page_number=5,
            validation_passed=True,
            sort_by="created_at",
            sort_order="desc",
        )
        assert filters.search == "Coca-Cola"
        assert len(filters.review_status) == 2
        assert filters.min_confidence == 0.8
        print("[PASS] Valid filter combinations")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Valid filter combinations: {e}")
        tests_failed += 1

    # Test 2: min_confidence range validation (0-1)
    try:
        ProductExportFilters(min_confidence=-0.1)
        print("[FAIL] min_confidence should reject negative values")
        tests_failed += 1
    except ValidationError:
        print("[PASS] min_confidence rejects negative values")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] min_confidence negative test: {e}")
        tests_failed += 1

    # Test 3: min_confidence upper bound
    try:
        ProductExportFilters(min_confidence=1.1)
        print("[FAIL] min_confidence should reject >1")
        tests_failed += 1
    except ValidationError:
        print("[PASS] min_confidence rejects >1")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] min_confidence upper bound test: {e}")
        tests_failed += 1

    # Test 4: Valid sort_by columns
    try:
        valid_columns = [
            "created_at", "updated_at", "product_name", "brand",
            "regular_price", "discounted_price", "discount_percentage",
            "confidence", "page_number", "review_status", "category"
        ]
        for col in valid_columns:
            filters = ProductExportFilters(sort_by=col)
            assert filters.sort_by == col
        print("[PASS] All valid sort_by columns accepted")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Valid sort_by columns: {e}")
        tests_failed += 1

    # Test 5: Invalid sort_by column rejected
    try:
        ProductExportFilters(sort_by="invalid_column")
        print("[FAIL] Invalid sort_by should be rejected")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Invalid sort_by rejected")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Invalid sort_by test: {e}")
        tests_failed += 1

    # Test 6: sort_order restricted to asc/desc
    try:
        ProductExportFilters(sort_order="asc")
        ProductExportFilters(sort_order="desc")
        print("[PASS] Valid sort_order values accepted")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Valid sort_order: {e}")
        tests_failed += 1

    # Test 7: Invalid sort_order rejected
    try:
        ProductExportFilters(sort_order="invalid")
        print("[FAIL] Invalid sort_order should be rejected")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Invalid sort_order rejected")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Invalid sort_order test: {e}")
        tests_failed += 1

    # Test 8: review_status validates against known statuses
    try:
        ProductExportFilters(review_status=["approved", "pending", "rejected"])
        print("[PASS] Valid review_status values accepted")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Valid review_status: {e}")
        tests_failed += 1

    # Test 9: Invalid review_status rejected
    try:
        ProductExportFilters(review_status=["invalid_status"])
        print("[FAIL] Invalid review_status should be rejected")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Invalid review_status rejected")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Invalid review_status test: {e}")
        tests_failed += 1

    # Test 10: Default values
    try:
        filters = ProductExportFilters()
        assert filters.sort_by == "created_at"
        assert filters.sort_order == "desc"
        assert filters.search is None
        assert filters.min_confidence is None
        print("[PASS] Default values correct")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Default values: {e}")
        tests_failed += 1

    return tests_passed, tests_failed


def run_product_export_request_tests():
    """Test ProductExportRequest validation."""
    print("\n" + "="*70)
    print("TESTING: ProductExportRequest Schema Validation")
    print("="*70)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Valid request for mode=all
    try:
        req = ProductExportRequest(
            format=ExportFormat.CSV,
            image_storage=ExportImageStorage.URL,
            mode=ExportMode.ALL,
        )
        assert req.mode == ExportMode.ALL
        assert req.filters is None
        assert req.product_ids is None
        print("[PASS] Valid request for mode=all")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Valid request mode=all: {e}")
        tests_failed += 1

    # Test 2: Mode=all rejects filters
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.ALL,
            filters=ProductExportFilters(),
        )
        print("[FAIL] Mode=all should reject filters")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=all rejects filters")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=all rejects filters test: {e}")
        tests_failed += 1

    # Test 3: Mode=all rejects product_ids
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.ALL,
            product_ids=[uuid4()],
        )
        print("[FAIL] Mode=all should reject product_ids")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=all rejects product_ids")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=all rejects product_ids test: {e}")
        tests_failed += 1

    # Test 4: Mode=all rejects review_queue_filters
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.ALL,
            review_queue_filters=ReviewQueueExportFilters(),
        )
        print("[FAIL] Mode=all should reject review_queue_filters")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=all rejects review_queue_filters")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=all rejects review_queue_filters test: {e}")
        tests_failed += 1

    # Test 5: Valid request for mode=filtered
    try:
        req = ProductExportRequest(
            format=ExportFormat.EXCEL,
            mode=ExportMode.FILTERED,
            filters=ProductExportFilters(
                review_status=["approved"],
                min_confidence=0.9,
            ),
        )
        assert req.mode == ExportMode.FILTERED
        assert req.filters is not None
        assert req.product_ids is None
        print("[PASS] Valid request for mode=filtered")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Valid request mode=filtered: {e}")
        tests_failed += 1

    # Test 6: Mode=filtered requires filters
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.FILTERED,
        )
        print("[FAIL] Mode=filtered should require filters")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=filtered requires filters")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=filtered requires filters test: {e}")
        tests_failed += 1

    # Test 7: Mode=filtered rejects product_ids
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.FILTERED,
            filters=ProductExportFilters(),
            product_ids=[uuid4()],
        )
        print("[FAIL] Mode=filtered should reject product_ids")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=filtered rejects product_ids")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=filtered rejects product_ids test: {e}")
        tests_failed += 1

    # Test 8: Valid request for mode=selected
    try:
        ids = [uuid4() for _ in range(10)]
        req = ProductExportRequest(
            format=ExportFormat.JSON,
            mode=ExportMode.SELECTED,
            product_ids=ids,
        )
        assert req.mode == ExportMode.SELECTED
        assert len(req.product_ids) == 10
        print("[PASS] Valid request for mode=selected")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Valid request mode=selected: {e}")
        tests_failed += 1

    # Test 9: Mode=selected requires product_ids
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.SELECTED,
        )
        print("[FAIL] Mode=selected should require product_ids")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=selected requires product_ids")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=selected requires product_ids test: {e}")
        tests_failed += 1

    # Test 10: Mode=selected accepts 1-500 product_ids
    try:
        # 1 ID (minimum)
        req = ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.SELECTED,
            product_ids=[uuid4()],
        )
        assert len(req.product_ids) == 1

        # 500 IDs (maximum)
        req = ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.SELECTED,
            product_ids=[uuid4() for _ in range(500)],
        )
        assert len(req.product_ids) == 500
        print("[PASS] Mode=selected accepts 1-500 product_ids")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=selected 1-500 product_ids: {e}")
        tests_failed += 1

    # Test 11: Mode=selected rejects over 500 product_ids
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.SELECTED,
            product_ids=[uuid4() for _ in range(501)],
        )
        print("[FAIL] Mode=selected should reject >500 product_ids")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=selected rejects >500 product_ids")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=selected >500 test: {e}")
        tests_failed += 1

    # Test 12: Mode=selected rejects empty product_ids
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.SELECTED,
            product_ids=[],
        )
        print("[FAIL] Mode=selected should reject empty product_ids")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=selected rejects empty product_ids")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=selected empty test: {e}")
        tests_failed += 1

    # Test 13: Mode=selected rejects duplicate product_ids
    try:
        id1 = uuid4()
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.SELECTED,
            product_ids=[id1, id1, id1],
        )
        print("[FAIL] Mode=selected should reject duplicate product_ids")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=selected rejects duplicate product_ids")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=selected duplicate test: {e}")
        tests_failed += 1

    # Test 14: Mode=selected rejects invalid UUID strings
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.SELECTED,
            product_ids=["not-a-uuid"],
        )
        print("[FAIL] Mode=selected should reject invalid UUID strings")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=selected rejects invalid UUID strings")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=selected invalid UUID test: {e}")
        tests_failed += 1

    # Test 15: Valid request for mode=review_queue
    try:
        req = ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.REVIEW_QUEUE,
        )
        assert req.mode == ExportMode.REVIEW_QUEUE
        assert req.review_queue_filters is None
        print("[PASS] Valid request for mode=review_queue (no filters)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Valid request mode=review_queue: {e}")
        tests_failed += 1

    # Test 16: Mode=review_queue accepts optional review_queue_filters
    try:
        req = ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.REVIEW_QUEUE,
            review_queue_filters=ReviewQueueExportFilters(
                leaflet_id=str(uuid4())
            ),
        )
        assert req.review_queue_filters is not None
        print("[PASS] Mode=review_queue accepts optional review_queue_filters")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=review_queue with filters: {e}")
        tests_failed += 1

    # Test 17: Mode=review_queue rejects filters
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.REVIEW_QUEUE,
            filters=ProductExportFilters(),
        )
        print("[FAIL] Mode=review_queue should reject filters")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=review_queue rejects filters")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=review_queue rejects filters test: {e}")
        tests_failed += 1

    # Test 18: Mode=review_queue rejects product_ids
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            mode=ExportMode.REVIEW_QUEUE,
            product_ids=[uuid4()],
        )
        print("[FAIL] Mode=review_queue should reject product_ids")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Mode=review_queue rejects product_ids")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Mode=review_queue rejects product_ids test: {e}")
        tests_failed += 1

    # Test 19: Invalid format rejected
    try:
        ProductExportRequest(
            format="xml",
            mode=ExportMode.ALL,
        )
        print("[FAIL] Invalid format should be rejected")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Invalid format rejected")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Invalid format test: {e}")
        tests_failed += 1

    # Test 20: Invalid image_storage rejected
    try:
        ProductExportRequest(
            format=ExportFormat.CSV,
            image_storage="invalid",
            mode=ExportMode.ALL,
        )
        print("[FAIL] Invalid image_storage should be rejected")
        tests_failed += 1
    except ValidationError:
        print("[PASS] Invalid image_storage rejected")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Invalid image_storage test: {e}")
        tests_failed += 1

    # Test 21: Default values
    try:
        req = ProductExportRequest(mode=ExportMode.ALL)
        assert req.format == ExportFormat.CSV
        assert req.image_storage == ExportImageStorage.URL
        print("[PASS] Default values correct")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Default values: {e}")
        tests_failed += 1

    return tests_passed, tests_failed


def run_export_storage_tests():
    """Test export storage utility functions."""
    print("\n" + "="*70)
    print("TESTING: Export Storage Utilities")
    print("="*70)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Export path generation
    try:
        org_id = uuid4()
        export_id = "abc-123"
        path = _export_path(org_id, export_id, "csv")
        expected = f"exports/{org_id}/abc-123.csv"
        assert path == expected
        print("[PASS] Export path generation correct")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Export path generation: {e}")
        tests_failed += 1

    # Test 2: Export path with different formats
    try:
        org_id = uuid4()
        export_id = str(uuid4())

        csv_path = _export_path(org_id, export_id, "csv")
        assert csv_path.endswith(".csv")

        xlsx_path = _export_path(org_id, export_id, "xlsx")
        assert xlsx_path.endswith(".xlsx")

        json_path = _export_path(org_id, export_id, "json")
        assert json_path.endswith(".json")

        print("[PASS] Export path with different formats")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Export path formats: {e}")
        tests_failed += 1

    # Test 3: Infer content type from file format
    try:
        assert _infer_content_type("csv") == "text/csv"
        assert _infer_content_type("xlsx") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert _infer_content_type("json") == "application/json"
        assert _infer_content_type("zip") == "application/zip"
        print("[PASS] Content type inference correct")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Content type inference: {e}")
        tests_failed += 1

    # Test 4: Infer content type for unknown format
    try:
        content_type = _infer_content_type("unknown")
        assert content_type == "application/octet-stream"
        print("[PASS] Unknown format returns octet-stream")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Unknown format content type: {e}")
        tests_failed += 1

    # Test 5: Content type case insensitive
    try:
        assert _infer_content_type("CSV") == "text/csv"
        assert _infer_content_type("XLSX") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        print("[PASS] Content type inference case insensitive")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Content type case insensitive: {e}")
        tests_failed += 1

    return tests_passed, tests_failed


def run_export_job_model_tests():
    """Test ExportJob model instantiation and properties."""
    print("\n" + "="*70)
    print("TESTING: ExportJob Model")
    print("="*70)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Basic model instantiation
    try:
        org_id = uuid4()
        user_id = uuid4()
        job = ExportJob(
            organization_id=org_id,
            user_id=user_id,
            format="csv",
            mode="all",
            product_count=2500,
        )
        assert job.organization_id == org_id
        assert job.user_id == user_id
        assert job.format == "csv"
        assert job.mode == "all"
        assert job.product_count == 2500
        print("[PASS] Basic model instantiation")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Basic model instantiation: {e}")
        tests_failed += 1

    # Test 2: Default field values (ORM defaults apply on DB insert, not instantiation)
    try:
        job = ExportJob(
            organization_id=uuid4(),
            format="csv",
            mode="all",
        )
        # ORM models don't apply defaults until DB insert
        # Just verify fields can be set to None without error
        assert job.file_path is None
        assert job.file_size_bytes is None
        assert job.error_message is None
        assert job.completed_at is None
        print("[PASS] Default field values (ORM behavior)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Default field values: {e}")
        tests_failed += 1

    # Test 3: is_completed property
    try:
        job = ExportJob(
            organization_id=uuid4(),
            format="csv",
            mode="all",
            status="completed",
        )
        assert job.is_completed is True

        job.status = "pending"
        assert job.is_completed is False
        print("[PASS] is_completed property works")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] is_completed property: {e}")
        tests_failed += 1

    # Test 4: is_failed property
    try:
        job = ExportJob(
            organization_id=uuid4(),
            format="csv",
            mode="all",
            status="failed",
        )
        assert job.is_failed is True

        job.status = "processing"
        assert job.is_failed is False
        print("[PASS] is_failed property works")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] is_failed property: {e}")
        tests_failed += 1

    # Test 5: is_expired property (not expired)
    try:
        future_time = datetime.now(timezone.utc) + timedelta(hours=12)
        job = ExportJob(
            organization_id=uuid4(),
            format="csv",
            mode="all",
            expires_at=future_time,
        )
        assert job.is_expired is False
        print("[PASS] is_expired property (not expired)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] is_expired not expired: {e}")
        tests_failed += 1

    # Test 6: is_expired property (expired)
    try:
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        job = ExportJob(
            organization_id=uuid4(),
            format="csv",
            mode="all",
            expires_at=past_time,
        )
        assert job.is_expired is True
        print("[PASS] is_expired property (expired)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] is_expired expired: {e}")
        tests_failed += 1

    # Test 7: file_extension property
    try:
        job_csv = ExportJob(organization_id=uuid4(), format="csv", mode="all")
        assert job_csv.file_extension == "csv"

        job_excel = ExportJob(organization_id=uuid4(), format="excel", mode="all")
        assert job_excel.file_extension == "xlsx"

        job_json = ExportJob(organization_id=uuid4(), format="json", mode="all")
        assert job_json.file_extension == "json"

        print("[PASS] file_extension property correct")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] file_extension property: {e}")
        tests_failed += 1

    # Test 8: request_params field (JSONB)
    try:
        params = {
            "format": "csv",
            "mode": "filtered",
            "filters": {
                "review_status": ["approved"],
                "min_confidence": 0.8,
            }
        }
        job = ExportJob(
            organization_id=uuid4(),
            format="csv",
            mode="filtered",
            request_params=params,
        )
        assert job.request_params == params
        assert job.request_params["filters"]["min_confidence"] == 0.8
        print("[PASS] request_params JSONB field works")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] request_params JSONB: {e}")
        tests_failed += 1

    return tests_passed, tests_failed


def run_export_service_tests():
    """Test export service pure functions."""
    print("\n" + "="*70)
    print("TESTING: Export Service Pure Functions")
    print("="*70)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Format file size - bytes
    try:
        assert _format_file_size(512) == "512 B"
        assert _format_file_size(1000) == "1000 B"
        print("[PASS] Format file size (bytes)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Format file size bytes: {e}")
        tests_failed += 1

    # Test 2: Format file size - KB
    try:
        assert _format_file_size(1024) == "1.0 KB"
        assert _format_file_size(1536) == "1.5 KB"
        assert _format_file_size(10240) == "10.0 KB"
        print("[PASS] Format file size (KB)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Format file size KB: {e}")
        tests_failed += 1

    # Test 3: Format file size - MB
    try:
        assert _format_file_size(1024 * 1024) == "1.0 MB"
        assert _format_file_size(5 * 1024 * 1024) == "5.0 MB"
        assert _format_file_size(int(1.5 * 1024 * 1024)) == "1.5 MB"
        print("[PASS] Format file size (MB)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Format file size MB: {e}")
        tests_failed += 1

    # Test 4: Format file size - GB
    try:
        assert _format_file_size(1024 * 1024 * 1024) == "1.0 GB"
        assert _format_file_size(int(2.5 * 1024 * 1024 * 1024)) == "2.5 GB"
        print("[PASS] Format file size (GB)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Format file size GB: {e}")
        tests_failed += 1

    # Test 5: Estimate export size (CSV with no images)
    try:
        size_str = estimate_export_size(1000, "csv", "none")
        # 1000 products * 500 bytes = 500,000 bytes = ~488 KB
        assert "KB" in size_str or "MB" in size_str
        print("[PASS] Estimate export size (CSV no images)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Estimate CSV no images: {e}")
        tests_failed += 1

    # Test 6: Estimate export size (CSV with URLs)
    try:
        size_str = estimate_export_size(1000, "csv", "url")
        # 1000 * 600 bytes = 600,000 bytes = ~586 KB
        assert "KB" in size_str or "MB" in size_str
        print("[PASS] Estimate export size (CSV with URLs)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Estimate CSV with URLs: {e}")
        tests_failed += 1

    # Test 7: Estimate export size (CSV with base64)
    try:
        size_str = estimate_export_size(100, "csv", "base64")
        # 100 * 50,000 bytes = 5,000,000 bytes = ~4.8 MB
        assert "MB" in size_str
        print("[PASS] Estimate export size (CSV with base64)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Estimate CSV with base64: {e}")
        tests_failed += 1

    # Test 8: Estimate export size (Excel with no images)
    try:
        size_str = estimate_export_size(2000, "excel", "none")
        # 2000 * 700 bytes = 1,400,000 bytes = ~1.3 MB
        assert "MB" in size_str or "KB" in size_str
        print("[PASS] Estimate export size (Excel no images)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Estimate Excel no images: {e}")
        tests_failed += 1

    # Test 9: Estimate export size (JSON with URLs)
    try:
        size_str = estimate_export_size(500, "json", "url")
        # 500 * 1200 bytes = 600,000 bytes = ~586 KB
        assert "KB" in size_str or "MB" in size_str
        print("[PASS] Estimate export size (JSON with URLs)")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Estimate JSON with URLs: {e}")
        tests_failed += 1

    # Test 10: Verify SIZE_ESTIMATES_PER_PRODUCT constants
    try:
        assert SIZE_ESTIMATES_PER_PRODUCT[("csv", "none")] == 500
        assert SIZE_ESTIMATES_PER_PRODUCT[("csv", "url")] == 600
        assert SIZE_ESTIMATES_PER_PRODUCT[("csv", "base64")] == 50_000
        assert SIZE_ESTIMATES_PER_PRODUCT[("excel", "none")] == 700
        assert SIZE_ESTIMATES_PER_PRODUCT[("json", "base64")] == 50_000
        print("[PASS] SIZE_ESTIMATES_PER_PRODUCT constants correct")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] SIZE_ESTIMATES constants: {e}")
        tests_failed += 1

    # Test 11: Estimate with zero products
    try:
        size_str = estimate_export_size(0, "csv", "none")
        assert size_str == "0 B"
        print("[PASS] Estimate with zero products")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Estimate zero products: {e}")
        tests_failed += 1

    # Test 12: Estimate with large product count
    try:
        size_str = estimate_export_size(100000, "csv", "none")
        # 100,000 * 500 = 50,000,000 bytes = ~47.7 MB
        assert "MB" in size_str
        print("[PASS] Estimate with large product count")
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Estimate large count: {e}")
        tests_failed += 1

    return tests_passed, tests_failed


def main():
    """Run all tests and report results."""
    print("\n" + "="*70)
    print("PRODUCT EXPORT FEATURE TEST SUITE")
    print("="*70)

    filters_passed, filters_failed = run_product_export_filters_tests()
    request_passed, request_failed = run_product_export_request_tests()
    storage_passed, storage_failed = run_export_storage_tests()
    model_passed, model_failed = run_export_job_model_tests()
    service_passed, service_failed = run_export_service_tests()

    total_passed = (
        filters_passed + request_passed + storage_passed +
        model_passed + service_passed
    )
    total_failed = (
        filters_failed + request_failed + storage_failed +
        model_failed + service_failed
    )
    total_tests = total_passed + total_failed

    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"ProductExportFilters:   {filters_passed}/{filters_passed + filters_failed} passed")
    print(f"ProductExportRequest:   {request_passed}/{request_passed + request_failed} passed")
    print(f"Export Storage:         {storage_passed}/{storage_passed + storage_failed} passed")
    print(f"ExportJob Model:        {model_passed}/{model_passed + model_failed} passed")
    print(f"Export Service:         {service_passed}/{service_passed + service_failed} passed")
    print(f"\nTOTAL:                  {total_passed}/{total_tests} passed")

    if total_failed == 0:
        print("\nRESULT: ALL TESTS PASSED")
        return 0
    else:
        print(f"\nRESULT: {total_failed} TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
