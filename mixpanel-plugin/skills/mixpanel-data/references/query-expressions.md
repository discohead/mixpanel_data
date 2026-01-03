# Query Expression Reference

Mixpanel provides two query expression systems for filtering and analyzing data.

## Table of Contents
- Filter Expressions (WHERE and ON)
- JQL (JavaScript Query Language)
- Built-in Reducers
- Common Patterns

## Filter Expressions

Used in `--where` and `--on` parameters. SQL-like syntax for filtering events and users.

### Property Access
```javascript
// Event properties
properties["country"]
properties["$browser"]
properties["custom_prop"]

// User properties (profile context)
user["$name"]
user["plan_type"]

// Event metadata
event["$event_name"]
event["$time"]
```

### Comparison Operators
```javascript
properties["browser"] == "Chrome"
properties["browser"] != "Safari"
properties["age"] > 18
properties["age"] >= 21
properties["age"] < 65
properties["price"] >= 10 and properties["price"] <= 100
properties["email"] == null
properties["email"] != null
```

### Logical Operators
```javascript
// AND
properties["plan"] == "premium" and properties["active"] == true

// OR
properties["source"] == "web" or properties["source"] == "mobile"

// NOT
not properties["beta_user"]
not (properties["age"] < 18)

// Complex
(properties["plan"] == "premium" or properties["plan"] == "enterprise") and properties["active"] == true
```

### Set Operations
```javascript
// IN operator
properties["country"] in ["US", "CA", "UK", "AU"]

// NOT IN
not (properties["status"] in ["deleted", "suspended"])

// Contains (substring)
properties["email"] contains "@company.com"
```

### Existence Functions
```javascript
// Check if defined
defined(properties["email"])
not defined(properties["deleted_at"])
```

### Date/Time Functions
```javascript
properties["created"] > datetime(2024, 1, 1)
properties["created"] >= datetime(2024, 1, 1, 0, 0, 0)
event["$time"] >= datetime("2024-01-01T00:00:00")
```

## ON Parameter (Segmentation Property)

The `--on` parameter segments results by a property. It accepts both **bare property names** and **full filter expressions**.

### Bare Property Names
Bare names are auto-wrapped to `properties["name"]`:
```bash
# These are equivalent:
mp query segmentation -e Purchase --on country
mp query segmentation -e Purchase --on 'properties["country"]'
```

### Full Filter Expressions
Use full expressions when you need accessor prefixes or complex logic:
```bash
# User property
mp query segmentation -e Purchase --on 'user["plan"]'

# Event property (explicit)
mp query segmentation -e Purchase --on 'properties["utm_source"]'
```

### CLI Usage
```bash
# Segment by country (bare name)
mp query segmentation -e Purchase --from 2024-01-01 --to 2024-01-31 --on country

# Segment by browser (special property with $)
mp query segmentation -e "Page View" --from 2024-01-01 --to 2024-01-31 --on '$browser'

# Funnel segmented by property
mp query funnel 12345 --from 2024-01-01 --to 2024-01-31 --on plan

# Numeric bucketing
mp query segmentation-numeric -e Purchase --from 2024-01-01 --to 2024-01-31 --on amount

# Sum by property
mp query segmentation-sum -e Purchase --from 2024-01-01 --to 2024-01-31 --on revenue

# Average by property
mp query segmentation-average -e Purchase --from 2024-01-01 --to 2024-01-31 --on order_value
```

### Python Usage
```python
# Segment by country (bare name)
result = ws.segmentation("Purchase", from_date="2024-01-01", to_date="2024-01-31",
                         on="country")

# Segment by browser (special property)
result = ws.segmentation("Page View", from_date="2024-01-01", to_date="2024-01-31",
                         on="$browser")

# Funnel segmented by property
result = ws.funnel(12345, from_date="2024-01-01", to_date="2024-01-31",
                   on="plan")

# Numeric bucketing
result = ws.segmentation_numeric("Purchase", from_date="2024-01-01", to_date="2024-01-31",
                                  on="amount")

# Sum of property
result = ws.segmentation_sum("Purchase", from_date="2024-01-01", to_date="2024-01-31",
                              on="revenue")

# Average of property
result = ws.segmentation_average("Purchase", from_date="2024-01-01", to_date="2024-01-31",
                                  on="order_value")
```

## WHERE Parameter (Filtering)

The `--where` parameter filters events/users before analysis. Always uses full expression syntax.

### CLI Usage
```bash
# Filter events by property
mp fetch events --from 2024-01-01 --to 2024-01-31 --where 'properties["country"] == "US"'

# Complex filter
mp fetch events --where 'properties["amount"] > 100 and properties["plan"] in ["premium", "enterprise"]'

# Filter profiles
mp fetch profiles --where 'user["plan"] == "premium" and defined(user["email"])'

# Segmentation with filter
mp query segmentation -e Purchase --from 2024-01-01 --to 2024-01-31 --where 'properties["amount"] > 100'

# Retention with filters
mp query retention -b "Sign Up" -r Purchase --from 2024-01-01 --to 2024-01-31 \
    --born-where 'properties["source"] == "organic"' \
    --return-where 'properties["amount"] > 50'

# Combine ON and WHERE
mp query segmentation -e Purchase --from 2024-01-01 --to 2024-01-31 \
    --on country --where 'properties["amount"] > 100'
```

