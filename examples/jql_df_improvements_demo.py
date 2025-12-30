"""Demonstration of improved JQLResult DataFrame conversion.

This shows how the enhanced DataFrame conversion handles common JQL result patterns.
"""

from mixpanel_data.types import JQLResult

# Example 1: groupBy with single key
print("=" * 60)
print("Example 1: groupBy by country (single key)")
print("=" * 60)

result1 = JQLResult(
    _raw=[
        {"key": ["US"], "value": 100},
        {"key": ["UK"], "value": 50},
        {"key": ["CA"], "value": 75},
    ]
)

df1 = result1.df
print("\nJQL Result:")
print(result1.raw)
print("\nDataFrame:")
print(df1)
print(f"\nColumns: {list(df1.columns)}")

# Example 2: groupBy with multiple keys
print("\n" + "=" * 60)
print("Example 2: groupBy by country and browser (multi-key)")
print("=" * 60)

result2 = JQLResult(
    _raw=[
        {"key": ["US", "Chrome"], "value": 100},
        {"key": ["US", "Firefox"], "value": 50},
        {"key": ["UK", "Chrome"], "value": 75},
    ]
)

df2 = result2.df
print("\nJQL Result:")
print(result2.raw)
print("\nDataFrame:")
print(df2)
print(f"\nColumns: {list(df2.columns)}")

# Example 3: groupBy with multiple reducers
print("\n" + "=" * 60)
print("Example 3: groupBy with multiple reducers (count, sum, avg)")
print("=" * 60)

result3 = JQLResult(
    _raw=[
        {"key": ["US"], "value": [100, 5000, 50.0]},
        {"key": ["UK"], "value": [50, 2500, 50.0]},
        {"key": ["CA"], "value": [75, 3750, 50.0]},
    ]
)

df3 = result3.df
print("\nJQL Result:")
print(result3.raw)
print("\nDataFrame:")
print(df3)
print(f"\nColumns: {list(df3.columns)}")

# Example 4: reduce with numeric_summary
print("\n" + "=" * 60)
print("Example 4: reduce with numeric_summary")
print("=" * 60)

result4 = JQLResult(
    _raw=[
        {
            "count": 221,
            "sum": 32624,
            "sum_squares": 9199564,
            "avg": 147.62,
            "stddev": 140.84,
        }
    ]
)

df4 = result4.df
print("\nJQL Result:")
print(result4.raw)
print("\nDataFrame:")
print(df4)
print(f"\nColumns: {list(df4.columns)}")

# Example 5: reduce with percentiles (nested structure)
print("\n" + "=" * 60)
print("Example 5: reduce with percentiles (nested)")
print("=" * 60)

result5 = JQLResult(
    _raw=[
        [
            {"percentile": 50, "value": 118},
            {"percentile": 90, "value": 356},
            {"percentile": 95, "value": 468},
            {"percentile": 99, "value": 732},
        ]
    ]
)

df5 = result5.df
print("\nJQL Result:")
print(result5.raw)
print("\nDataFrame:")
print(df5)
print(f"\nColumns: {list(df5.columns)}")

# Example 6: After .map() transformation
print("\n" + "=" * 60)
print("Example 6: After .map() transformation (already named)")
print("=" * 60)

result6 = JQLResult(
    _raw=[
        {"country": "US", "purchases": 100, "total_revenue": 5000, "avg_order": 50.0},
        {"country": "UK", "purchases": 50, "total_revenue": 2500, "avg_order": 50.0},
        {"country": "CA", "purchases": 75, "total_revenue": 3750, "avg_order": 50.0},
    ]
)

df6 = result6.df
print("\nJQL Result:")
print(result6.raw)
print("\nDataFrame:")
print(df6)
print(f"\nColumns: {list(df6.columns)}")

# Example 7: Demonstrate backward compatibility
print("\n" + "=" * 60)
print("Example 7: Backward compatibility - simple list")
print("=" * 60)

result7 = JQLResult(_raw=[1, 2, 3, 4, 5])

df7 = result7.df
print("\nJQL Result:")
print(result7.raw)
print("\nDataFrame:")
print(df7)
print(f"\nColumns: {list(df7.columns)}")

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print(
    """
The improved JQLResult.df now handles:
✓ groupBy with single key: key_0 column
✓ groupBy with multiple keys: key_0, key_1, key_2, ... columns
✓ Multiple reducers: value_0, value_1, value_2, ... columns
✓ reduce() results: preserved as-is
✓ Nested percentile arrays: flattened automatically
✓ After .map(): preserved column names
✓ Backward compatible: simple lists still work
"""
)
