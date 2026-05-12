# Quickstart: Custom Properties in Queries

## 1. Break Down by Custom Property

```python
from mixpanel_data import Workspace, GroupBy, CustomPropertyRef, InlineCustomProperty, PropertyInput

ws = Workspace()

# Saved custom property (by ID)
result = ws.query(
    "Purchase",
    group_by=GroupBy(property=CustomPropertyRef(42), property_type="number"),
)

# Inline formula: revenue = price * quantity
result = ws.query(
    "Purchase",
    group_by=GroupBy(
        property=InlineCustomProperty.numeric("A * B", A="price", B="quantity"),
        property_type="number",
        bucket_size=100,
    ),
)

# String formula with conditional bucketing
result = ws.query(
    "Purchase",
    group_by=GroupBy(
        property=InlineCustomProperty(
            formula='IFS(A > 1000, "Enterprise", A > 100, "Pro", TRUE, "Free")',
            inputs={"A": PropertyInput("amount", type="number")},
            property_type="string",
        ),
    ),
)
```

## 2. Filter by Custom Property

```python
from mixpanel_data import Filter, CustomPropertyRef, InlineCustomProperty

# Saved custom property
result = ws.query(
    "Purchase",
    where=Filter.greater_than(property=CustomPropertyRef(42), value=100),
)

# Inline formula: filter where revenue > 1000
result = ws.query(
    "Purchase",
    where=Filter.greater_than(
        property=InlineCustomProperty.numeric("A * B", A="price", B="quantity"),
        value=1000,
    ),
)

# Extract email domain and filter
result = ws.query(
    "Signup",
    where=Filter.equals(
        property=InlineCustomProperty(
            formula='REGEX_EXTRACT(A, "@(.+)$")',
            inputs={"A": PropertyInput("email", type="string")},
            property_type="string",
        ),
        value="company.com",
    ),
)
```

## 3. Aggregate on Custom Property

```python
from mixpanel_data import Metric, CustomPropertyRef, InlineCustomProperty

# Average of a saved custom property
result = ws.query(
    Metric("Purchase", math="average", property=CustomPropertyRef(42)),
)

# Average revenue (price * quantity) per purchase
result = ws.query(
    Metric(
        "Purchase",
        math="average",
        property=InlineCustomProperty.numeric("A * B", A="price", B="quantity"),
    ),
)

# Median profit margin
result = ws.query(
    Metric(
        "Purchase",
        math="median",
        property=InlineCustomProperty.numeric(
            "(A - B) / A * 100", A="revenue", B="cost",
        ),
    ),
)
```

## 4. Combine All Three Positions

```python
# Revenue breakdown by tier, filtered to high-value, with average revenue metric
revenue = InlineCustomProperty.numeric("A * B", A="price", B="quantity")

result = ws.query(
    Metric("Purchase", math="average", property=CustomPropertyRef(99)),
    group_by=GroupBy(property=revenue, property_type="number", bucket_size=100),
    where=Filter.greater_than(property=revenue, value=50),
)
```

## 5. Works Across Query Engines

```python
# Funnels: break down conversion by custom property
result = ws.query_funnel(
    ["Signup", "Purchase"],
    group_by=GroupBy(property=CustomPropertyRef(42), property_type="number"),
)

# Retention: filter by custom property
result = ws.query_retention(
    "Signup", "Purchase",
    where=Filter.greater_than(property=CustomPropertyRef(42), value=100),
)

# Mix with plain strings — everything is backward-compatible
result = ws.query(
    "Purchase",
    group_by=[
        "country",
        GroupBy(property=CustomPropertyRef(42), property_type="number"),
        GroupBy(
            property=InlineCustomProperty.numeric("A", A="revenue"),
            property_type="number",
        ),
    ],
)
```
