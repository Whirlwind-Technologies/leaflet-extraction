"""
Cost Tracking System Tests

These tests verify the VLM cost tracking system works correctly after fixing bugs that caused
inconsistent cost values across provider, leaflet, and organization levels.

Key bugs that were fixed:
1. Float precision drift causing costs to accumulate incorrectly
2. Double-write in extract_page() calling record_usage() twice
3. Hardcoded Anthropic pricing in tasks.py ignoring actual provider rates
4. Subtraction-based system cost calculation in usage stats endpoint
5. Missing Decimal type conversion in record_usage() methods

All tests are designed to catch regression if these bugs return.
"""

import inspect
from decimal import Decimal
from pathlib import Path

import pytest


class TestProviderRecordUsageDecimal:
    """Test VLMProvider.record_usage() uses Decimal arithmetic correctly."""

    def test_record_usage_decimal_precision(self):
        """
        Verify record_usage accumulates costs with Decimal precision, no float drift.

        Bug prevented: Float accumulation causes drift over many small additions.
        With 1000 calls at $0.0735, float would not equal exactly 73.5000.
        """
        from app.models.vlm_provider import VLMProvider

        provider = VLMProvider(
            provider_type="anthropic",
            model_name="claude-sonnet-4-20250514",
            api_key_encrypted=b"test",
            is_active=True,
            total_spent=Decimal("0"),
            current_month_spent=Decimal("0"),
            total_requests=0,
            total_input_tokens=0,
            total_output_tokens=0,
        )

        # Simulate 1000 small API calls at $0.0735 each
        # With Float, this would drift; with Decimal it should be exact
        for _ in range(1000):
            provider.record_usage(input_tokens=1000, output_tokens=500, cost=0.0735)

        expected = Decimal("73.5000")
        assert provider.total_spent == expected, (
            f"Expected {expected}, got {provider.total_spent}. "
            f"Float drift detected in cost accumulation."
        )
        assert provider.current_month_spent == expected
        assert provider.total_requests == 1000
        assert provider.total_input_tokens == 1000000
        assert provider.total_output_tokens == 500000

    def test_record_usage_accepts_float_and_decimal(self):
        """
        record_usage should work with both float and Decimal cost arguments.

        Bug prevented: Type errors when passing float vs Decimal to record_usage().
        """
        from app.models.vlm_provider import VLMProvider

        provider = VLMProvider(
            provider_type="anthropic",
            model_name="claude-sonnet-4-20250514",
            api_key_encrypted=b"test",
            is_active=True,
            total_spent=Decimal("0"),
            current_month_spent=Decimal("0"),
            total_requests=0,
            total_input_tokens=0,
            total_output_tokens=0,
        )

        # First call with float
        provider.record_usage(input_tokens=100, output_tokens=50, cost=0.05)
        # Second call with Decimal
        provider.record_usage(input_tokens=100, output_tokens=50, cost=Decimal("0.05"))

        assert provider.total_spent == Decimal("0.1000")
        assert provider.current_month_spent == Decimal("0.1000")
        assert provider.total_requests == 2

    def test_record_usage_handles_none_initial_values(self):
        """
        record_usage should handle None values in total_spent/current_month_spent.

        Bug prevented: TypeError when adding to None values on first usage.
        """
        from app.models.vlm_provider import VLMProvider

        provider = VLMProvider(
            provider_type="anthropic",
            model_name="claude-sonnet-4-20250514",
            api_key_encrypted=b"test",
            is_active=True,
            total_spent=None,
            current_month_spent=None,
            total_requests=0,
            total_input_tokens=0,
            total_output_tokens=0,
        )

        provider.record_usage(input_tokens=100, output_tokens=50, cost=0.05)

        assert provider.total_spent == Decimal("0.0500")
        assert provider.current_month_spent == Decimal("0.0500")
        assert provider.total_requests == 1

    def test_record_usage_preserves_precision_with_small_costs(self):
        """
        Verify very small costs (e.g., $0.0001) are tracked precisely.

        Bug prevented: Rounding errors losing sub-cent costs over many calls.
        """
        from app.models.vlm_provider import VLMProvider

        provider = VLMProvider(
            provider_type="anthropic",
            model_name="claude-sonnet-4-20250514",
            api_key_encrypted=b"test",
            is_active=True,
            total_spent=Decimal("0"),
            current_month_spent=Decimal("0"),
            total_requests=0,
            total_input_tokens=0,
            total_output_tokens=0,
        )

        # 10,000 calls at $0.0001 each should equal exactly $1.0000
        for _ in range(10000):
            provider.record_usage(input_tokens=10, output_tokens=5, cost=0.0001)

        expected = Decimal("1.0000")
        assert provider.total_spent == expected
        assert provider.current_month_spent == expected


