# Mixpanel Query Expression Language Reference

## Table of Contents
1. [Overview](#overview)
2. [Filter Expression Syntax (WHERE)](#filter-expression-syntax-where)
3. [JQL (JavaScript Query Language)](#jql-javascript-query-language)
4. [Data Sources](#data-sources)
5. [Operators](#operators)
6. [Functions](#functions)
7. [Reducers](#reducers)
8. [Advanced Patterns](#advanced-patterns)
9. [Examples](#examples)

## Overview

Mixpanel provides two primary query expression systems:
1. **Filter Expressions** - Used in WHERE clauses and selectors for filtering data
2. **JQL (JavaScript Query Language)** - Full JavaScript-based query language for complex data analysis

## Filter Expression Syntax (WHERE)

Filter expressions are used in API endpoints and selectors to filter events and users. They support a SQL-like syntax with property access and logical operators.

### Property Access

```javascript
// Event properties
properties["property_name"]
properties["$browser"]
properties["custom_prop"]

// User properties (in user context)
user["$name"]
user["$email"]
user["plan_type"]

// Event metadata
event["$event_name"]
event["$time"]
event["$distinct_id"]

// Group properties (when using data groups)
group_properties["company"]["industry"]
group_properties["team"]["size"]
```

### Comparison Operators

```javascript
// Equality
properties["browser"] == "Chrome"
properties["browser"] != "Safari"

// Numeric comparisons
properties["age"] > 18
properties["age"] >= 21
properties["age"] < 65
properties["age"] <= 100

// Range checks
properties["price"] >= 10 and properties["price"] <= 100

// Null checks
properties["email"] == null
properties["email"] != null
```

### Logical Operators

```javascript
// AND operator
properties["plan"] == "premium" and properties["active"] == true

// OR operator
properties["source"] == "web" or properties["source"] == "mobile"

// NOT operator
not properties["beta_user"]
not (properties["age"] < 18)

// Complex combinations
(properties["plan"] == "premium" or properties["plan"] == "enterprise") and properties["active"] == true
```

### Set Operations

```javascript
// IN operator - check if value is in a set
properties["country"] in ["US", "CA", "UK", "AU"]
properties["plan"] in ["free", "trial"]

// NOT IN
not (properties["status"] in ["deleted", "suspended"])

// String contains (substring check)
properties["email"] contains "@company.com"
properties["tags"] contains "premium"
"mobile" in properties["platforms"]
```

### Existence Functions

```javascript
// Check if property is defined
defined(properties["email"])
defined(user["signup_date"])
defined(group_properties["company"]["name"])

// Check if property is not defined
not defined(properties["deleted_at"])
not defined(properties["temp_flag"])
```

### Date/Time Functions

```javascript
// Date comparison
properties["created"] > datetime(2024, 1, 1)
properties["created"] >= datetime(2024, 1, 1, 0, 0, 0)

// Event time filtering
event["$time"] >= datetime("2024-01-01T00:00:00")
event["$time"] < datetime("2024-02-01T00:00:00")

// Relative time (in some contexts)
properties["last_seen"] > datetime("2024-01-01")
```

### Type Coercion

```javascript
// Properties are automatically coerced when possible
properties["age"] > "18"  // String "18" coerced to number
properties["active"] == true  // Boolean comparison
properties["count"] == 5  // Numeric comparison
```

## JQL (JavaScript Query Language)

JQL is a full JavaScript-based query language that allows complex data transformations and analysis.

### Basic Structure

```javascript
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    })
    .filter(/* ... */)
    .map(/* ... */)
    .groupBy(/* ... */)
    .reduce(/* ... */);
}
```

### Parameters Support

```javascript
function main() {
    return Events({
        from_date: params.from_date,
        to_date: params.to_date
    })
    .filter(function(event) {
        return event.properties.amount >= params.min_amount;
    });
}
```

## Data Sources

### Events

```javascript
// Basic events query
Events({
    from_date: '2024-01-01',
    to_date: '2024-01-31'
})

// With event selectors
Events({
    from_date: '2024-01-01',
    to_date: '2024-01-31',
    event_selectors: [
        {event: 'Sign Up'},
        {event: 'Purchase'},
        {selector: 'properties["category"] == "electronics"'}
    ]
})

// Complex selector
Events({
    from_date: '2024-01-01',
    to_date: '2024-01-31',
    event_selectors: [{
        selector: 'properties["amount"] >= 100 and properties["amount"] < 1000'
    }]
})
```

### People (User Profiles)

```javascript
// All users
People({})

// With user selectors
People({
    user_selectors: [{
        selector: 'user["plan"] == "premium"'
    }]
})

// Multiple conditions
People({
    user_selectors: [{
        selector: 'user["created"] >= datetime(2024, 1, 1) and user["active"] == true'
    }]
})
```

### Joins

```javascript
// Inner join - only users with events
join(
    People({}),
    Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    }),
    {type: 'inner'}
)

// Left join - all users, with or without events
join(
    People({}),
    Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    }),
    {type: 'left'}
)

// Right join - all events, with or without user profiles
join(
    People({}),
    Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    }),
    {type: 'right'}
)

// Full outer join
join(
    People({}),
    Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    }),
    {type: 'full'}
)
```

## Operators

### Transformation Operators

#### filter()
```javascript
// Filter events by property value
.filter(function(event) {
    return event.properties.amount > 100;
})

// Complex filtering
.filter(function(event) {
    return event.properties.country == "US" &&
           event.properties.amount > 50 &&
           event.properties.category in ["electronics", "books"];
})
```

#### map()
```javascript
// Transform each event
.map(function(event) {
    return {
        user: event.distinct_id,
        amount: event.properties.amount,
        category: event.properties.category
    };
})

// Extract specific property
.map("properties.browser")
```

#### groupBy()
```javascript
// Group by single property
.groupBy(['properties.country'], mixpanel.reducer.count())

// Group by multiple properties
.groupBy([
    'properties.country',
    'properties.city'
], mixpanel.reducer.count())

// Group by computed value
.groupBy([
    function(event) {
        return Math.floor(event.properties.amount / 100) * 100;
    }
], mixpanel.reducer.count())
```

#### groupByUser()
```javascript
// Count events per user
.groupByUser(mixpanel.reducer.count())

// Custom aggregation per user
.groupByUser(function(state, events) {
    state = state || {
        event_count: 0,
        total_amount: 0,
        categories: new Set()
    };

    events.forEach(function(event) {
        state.event_count++;
        state.total_amount += event.properties.amount || 0;
        state.categories.add(event.properties.category);
    });

    return state;
})

// Multiple reducers
.groupByUser([
    mixpanel.reducer.count(),
    mixpanel.reducer.sum('properties.amount')
])
```

#### reduce()
```javascript
// Simple reduction
.reduce(mixpanel.reducer.count())

// Custom reducer
.reduce(function(accumulator, events) {
    accumulator = accumulator || 0;
    return accumulator + events.length;
})
```

#### flatten()
```javascript
// Flatten nested arrays
.reduce(mixpanel.reducer.top(10))
.flatten()
```

#### sortAsc() / sortDesc()
```javascript
// Sort ascending by value
.groupBy(['properties.country'], mixpanel.reducer.count())
.sortAsc('value')

// Sort descending
.sortDesc('value')
```

#### applyGroupLimits()
```javascript
// Limit results per group level
.groupBy(['properties.category', 'properties.brand'], mixpanel.reducer.count())
.applyGroupLimits([5, 10])  // Top 5 categories, top 10 brands per category

// With minimum threshold
.applyGroupLimits([10, 5], 100)  // Only include groups with at least 100 items
```

## Functions

### Type Conversion Functions

```javascript
// Convert to boolean
mixpanel.to_boolean("event")
mixpanel.to_boolean("user")
mixpanel.to_boolean(0)  // false
mixpanel.to_boolean(1)  // true

// Convert to string
mixpanel.to_string(123)
mixpanel.to_string(true)

// Convert to number
mixpanel.to_number("123")
mixpanel.to_number(true)  // 1
```

### Bucketing Functions

```javascript
// Numeric bucketing with explicit buckets
mixpanel.numeric_bucket('properties.age', [18, 25, 35, 45, 55, 65])

// Numeric bucketing with size and offset
mixpanel.numeric_bucket('properties.amount', {
    bucket_size: 100,
    offset: 0
})

// Time bucketing
.groupBy([
    mixpanel.numeric_bucket('time', mixpanel.daily_time_buckets)
], mixpanel.reducer.count())

// Weekly buckets
mixpanel.numeric_bucket('time', mixpanel.weekly_time_buckets)

// Monthly buckets
mixpanel.numeric_bucket('time', mixpanel.monthly_time_buckets)
```

### Multiple Keys Function

```javascript
// Expand list property into multiple grouping keys
.groupBy([
    mixpanel.multiple_keys("properties.tags")
], mixpanel.reducer.count())

// Without array wrapper
.groupBy(
    mixpanel.multiple_keys("properties.categories"),
    mixpanel.reducer.count()
)
```

## Reducers

### Basic Reducers

```javascript
// Count items
mixpanel.reducer.count()

// Count with sampling factor
mixpanel.reducer.count({account_for_sampling: true})

// Sum values
mixpanel.reducer.sum('properties.amount')

// Average
mixpanel.reducer.avg('properties.rating')

// With sampling
mixpanel.reducer.avg('properties.rating', {account_for_sampling: true})

// Minimum value
mixpanel.reducer.min('properties.price')

// Maximum value
mixpanel.reducer.max('properties.score')

// Any (non-deterministic selection)
mixpanel.reducer.any()
```

### Advanced Reducers

```javascript
// Top N items
mixpanel.reducer.top(10)

// Numeric percentiles
mixpanel.reducer.numeric_percentiles('properties.load_time', [25, 50, 75, 90, 95, 99])

// Numeric summary (min, max, avg, sum, count)
mixpanel.reducer.numeric_summary('properties.amount')

// Custom reducer with selector
mixpanel.reducer.sum(function(item) {
    return item.properties.quantity * item.properties.price;
})
```

## Advanced Patterns

### Complex Event Filtering

```javascript
// Multiple event types with different conditions
Events({
    from_date: '2024-01-01',
    to_date: '2024-01-31',
    event_selectors: [
        {
            event: 'Purchase',
            selector: 'properties["amount"] > 100'
        },
        {
            event: 'Add to Cart',
            selector: 'properties["category"] == "electronics"'
        },
        {
            selector: 'properties["source"] == "mobile" and event["$event_name"] != "Page View"'
        }
    ]
})
```

### User Journey Analysis

```javascript
function main() {
    return join(
        People({}),
        Events({
            from_date: '2024-01-01',
            to_date: '2024-01-31'
        }),
        {type: 'inner'}
    )
    .groupByUser(function(state, items) {
        state = state || {
            events: [],
            first_event: null,
            last_event: null
        };

        items.forEach(function(item) {
            if (item.event) {
                state.events.push(item.event.name);
                if (!state.first_event || item.event.time < state.first_event) {
                    state.first_event = item.event.time;
                }
                if (!state.last_event || item.event.time > state.last_event) {
                    state.last_event = item.event.time;
                }
            }
        });

        state.journey_duration = state.last_event - state.first_event;
        return state;
    })
    .filter(function(item) {
        return item.value.events.includes('Purchase');
    });
}
```

### Cohort Analysis

```javascript
function main() {
    return join(
        People({
            user_selectors: [{
                selector: 'user["$created"] >= datetime(2024, 1, 1)'
            }]
        }),
        Events({
            from_date: '2024-01-01',
            to_date: '2024-01-31',
            event_selectors: [{event: 'Purchase'}]
        })
    )
    .groupByUser(function(state, items) {
        state = state || {purchase_count: 0};
        items.forEach(function(item) {
            if (item.event && item.event.name == 'Purchase') {
                state.purchase_count++;
            }
        });
        return state;
    })
    .groupBy([
        function(item) {
            var count = item.value.purchase_count;
            if (count == 0) return "No purchases";
            if (count == 1) return "1 purchase";
            if (count <= 5) return "2-5 purchases";
            return "6+ purchases";
        }
    ], mixpanel.reducer.count());
}
```

### Time-based Aggregation

```javascript
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    })
    .groupBy([
        mixpanel.numeric_bucket('time', mixpanel.daily_time_buckets),
        'properties.category'
    ], [
        mixpanel.reducer.count(),
        mixpanel.reducer.sum('properties.amount'),
        mixpanel.reducer.avg('properties.amount')
    ])
    .map(function(item) {
        return {
            date: new Date(item.key[0] * 1000).toISOString().split('T')[0],
            category: item.key[1],
            event_count: item.value[0],
            total_revenue: item.value[1],
            avg_order_value: item.value[2]
        };
    });
}
```

### Funnel Analysis

```javascript
function main() {
    var funnel_events = ['View Product', 'Add to Cart', 'Checkout', 'Purchase'];

    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31',
        event_selectors: funnel_events.map(function(e) { return {event: e}; })
    })
    .groupByUser(function(state, events) {
        state = state || {};
        events.forEach(function(event) {
            state[event.name] = (state[event.name] || 0) + 1;
        });

        // Calculate funnel progression
        state.funnel_stage = 0;
        for (var i = 0; i < funnel_events.length; i++) {
            if (state[funnel_events[i]] > 0) {
                state.funnel_stage = i + 1;
            } else {
                break;
            }
        }

        return state;
    })
    .groupBy(['value.funnel_stage'], mixpanel.reducer.count())
    .map(function(item) {
        return {
            stage: item.key[0],
            stage_name: funnel_events[item.key[0] - 1] || 'Not in funnel',
            users: item.value
        };
    });
}
```

## Examples

### Example 1: Basic Event Count

```javascript
// Filter expression (API)
where: 'properties["plan"] == "premium" and properties["active"] == true'

// JQL equivalent
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    })
    .filter(function(e) {
        return e.properties.plan == "premium" && e.properties.active == true;
    })
    .reduce(mixpanel.reducer.count());
}
```

### Example 2: Revenue by Country

```javascript
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31',
        event_selectors: [{event: 'Purchase'}]
    })
    .groupBy(['properties.country'], [
        mixpanel.reducer.count(),
        mixpanel.reducer.sum('properties.amount'),
        mixpanel.reducer.avg('properties.amount')
    ])
    .map(function(item) {
        return {
            country: item.key[0],
            purchases: item.value[0],
            total_revenue: item.value[1],
            avg_order_value: item.value[2]
        };
    })
    .sortDesc('total_revenue');
}
```

### Example 3: User Retention

```javascript
function main() {
    return join(
        People({
            user_selectors: [{
                selector: 'user["$created"] >= datetime(2024, 1, 1) and user["$created"] < datetime(2024, 2, 1)'
            }]
        }),
        Events({
            from_date: '2024-01-01',
            to_date: '2024-03-31',
            event_selectors: [{event: 'App Open'}]
        }),
        {type: 'left'}
    )
    .groupByUser(function(state, items) {
        state = state || {
            signup_date: null,
            active_days: new Set()
        };

        items.forEach(function(item) {
            if (item.user && item.user.properties.$created) {
                state.signup_date = new Date(item.user.properties.$created);
            }
            if (item.event) {
                var event_date = new Date(item.event.time);
                var day_key = event_date.toISOString().split('T')[0];
                state.active_days.add(day_key);
            }
        });

        state.retention_days = state.active_days.size;
        return state;
    })
    .groupBy([
        function(item) {
            var days = item.value.retention_days;
            if (days == 0) return "Never returned";
            if (days == 1) return "1 day";
            if (days <= 7) return "2-7 days";
            if (days <= 30) return "8-30 days";
            return "30+ days";
        }
    ], mixpanel.reducer.count());
}
```

### Example 4: Complex Filtering

```javascript
// API filter expression
where: '(properties["amount"] >= 100 and properties["amount"] < 1000) and properties["country"] in ["US", "CA", "UK"] and (properties["category"] == "electronics" or properties["category"] == "books") and defined(properties["user_id"]) and not defined(properties["test_flag"])'

// JQL equivalent with comments
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31',
        event_selectors: [{
            selector: [
                '(properties["amount"] >= 100 and properties["amount"] < 1000)',
                'and properties["country"] in ["US", "CA", "UK"]',
                'and (properties["category"] == "electronics" or properties["category"] == "books")',
                'and defined(properties["user_id"])',
                'and not defined(properties["test_flag"])'
            ].join(' ')
        }]
    })
    .reduce(mixpanel.reducer.count());
}
```

### Example 5: Percentile Analysis

```javascript
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31',
        event_selectors: [{event: 'Page Load'}]
    })
    .groupBy(['properties.page_name'],
        mixpanel.reducer.numeric_percentiles('properties.load_time', [50, 75, 90, 95, 99])
    )
    .map(function(item) {
        return {
            page: item.key[0],
            p50: item.value[0].value,
            p75: item.value[1].value,
            p90: item.value[2].value,
            p95: item.value[3].value,
            p99: item.value[4].value
        };
    })
    .sortDesc('p90');
}
```

## Query Expression Best Practices

### 1. Performance Optimization

```javascript
// Use event selectors to filter early
Events({
    event_selectors: [{
        selector: 'properties["amount"] > 100'  // Filter at data source
    }]
})
// Instead of
Events({})
.filter(function(e) { return e.properties.amount > 100; })  // Filter after loading
```

### 2. Null Safety

```javascript
// Check for existence before accessing
.filter(function(e) {
    return e.properties.email && e.properties.email.indexOf('@') > -1;
})

// Use defined() in selectors
selector: 'defined(properties["user_id"]) and properties["amount"] > 0'
```

### 3. Date Range Optimization

```javascript
// Use specific date ranges
from_date: '2024-01-01',
to_date: '2024-01-31'

// Instead of very broad ranges
from_date: '2020-01-01',
to_date: '2024-12-31'
```

### 4. Efficient Grouping

```javascript
// Limit group cardinality
.groupBy(['properties.country'], reducer)  // Good: limited countries

// Avoid high-cardinality grouping without limits
.groupBy(['properties.user_id'], reducer)  // Bad: potentially millions of groups
// Better:
.groupByUser(reducer)  // Optimized for user-level aggregation
```

### 5. Sampling for Large Datasets

```javascript
// Use sampling-aware reducers for estimates
.reduce(mixpanel.reducer.count({account_for_sampling: true}))
.reduce(mixpanel.reducer.avg('properties.value', {account_for_sampling: true}))
```

## CLI Usage Examples

```bash
# Simple filter query
mp query events --where 'properties["plan"] == "premium"'

# Complex filter with multiple conditions
mp query events --where 'properties["amount"] > 100 and properties["country"] in ["US", "CA"]'

# JQL query from file
mp jql --file query.js --params '{"from_date": "2024-01-01", "to_date": "2024-01-31"}'

# Inline JQL query
mp jql --query 'function main() { return Events({from_date: "2024-01-01", to_date: "2024-01-31"}).reduce(mixpanel.reducer.count()); }'

# User filtering
mp users list --where 'user["plan"] == "premium" and defined(user["email"])'

# Export with filtering
mp export --from 2024-01-01 --to 2024-01-31 --where 'properties["amount"] > 1000'
```

## Error Handling

### Common Errors

1. **Invalid property access**
```javascript
// Error: Property doesn't exist
properties["nonexistent"]

// Solution: Check existence first
defined(properties["nonexistent"]) and properties["nonexistent"] > 0
```

2. **Type mismatch**
```javascript
// Error: Comparing string to number
properties["age"] > "eighteen"

// Solution: Use proper types
properties["age"] > 18
```

3. **Invalid date format**
```javascript
// Error: Invalid datetime
datetime("1/1/2024")

// Solution: Use ISO format or components
datetime("2024-01-01")
datetime(2024, 1, 1)
```

4. **Syntax errors in selectors**
```javascript
// Error: Unmatched brackets
properties["country" == "US"

// Solution: Proper bracket placement
properties["country"] == "US"
```

## Reference Tables

### Operator Precedence (highest to lowest)

1. Property access: `[]`, `.`
2. Function calls: `()`
3. Unary: `not`, `-`
4. Multiplicative: `*`, `/`, `%`
5. Additive: `+`, `-`
6. Relational: `<`, `<=`, `>`, `>=`, `in`
7. Equality: `==`, `!=`
8. Logical AND: `and`
9. Logical OR: `or`

### Reserved Keywords

- `and`, `or`, `not`
- `in`, `contains`
- `defined`
- `datetime`
- `true`, `false`, `null`
- `event`, `properties`, `user`
- `Events`, `People`, `join`
- `function`, `return`
- `params`

### Time Bucket Constants

- `mixpanel.daily_time_buckets` - Group by day
- `mixpanel.weekly_time_buckets` - Group by week
- `mixpanel.monthly_time_buckets` - Group by month
- `mixpanel.hourly_time_buckets` - Group by hour (if available)

## Summary

Mixpanel's Query Expression Language provides powerful capabilities for:
- **Filtering**: Complex conditional logic with property access
- **Transformation**: Map, filter, and reshape data
- **Aggregation**: Group and reduce with built-in and custom reducers
- **Analysis**: Joins, cohorts, funnels, and time-series analysis
- **Flexibility**: Full JavaScript support in JQL for complex logic

The combination of simple filter expressions for basic queries and JQL for complex analysis makes it suitable for both simple CLI operations and sophisticated data analysis tasks.