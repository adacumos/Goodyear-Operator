"""
Test Suite for Analytics and Forecasting Features
Run this to validate your analytical capabilities
"""

import asyncio
import logging
from typing import List, Dict
from analytics_helper import ManufacturingAnalytics, create_analytics_context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Sample search results for testing
SAMPLE_SEARCH_OUTPUT = """
Source: History | ACME Corporation (10001) | Order: 5501
Content: Record Type: Historical Order. Customer Name: ACME Corporation. Customer Code: 10001. Order #: 5501-1. Shipped Date: 2025-11-15. Part Number: BELT-100. Quantity Shipped: 500 FT. Price: $2,500.00.

---

Source: History | ACME Corporation (10001) | Order: 5502
Content: Record Type: Historical Order. Customer Name: ACME Corporation. Customer Code: 10001. Order #: 5502-1. Shipped Date: 2025-12-10. Part Number: BELT-100. Quantity Shipped: 550 FT. Price: $2,750.00.

---

Source: History | Baldwin Manufacturing (10002) | Order: 5503
Content: Record Type: Historical Order. Customer Name: Baldwin Manufacturing. Customer Code: 10002. Order #: 5503-1. Shipped Date: 2025-12-15. Part Number: VALVE-50. Quantity Shipped: 100 EA. Price: $5,000.00.

---

Source: OpenOrder | ACME Corporation (10001) | Order: 5504
Content: Record Type: Open Order. Customer Name: ACME Corporation. Customer Code: 10001. Order #: 5504-1. Status: Backordered. Promised Date: 2026-01-20. Part Number: BELT-100. Quantity Ordered: 600 FT. Price: $3,000.00.
"""


def test_extract_numeric_value():
    """Test 1: Numeric extraction"""
    logger.info("=" * 60)
    logger.info("TEST 1: Numeric Value Extraction")
    logger.info("=" * 60)
    
    analytics = ManufacturingAnalytics()
    
    test_cases = [
        ("Quantity: 500", 500.0),
        ("Price: $2,500.00", 2500.0),
        ("Growth of 15.5%", 15.5),
        ("No numbers here", None)
    ]
    
    all_passed = True
    for text, expected in test_cases:
        result = analytics.extract_numeric_value(text)
        if result == expected:
            logger.info(f"✅ '{text}' -> {result}")
        else:
            logger.error(f"❌ '{text}' -> {result} (expected {expected})")
            all_passed = False
    
    return all_passed


def test_calculate_moving_average():
    """Test 2: Moving average calculation"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Moving Average Calculation")
    logger.info("=" * 60)
    
    analytics = ManufacturingAnalytics()
    
    # Test case: [100, 110, 120, 130, 140]
    values = [100, 110, 120, 130, 140]
    ma_3 = analytics.calculate_moving_average(values, window=3)
    
    # Expected: (120 + 130 + 140) / 3 = 130
    expected = 130.0
    
    if ma_3 == expected:
        logger.info(f"✅ 3-period MA of {values[-3:]} = {ma_3}")
        return True
    else:
        logger.error(f"❌ Expected {expected}, got {ma_3}")
        return False


def test_calculate_growth_rate():
    """Test 3: Growth rate calculation"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Growth Rate Calculation")
    logger.info("=" * 60)
    
    analytics = ManufacturingAnalytics()
    
    test_cases = [
        (100, 110, 10.0),  # 10% growth
        (100, 90, -10.0),  # 10% decline
        (1000, 1150, 15.0),  # 15% growth
    ]
    
    all_passed = True
    for old_val, new_val, expected in test_cases:
        result = analytics.calculate_growth_rate(old_val, new_val)
        if result == expected:
            logger.info(f"✅ {old_val} -> {new_val} = {result:+.1f}%")
        else:
            logger.error(f"❌ Expected {expected}%, got {result}%")
            all_passed = False
    
    return all_passed


def test_simple_linear_forecast():
    """Test 4: Linear forecasting"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Linear Trend Forecasting")
    logger.info("=" * 60)
    
    analytics = ManufacturingAnalytics()
    
    # Test case: Growing trend [100, 110, 120, 130]
    values = [100, 110, 120, 130]
    forecast = analytics.simple_linear_forecast(values, periods_ahead=1)
    
    if forecast:
        logger.info(f"✅ Forecast generated successfully")
        logger.info(f"   Historical values: {values}")
        logger.info(f"   Forecasted value: {forecast['forecast_value']}")
        logger.info(f"   Average growth: {forecast['avg_growth_rate']:.2f}%")
        logger.info(f"   Confidence: {forecast['confidence']}")
        
        # Validate forecast is reasonable (should be around 140-145)
        if 135 <= forecast['forecast_value'] <= 145:
            logger.info(f"✅ Forecast value in expected range")
            return True
        else:
            logger.error(f"❌ Forecast value {forecast['forecast_value']} outside expected range (135-145)")
            return False
    else:
        logger.error(f"❌ Forecast generation failed")
        return False


def test_analyze_search_results():
    """Test 5: Search results analysis"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Search Results Analysis")
    logger.info("=" * 60)
    
    analytics = ManufacturingAnalytics()
    analysis = analytics.analyze_search_results(SAMPLE_SEARCH_OUTPUT)
    
    logger.info(f"Analysis results:")
    logger.info(f"  - Total orders found: {analysis.get('order_count', 0)}")
    logger.info(f"  - Unique customers: {analysis.get('unique_customers', 0)}")
    logger.info(f"  - Record types: {dict(analysis.get('record_types', {}))}")
    
    # Validate expected results
    checks = {
        'order_count': (4, "Should find 4 orders"),
        'unique_customers': (2, "Should find 2 unique customers (ACME and Baldwin)"),
    }
    
    all_passed = True
    for key, (expected, description) in checks.items():
        actual = analysis.get(key, 0)
        if actual == expected:
            logger.info(f"✅ {description}: {actual}")
        else:
            logger.error(f"❌ {description}: Expected {expected}, got {actual}")
            all_passed = False
    
    # Check if revenue calculation works
    if 'total_revenue' in analysis:
        total_rev = analysis['total_revenue']
        # Expected: 2500 + 2750 + 5000 + 3000 = 13250
        expected_rev = 13250.0
        if abs(total_rev - expected_rev) < 0.01:
            logger.info(f"✅ Total revenue: ${total_rev:,.2f}")
        else:
            logger.error(f"❌ Revenue calculation: Expected ${expected_rev:,.2f}, got ${total_rev:,.2f}")
            all_passed = False
    
    return all_passed