class TestPlatformProviderRecordUsageDecimal:
    """Test PlatformVLMProvider.record_usage() uses Decimal arithmetic correctly."""

    def test_platform_provider_record_usage_decimal(self):
        """
        Verify PlatformVLMProvider accumulates costs with Decimal precision.

        Bug prevented: Same float drift issue as VLMProvider.
        """
        from app.models.platform_vlm_provider import PlatformVLMProvider

        provider = PlatformVLMProvider(
            provider_type="anthropic",
            model_name="claude-sonnet-4-20250514",
            api_key_encrypted=b"test",
            is_active=True,
            total_spent=Decimal("0"),
            current_month_spent=Decimal("0"),
            current_day_spent=Decimal("0"),
            total_requests=0,
            total_input_tokens=0,
            total_output_tokens=0,
        )

        for _ in range(100):
            provider.record_usage(input_tokens=5000, output_tokens=2000, cost=0.0735)

        expected = Decimal("7.3500")
        assert provider.total_spent == expected
        assert provider.current_month_spent == expected
        assert provider.current_day_spent == expected
        assert provider.total_requests == 100

    def test_platform_provider_handles_none_values(self):
        """
        PlatformVLMProvider should handle None in cost fields.

        Bug prevented: TypeError on first usage with None values.
        """
        from app.models.platform_vlm_provider import PlatformVLMProvider

        provider = PlatformVLMProvider(
            provider_type="anthropic",
            model_name="claude-sonnet-4-20250514",
            api_key_encrypted=b"test",
            is_active=True,
            total_spent=None,
            current_month_spent=None,
            current_day_spent=None,
            total_requests=0,
            total_input_tokens=0,
            total_output_tokens=0,
        )

        provider.record_usage(input_tokens=1000, output_tokens=500, cost=0.05)

        assert provider.total_spent == Decimal("0.0500")
        assert provider.current_month_spent == Decimal("0.0500")
        assert provider.current_day_spent == Decimal("0.0500")


class TestSourceCodeRegressionChecks:
    """Tests that check source code to detect if bug patterns return."""

    def test_no_double_write_in_extract_page(self):
        """
        Verify extract_page() does not call platform_service.record_usage() (double-write bug fix).

        Bug prevented: extract_page() calling platform_service.record_usage() AND the client's
        VLM call also recording usage, causing costs to be doubled.

        The correct flow is: VLM client records usage -> extract_page() reads from client.total_cost.
        """
        from app.core.extraction.vlm_extractor_service import VLMExtractorService

        source = inspect.getsource(VLMExtractorService.extract_page)

        # Should not contain any direct calls to platform_service.record_usage
        assert 'platform_service.record_usage' not in source, (
            "extract_page() should not call platform_service.record_usage() directly. "
            "This causes double-write bug where costs are recorded twice. "
            "Usage should only be recorded by the VLM client."
        )

    def test_leaflet_processing_cost_not_hardcoded(self):
        """
        Verify tasks.py doesn't use hardcoded Anthropic pricing for leaflet cost.

        Bug prevented: Using hardcoded "$3.00 per 1M input tokens, $15.00 per 1M output tokens"
        instead of actual provider pricing. This caused incorrect costs when using non-Anthropic
        providers or when Anthropic changed their pricing.
        """
        tasks_path = Path(__file__).resolve().parent.parent.parent / 'app' / 'workers' / 'tasks.py'
        with open(tasks_path, 'r') as f:
            source = f.read()

        # Check for the old hardcoded pricing pattern
        # Old code: input_cost = (total_input_tokens / 1_000_000) * 3.0
        # Old code: output_cost = (total_output_tokens / 1_000_000) * 15.0

        # Look for suspicious patterns near token calculations
        if '* 3.0' in source:
            # Get context around the match to see if it's related to input tokens
            idx = source.find('* 3.0')
            context = source[max(0, idx-200):min(len(source), idx+50)]
            assert 'input_token' not in context.lower() and 'input_cost' not in context.lower(), (
                "Found hardcoded $3.0/1M input token pricing in tasks.py. "
                "Use extractor.total_cost instead of calculating with hardcoded rates."
            )

        if '* 15.0' in source:
            idx = source.find('* 15.0')
            context = source[max(0, idx-200):min(len(source), idx+50)]
            assert 'output_token' not in context.lower() and 'output_cost' not in context.lower(), (
                "Found hardcoded $15.0/1M output token pricing in tasks.py. "
                "Use extractor.total_cost instead of calculating with hardcoded rates."
            )

    def test_usage_stats_no_subtraction(self):
        """
        Verify get_usage_stats() doesn't compute system cost as leaflet_total - provider_total.

        Bug prevented: Calculating system provider cost by subtracting user provider costs from
        total leaflet costs. This is wrong because:
        1. Not all leaflets may be processed yet (pending extractions)
        2. Leaflet costs may be stale or incomplete
        3. Creates circular dependency between leaflet and provider costs

        Correct approach: Sum system provider usage directly from audit logs or system provider records.
        """
        from app.api.v1 import vlm_providers

        source = inspect.getsource(vlm_providers.get_usage_stats)

        # The old buggy pattern was something like:
        # system_cost = float(leaflet_stats.total_cost or 0) - sum(provider_costs)

        # Check for suspicious subtraction near leaflet cost references
        if 'leaflet_stats.total_cost' in source:
            # Get the full function to analyze
            lines = source.split('\n')
            for i, line in enumerate(lines):
                if 'leaflet_stats.total_cost' in line or 'leaflet_total' in line:
                    # Check next few lines for subtraction
                    context_lines = '\n'.join(lines[i:min(i+5, len(lines))])
                    assert '- sum(' not in context_lines and '- provider' not in context_lines, (
                        "get_usage_stats() appears to calculate system cost by subtracting provider costs "
                        "from leaflet costs. This is incorrect. System cost should be summed directly from "
                        "system provider usage records or audit logs."
                    )