### Python Usage
```python
# fetch_events with where filter
ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-31",
                where='properties["country"] == "US"')

# Segmentation with where
ws.segmentation("Purchase", from_date="2024-01-01", to_date="2024-01-31",
                where='properties["amount"] > 100')

# Retention with where filters
ws.retention(
    born_event="Sign Up",
    return_event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    born_where='properties["source"] == "organic"',
    return_where='properties["amount"] > 50'
)

# Combine on and where
ws.segmentation("Purchase", from_date="2024-01-01", to_date="2024-01-31",
                on="country", where='properties["amount"] > 100')
```

### ON vs WHERE Summary
| Parameter | Purpose | Accepts Bare Names | Example |
|-----------|---------|-------------------|---------|
| `on` | Segment/group by property | Yes | `--on country` |
| `where` | Filter before analysis | No | `--where 'properties["country"] == "US"'` |

## JQL (JavaScript Query Language)

Full JavaScript-based query language for complex data transformations and custom analysis.

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

### Data Sources

#### Events()
```javascript
Events({
    from_date: '2024-01-01',
    to_date: '2024-01-31',
    event_selectors: [
        {event: 'Sign Up'},
        {event: 'Purchase', selector: 'properties["amount"] > 100'},
        {selector: 'properties["source"] == "mobile"'}
    ]
})
```

Event object attributes: `name`, `distinct_id`, `time`, `sampling_factor`, `properties`

#### People()
```javascript
People({
    user_selectors: [{
        selector: 'user["plan"] == "premium"'
    }]
})
```

User object attributes: `distinct_id`, `time`, `last_seen`, `properties`

#### join()
```javascript
// Inner join - only users with events
join(People({}), Events({...}), {type: 'inner'})

// Left join - all users, with or without events
join(People({}), Events({...}), {type: 'left'})

// Full outer join
join(People({}), Events({...}), {type: 'full'})
```

### Transformations

#### filter()
```javascript
.filter(function(event) {
    return event.properties.amount > 100 &&
           event.properties.country == "US";
})
```

#### map()
```javascript
.map(function(event) {
    return {
        user: event.distinct_id,
        amount: event.properties.amount,
        day: new Date(event.time).toISOString().split('T')[0]
    };
})
```

#### groupBy()
```javascript
// Single property
.groupBy(['properties.country'], mixpanel.reducer.count())

// Multiple properties
.groupBy(['properties.country', 'properties.city'], mixpanel.reducer.count())

// Computed key
.groupBy([function(event) {
    return Math.floor(event.properties.amount / 100) * 100;
}], mixpanel.reducer.count())

// Multiple reducers
.groupBy(['properties.country'], [
    mixpanel.reducer.count(),
    mixpanel.reducer.sum('properties.amount'),
    mixpanel.reducer.avg('properties.amount')
])
```

#### groupByUser()
Events for each user processed in temporal order.
```javascript
.groupByUser(mixpanel.reducer.count())

// Custom aggregation
.groupByUser(function(state, events) {
    state = state || {event_count: 0, total_amount: 0};
    events.forEach(function(event) {
        state.event_count++;
        state.total_amount += event.properties.amount || 0;
    });
    return state;
})
```

#### reduce()
```javascript
.reduce(mixpanel.reducer.count())
```

#### sortAsc() / sortDesc()
```javascript
.groupBy(['properties.country'], mixpanel.reducer.count())
.sortDesc('value')
```

#### flatten()
```javascript
.reduce(mixpanel.reducer.top(10))
.flatten()
```

### Parameters
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

## Built-in Reducers

| Reducer | Description |
|---------|-------------|
| `mixpanel.reducer.count()` | Count elements |
| `mixpanel.reducer.sum('property')` | Sum numeric property |
| `mixpanel.reducer.avg('property')` | Average numeric property |
| `mixpanel.reducer.min('property')` | Minimum value |
| `mixpanel.reducer.max('property')` | Maximum value |
| `mixpanel.reducer.min_by('property')` | Element with minimum value |
| `mixpanel.reducer.max_by('property')` | Element with maximum value |
| `mixpanel.reducer.numeric_summary('property')` | Count, sum, avg, stddev |
| `mixpanel.reducer.numeric_percentiles('property', [50, 90, 99])` | Percentile values |
| `mixpanel.reducer.top(N)` | Top N by value |
| `mixpanel.reducer.any()` | Any single element |
| `mixpanel.reducer.null()` | Always returns null |
| `mixpanel.reducer.object_merge()` | Merge objects, sum numerics |

### Sampling-Aware Reducers
```javascript
// Account for Mixpanel's sampling
mixpanel.reducer.count({account_for_sampling: true})
mixpanel.reducer.avg('property', {account_for_sampling: true})
```