def test_generate_forecast_insight():
    """Test 6: Forecast insight generation"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: Forecast Insight Generation")
    logger.info("=" * 60)
    
    analytics = ManufacturingAnalytics()
    analysis = analytics.analyze_search_results(SAMPLE_SEARCH_OUTPUT)
    insight = analytics.generate_forecast_insight(analysis)
    
    logger.info(f"Generated insight:")
    logger.info(f"  {insight}")
    
    # Check if key information is present
    required_elements = [
        'orders',
        'customers',
        'revenue'
    ]
    
    all_present = True
    for element in required_elements:
        if element.lower() in insight.lower():
            logger.info(f"✅ Insight includes '{element}'")
        else:
            logger.error(f"❌ Insight missing '{element}'")
            all_present = False
    
    return all_present


def test_create_analytics_context():
    """Test 7: Analytics context creation"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 7: Analytics Context Creation")
    logger.info("=" * 60)
    
    context = create_analytics_context(SAMPLE_SEARCH_OUTPUT)
    
    if context and len(context) > 100:
        logger.info(f"✅ Analytics context generated ({len(context)} chars)")
        logger.info(f"\nSample context:")
        logger.info(context[:300] + "...")
        
        # Check for key sections
        required_sections = [
            'ANALYTICAL SUMMARY',
            'KEY METRICS',
        ]
        
        all_present = True
        for section in required_sections:
            if section in context:
                logger.info(f"✅ Context includes '{section}' section")
            else:
                logger.error(f"❌ Context missing '{section}' section")
                all_present = False
        
        return all_present
    else:
        logger.error(f"❌ Analytics context generation failed or too short")
        return False


def test_edge_cases():
    """Test 8: Edge cases and error handling"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 8: Edge Cases and Error Handling")
    logger.info("=" * 60)
    
    analytics = ManufacturingAnalytics()
    
    # Test empty input
    logger.info("Testing empty search output...")
    context = create_analytics_context("")
    if context == "":
        logger.info("✅ Empty input handled correctly")
    else:
        logger.error("❌ Empty input not handled correctly")
        return False
    
    # Test insufficient data for forecast
    logger.info("Testing insufficient data for forecast...")
    forecast = analytics.simple_linear_forecast([100], periods_ahead=1)
    if forecast is None:
        logger.info("✅ Insufficient data handled correctly")
    else:
        logger.error("❌ Should return None for single data point")
        return False
    
    # Test zero division in growth rate
    logger.info("Testing zero division in growth rate...")
    growth = analytics.calculate_growth_rate(0, 100)
    if growth is None:
        logger.info("✅ Zero division handled correctly")
    else:
        logger.error("❌ Should return None for zero base value")
        return False
    
    return True


async def run_all_tests():
    """Run all analytics tests"""
    logger.info("\n" + "=" * 80)
    logger.info("GOODYEAR RAG AGENT - ANALYTICS TEST SUITE")
    logger.info("=" * 80 + "\n")
    
    tests = [
        ("Numeric Extraction", test_extract_numeric_value),
        ("Moving Average", test_calculate_moving_average),
        ("Growth Rate", test_calculate_growth_rate),
        ("Linear Forecast", test_simple_linear_forecast),
        ("Search Analysis", test_analyze_search_results),
        ("Forecast Insights", test_generate_forecast_insight),
        ("Context Creation", test_create_analytics_context),
        ("Edge Cases", test_edge_cases)
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Generate summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    logger.info(f"\nTests Passed: {passed}/{total}")
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {status} - {test_name}")
    
    # Recommendations
    logger.info("\n" + "=" * 80)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 80)
    
    if passed == total:
        logger.info("🎉 All analytics tests passed! System is ready for forecasting queries.")
        logger.info("\nTry these analytical queries:")
        logger.info("  - 'What are my sales trends over the last quarter?'")
        logger.info("  - 'Forecast next month's order volume'")
        logger.info("  - 'Which customers should I prioritize?'")
        logger.info("  - 'Analyze my revenue by customer'")
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed. Review analytics_helper.py")
    
    logger.info("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    print("\nStarting Analytics Test Suite...\n")
    success = asyncio.run(run_all_tests())
    print("\nTest suite completed.\n")
    exit(0 if success else 1)