class TestDatabaseSchema:
    """Test that database schema uses correct types for cost fields."""

    def test_cost_columns_are_numeric(self):
        """
        Verify all cost columns use Numeric(10,4) not Float.

        Bug prevented: Using Float columns causes precision loss over time as costs accumulate.
        Numeric(10,4) ensures exact decimal arithmetic up to 4 decimal places.
        """
        from sqlalchemy import Float, Numeric
        from sqlalchemy import inspect as sa_inspect

        from app.models.leaflet import Leaflet
        from app.models.platform_vlm_provider import PlatformVLMProvider
        from app.models.vlm_provider import VLMProvider

        cost_fields = [
            (VLMProvider, ['monthly_budget', 'total_spent', 'current_month_spent']),
            (PlatformVLMProvider, ['monthly_budget', 'daily_budget', 'total_spent', 'current_month_spent', 'current_day_spent']),
            (Leaflet, ['processing_cost']),
        ]

        errors = []
        for model, fields in cost_fields:
            mapper = sa_inspect(model)
            for field_name in fields:
                col = mapper.columns[field_name]

                # Check it's Numeric type
                if not isinstance(col.type, Numeric):
                    errors.append(
                        f"{model.__name__}.{field_name} should be Numeric, got {type(col.type).__name__}. "
                        f"Float columns cause precision loss in cost tracking."
                    )

                # Explicitly check it's NOT Float
                if isinstance(col.type, Float):
                    errors.append(
                        f"{model.__name__}.{field_name} should NOT be Float. "
                        f"Use Numeric(10, 4) for exact decimal arithmetic."
                    )

        if errors:
            pytest.fail("\n".join(errors))

    def test_cost_columns_have_precision(self):
        """
        Verify Numeric cost columns have appropriate precision (10,4).

        Bug prevented: Using Numeric without specifying precision may lead to
        different behavior across databases.
        """
        from sqlalchemy import Numeric
        from sqlalchemy import inspect as sa_inspect

        from app.models.leaflet import Leaflet
        from app.models.platform_vlm_provider import PlatformVLMProvider
        from app.models.vlm_provider import VLMProvider

        cost_fields = [
            (VLMProvider, ['monthly_budget', 'total_spent', 'current_month_spent']),
            (PlatformVLMProvider, ['monthly_budget', 'daily_budget', 'total_spent', 'current_month_spent', 'current_day_spent']),
            (Leaflet, ['processing_cost']),
        ]

        for model, fields in cost_fields:
            mapper = sa_inspect(model)
            for field_name in fields:
                col = mapper.columns[field_name]

                if isinstance(col.type, Numeric):
                    # Check precision and scale are set
                    assert col.type.precision is not None, (
                        f"{model.__name__}.{field_name} Numeric type should specify precision"
                    )
                    assert col.type.scale is not None, (
                        f"{model.__name__}.{field_name} Numeric type should specify scale"
                    )

                    # Typically we want 10 digits total, 4 after decimal
                    # This allows values up to 999,999.9999
                    assert col.type.precision >= 10, (
                        f"{model.__name__}.{field_name} precision should be >= 10 to handle large costs"
                    )
                    assert col.type.scale == 4, (
                        f"{model.__name__}.{field_name} scale should be 4 for sub-cent precision"
                    )


