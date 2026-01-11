"""
Quick verification script to test the fixes
Run this to verify the numeric extraction and revenue calculation work correctly
"""

from analytics_helper import ManufacturingAnalytics

print("=" * 60)
print("TESTING FIXES")
print("=" * 60)

analytics = ManufacturingAnalytics()

# Test 1: Numeric extraction with commas
print("\n1. Testing numeric extraction with commas:")
test_cases = [
    ("Quantity: 500", 500.0),
    ("Price: $2,500.00", 2500.0),
    ("Total: $13,250.00", 13250.0),
    ("Growth of 15.5%", 15.5),
]

for text, expected in test_cases:
    result = analytics.extract_numeric_value(text)
    status = "✅" if result == expected else "❌"
    print(f"  {status} '{text}' -> {result} (expected {expected})")

# Test 2: Revenue calculation from sample data
print("\n2. Testing revenue calculation from search results:")

SAMPLE_DATA = """
Source: History | ACME Corporation (10001) | Order: 5501
Content: Record Type: Historical Order. Customer Name: ACME Corporation. Order #: 5501-1. Shipped Date: 2025-11-15. Part Number: BELT-100. Quantity Shipped: 500 FT. Price: $2,500.00.

---

Source: History | ACME Corporation (10001) | Order: 5502
Content: Record Type: Historical Order. Customer Name: ACME Corporation. Order #: 5502-1. Shipped Date: 2025-12-10. Part Number: BELT-100. Quantity Shipped: 550 FT. Price: $2,750.00.

---

Source: History | Baldwin Manufacturing (10002) | Order: 5503
Content: Record Type: Historical Order. Customer Name: Baldwin Manufacturing. Order #: 5503-1. Shipped Date: 2025-12-15. Part Number: VALVE-50. Quantity Shipped: 100 EA. Price: $5,000.00.

---

Source: OpenOrder | ACME Corporation (10001) | Order: 5504
Content: Record Type: Open Order. Customer Name: ACME Corporation. Order #: 5504-1. Promised Date: 2026-01-20. Part Number: BELT-100. Quantity Ordered: 600 FT. Price: $3,000.00.
"""

analysis = analytics.analyze_search_results(SAMPLE_DATA)

expected_revenue = 13250.0  # 2500 + 2750 + 5000 + 3000
actual_revenue = analysis.get('total_revenue', 0)

print(f"  Expected revenue: ${expected_revenue:,.2f}")
print(f"  Actual revenue:   ${actual_revenue:,.2f}")

if actual_revenue == expected_revenue:
    print(f"  ✅ Revenue calculation CORRECT!")
else:
    print(f"  ❌ Revenue calculation INCORRECT (diff: ${abs(actual_revenue - expected_revenue):,.2f})")

# Test 3: Quantity extraction
expected_qty = 1750.0  # 500 + 550 + 100 + 600
actual_qty = analysis.get('total_quantity', 0)

print(f"\n  Expected quantity: {expected_qty:,.0f}")
print(f"  Actual quantity:   {actual_qty:,.0f}")

if actual_qty == expected_qty:
    print(f"  ✅ Quantity calculation CORRECT!")
else:
    print(f"  ❌ Quantity calculation INCORRECT (diff: {abs(actual_qty - expected_qty):,.0f})")

# Test 4: Customer count
expected_customers = 2
actual_customers = analysis.get('unique_customers', 0)

print(f"\n  Expected customers: {expected_customers}")
print(f"  Actual customers:   {actual_customers}")

if actual_customers == expected_customers:
    print(f"  ✅ Customer count CORRECT!")
else:
    print(f"  ❌ Customer count INCORRECT")

print("\n" + "=" * 60)
if (actual_revenue == expected_revenue and 
    actual_qty == expected_qty and 
    actual_customers == expected_customers):
    print("🎉 ALL FIXES VERIFIED - Ready to use!")
else:
    print("⚠️  Some issues remain - check output above")
print("=" * 60)