## Bucketing Functions

### Numeric Buckets
```javascript
// Explicit boundaries
mixpanel.numeric_bucket('properties.age', [0, 18, 30, 50, 65])

// Regular intervals
mixpanel.numeric_bucket('properties.amount', {bucket_size: 100, offset: 0})
```

### Time Buckets
```javascript
// Daily
mixpanel.numeric_bucket('time', mixpanel.daily_time_buckets)

// Weekly
mixpanel.numeric_bucket('time', mixpanel.weekly_time_buckets)

// Monthly
mixpanel.numeric_bucket('time', mixpanel.monthly_time_buckets)
```

### Multiple Keys (List Expansion)
```javascript
// Expand list property into multiple groups
.groupBy([mixpanel.multiple_keys('properties.tags')], mixpanel.reducer.count())
```

## Common Patterns

### Daily Event Counts
```javascript
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    })
    .groupBy([
        mixpanel.numeric_bucket('time', mixpanel.daily_time_buckets),
        'name'
    ], mixpanel.reducer.count())
    .map(function(item) {
        return {
            date: new Date(item.key[0]).toISOString().split('T')[0],
            event: item.key[1],
            count: item.value
        };
    });
}
```

### Revenue by Country
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
            avg_order: item.value[2]
        };
    })
    .sortDesc('total_revenue');
}
```

### User Event Sequences
```javascript
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    })
    .groupByUser(function(state, events) {
        state = state || {sequence: []};
        events.forEach(function(e) {
            state.sequence.push(e.name);
        });
        return state;
    })
    .filter(function(item) {
        return item.value.sequence.includes('Purchase');
    });
}
```

### Cohort Purchase Analysis
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
            to_date: '2024-03-31',
            event_selectors: [{event: 'Purchase'}]
        })
    )
    .groupByUser(function(state, items) {
        state = state || {purchase_count: 0, total_spend: 0};
        items.forEach(function(item) {
            if (item.event && item.event.name == 'Purchase') {
                state.purchase_count++;
                state.total_spend += item.event.properties.amount || 0;
            }
        });
        return state;
    })
    .groupBy([function(item) {
        var count = item.value.purchase_count;
        if (count == 0) return "No purchases";
        if (count == 1) return "1 purchase";
        if (count <= 5) return "2-5 purchases";
        return "6+ purchases";
    }], mixpanel.reducer.count());
}
```

### Percentile Analysis
```javascript
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31',
        event_selectors: [{event: 'Page Load'}]
    })
    .groupBy(['properties.page'],
        mixpanel.reducer.numeric_percentiles('properties.load_time', [50, 90, 95, 99])
    )
    .map(function(item) {
        return {
            page: item.key[0],
            p50: item.value[0].value,
            p90: item.value[1].value,
            p95: item.value[2].value,
            p99: item.value[3].value
        };
    })
    .sortDesc('p90');
}
```

### Unique Users per Country
```javascript
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    })
    .groupByUser(['properties.country'], mixpanel.reducer.null())
    .groupBy([mixpanel.slice('key', 1)], mixpanel.reducer.count());
}
```

### Funnel Analysis in JQL
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

## CLI JQL Usage

```bash
# From file
mp query jql script.js

# With parameters
mp query jql script.js --param from_date=2024-01-01 --param to_date=2024-01-31

# Inline script
mp query jql --script "function main() { return Events({from_date: '2024-01-01', to_date: '2024-01-01'}).reduce(mixpanel.reducer.count()); }"
```

## Python JQL Usage

```python
# From string
result = ws.jql("""
function main() {
    return Events({
        from_date: '2024-01-01',
        to_date: '2024-01-31'
    }).reduce(mixpanel.reducer.count());
}
""")

# With parameters
result = ws.jql("""
function main() {
    return Events({
        from_date: params.from_date,
        to_date: params.to_date
    }).reduce(mixpanel.reducer.count());
}
""", params={"from_date": "2024-01-01", "to_date": "2024-01-31"})

# Access results
print(result.data)  # Raw response
df = result.df      # As DataFrame
```

## Best Practices

### Performance
1. **Filter early**: Use `event_selectors` in Events() rather than `.filter()` after
2. **Limit date ranges**: Smaller ranges = faster queries
3. **Use groupByUser for user aggregation**: Optimized for per-user analysis
4. **Avoid high-cardinality groupBy**: Don't group by user_id directly

### Null Safety
```javascript
// Check existence before accessing
.filter(function(e) {
    return e.properties.email && e.properties.email.indexOf('@') > -1;
})

// Use defined() in selectors
selector: 'defined(properties["user_id"]) and properties["amount"] > 0'
```

### Date Handling
```javascript
// Valid formats
datetime(2024, 1, 1)
datetime(2024, 1, 1, 0, 0, 0)
datetime("2024-01-01")
datetime("2024-01-01T00:00:00")

// Invalid
datetime("1/1/2024")  // Wrong format
```