class TestCostCalculationEdgeCases:
    """Test edge cases in cost calculation and accumulation."""

    def test_zero_cost_doesnt_break_tracking(self):
        """
        Verify that recording zero-cost operations doesn't cause errors.

        Bug prevented: Division by zero or None propagation with zero costs.
        """
        from app.models.vlm_provider import VLMProvider

        provider = VLMProvider(
            provider_type="anthropic",
            model_name="claude-sonnet-4-20250514",
            api_key_encrypted=b"test",
            is_active=True,
            total_spent=Decimal("0"),
            current_month_spent=Decimal("0"),
            total_requests=0,
            total_input_tokens=0,
            total_output_tokens=0,
        )

        # Record usage with zero cost (e.g., free tier, cached response)
        provider.record_usage(input_tokens=1000, output_tokens=500, cost=0.0)

        assert provider.total_spent == Decimal("0.0000")
        assert provider.current_month_spent == Decimal("0.0000")
        assert provider.total_requests == 1
        assert provider.total_input_tokens == 1000

    def test_very_large_cost_doesnt_overflow(self):
        """
        Verify that very large costs don't cause overflow with Numeric(10,4).

        Bug prevented: Overflow errors or loss of precision with large accumulated costs.
        """
        from app.models.vlm_provider import VLMProvider

        provider = VLMProvider(
            provider_type="anthropic",
            model_name="claude-sonnet-4-20250514",
            api_key_encrypted=b"test",
            is_active=True,
            total_spent=Decimal("0"),
            current_month_spent=Decimal("0"),
            total_requests=0,
            total_input_tokens=0,
            total_output_tokens=0,
        )

        # Record a very large cost (but within Numeric(10,4) range)
        # Max value for Numeric(10,4) is 999,999.9999
        large_cost = Decimal("50000.5000")
        provider.record_usage(input_tokens=100000, output_tokens=50000, cost=large_cost)

        assert provider.total_spent == large_cost
        assert provider.current_month_spent == large_cost

    def test_negative_cost_handling(self):
        """
        Verify that negative costs (credits/refunds) are handled correctly.

        Bug prevented: Absolute value conversion or error on negative costs.
        """
        from app.models.vlm_provider import VLMProvider

        provider = VLMProvider(
            provider_type="anthropic",
            model_name="claude-sonnet-4-20250514",
            api_key_encrypted=b"test",
            is_active=True,
            total_spent=Decimal("100.0000"),
            current_month_spent=Decimal("100.0000"),
            total_requests=10,
            total_input_tokens=10000,
            total_output_tokens=5000,
        )

        # Record a refund/credit (negative cost)
        provider.record_usage(input_tokens=0, output_tokens=0, cost=-10.0)

        assert provider.total_spent == Decimal("90.0000")
        assert provider.current_month_spent == Decimal("90.0000")
        assert provider.total_requests == 11


class TestCostIntegrity:
    """Test that costs maintain integrity across the system."""

    def test_cost_types_consistent_across_models(self):
        """
        Verify that all cost-related fields use consistent types across models.

        Bug prevented: Type mismatches when aggregating costs from different models.
        """
        from sqlalchemy import Numeric
        from sqlalchemy import inspect as sa_inspect

        from app.models.leaflet import Leaflet
        from app.models.platform_vlm_provider import PlatformVLMProvider
        from app.models.vlm_provider import VLMProvider

        # Get all cost columns
        all_cost_columns = []

        for model in [VLMProvider, PlatformVLMProvider, Leaflet]:
            mapper = sa_inspect(model)
            for col_name, col in mapper.columns.items():
                if 'cost' in col_name.lower() or 'spent' in col_name.lower() or 'budget' in col_name.lower():
                    all_cost_columns.append((model.__name__, col_name, col.type))

        # All should be Numeric
        non_numeric = [(m, c, t) for m, c, t in all_cost_columns if not isinstance(t, Numeric)]

        assert len(non_numeric) == 0, (
            f"Found non-Numeric cost columns: {non_numeric}. "
            f"All cost/spent/budget fields should use Numeric(10,4) for consistency."
        )
