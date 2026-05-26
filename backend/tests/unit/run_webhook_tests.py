"""
Standalone runner for webhook unit tests.

Bypasses pytest conftest issues by running tests directly with Python.
"""

import sys
sys.path.insert(0, '.')

# Run the tests by importing the test module
if __name__ == "__main__":
    print("=" * 80)
    print("WEBHOOK UNIT TESTS")
    print("=" * 80)
    print()

    # Import test classes
    from tests.unit.test_webhooks import (
        TestSSRFPrevention,
        TestWebhookModel,
        TestWebhookDeliveryModel,
        TestWebhookSchemas,
        TestHeaderRedaction,
        TestWebhookDispatch,
        TestResponseBodyTruncation,
        TestWebhookEvents,
        TestWebhookSecretEncryption,
        TestSSRFDispatchCheck,
        TestWebhookSoftDelete,
        TestResponseBodyConstraint,
        TestWebhookService,
    )

    test_classes = [
        TestSSRFPrevention,
        TestWebhookModel,
        TestWebhookDeliveryModel,
        TestWebhookSchemas,
        TestHeaderRedaction,
        TestWebhookDispatch,
        TestResponseBodyTruncation,
        TestWebhookEvents,
        # Critical security fix tests
        TestWebhookSecretEncryption,
        TestSSRFDispatchCheck,
        TestWebhookSoftDelete,
        TestResponseBodyConstraint,
        TestWebhookService,
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    for test_class in test_classes:
        print(f"\n{test_class.__name__}")
        print("-" * 80)

        test_instance = test_class()

        # Get all test methods
        test_methods = [
            method for method in dir(test_instance)
            if method.startswith('test_') and callable(getattr(test_instance, method))
        ]

        for method_name in test_methods:
            total_tests += 1
            test_method = getattr(test_instance, method_name)

            try:
                # Check if async test
                import inspect
                import asyncio
                if inspect.iscoroutinefunction(test_method):
                    asyncio.run(test_method())
                else:
                    test_method()

                print(f"  PASS {method_name}")
                passed_tests += 1
            except Exception as e:
                print(f"  FAIL {method_name}")
                print(f"    Error: {e}")
                failed_tests.append((test_class.__name__, method_name, str(e)))

    print()
    print("=" * 80)
    print(f"RESULTS: {passed_tests}/{total_tests} tests passed")
    if failed_tests:
        print()
        print("FAILED TESTS:")
        for class_name, method_name, error in failed_tests:
            print(f"  - {class_name}.{method_name}")
            print(f"    {error}")
    print("=" * 80)

    sys.exit(0 if len(failed_tests) == 0 else 1)
