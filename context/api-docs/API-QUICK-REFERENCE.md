# Mixpanel API Quick Reference

## Authentication Quick Guide

| API | Method | Format | Example |
|-----|--------|--------|---------|
| Query/Export | API Secret | Basic Auth | `Authorization: Basic <base64(secret:)>` |
| Ingestion | Project Token | Body/URL | `?token=PROJECT_TOKEN` |
| Service/Lexicon | Service Account | Basic Auth | `Authorization: Basic <base64(user:secret)>` |
| GDPR | OAuth Token | Bearer | `Authorization: Bearer TOKEN` |
| Feature Flags | Project Token | URL | `?token=PROJECT_TOKEN` |

## Regional Endpoints

| Region | Ingestion | Query | Export |
|--------|-----------|-------|--------|
| US | api.mixpanel.com | mixpanel.com/api | data.mixpanel.com/api/2.0 |
| EU | api-eu.mixpanel.com | eu.mixpanel.com/api | data-eu.mixpanel.com/api/2.0 |
| India | api-in.mixpanel.com | in.mixpanel.com/api | data-in.mixpanel.com/api/2.0 |

## Common Operations

### Track Event
```bash
POST /track
Body: data=<base64({
  "event": "Purchase",
  "properties": {
    "token": "PROJECT_TOKEN",
    "distinct_id": "user123",
    "amount": 99.99
  }
})>
```

### Query Events
```bash
GET /api/2.0/events
?from_date=2024-01-01
&to_date=2024-01-31
&event=["Login","Signup"]
&type=unique
&unit=day
```

### Export Raw Data
```bash
GET /api/2.0/export
?from_date=2024-01-01
&to_date=2024-01-31
&event=["Purchase"]
&where=properties["amount"]>100
```

### Update User Profile
```bash
POST /engage
Body: data=<base64({
  "$token": "PROJECT_TOKEN",
  "$distinct_id": "user123",
  "$set": {
    "plan": "premium",
    "updated_at": "2024-01-01"
  }
})>
```

### Link User Identity
```bash
POST /track#create-identity
Body: data=<base64({
  "event": "$identify",
  "properties": {
    "$identified_id": "user123",
    "$anon_id": "anon456",
    "token": "PROJECT_TOKEN"
  }
})>
```

### JQL Query
```bash
POST /api/2.0/jql
Body: script=<urlencoded(
  function main() {
    return Events({
      from_date: '2024-01-01',
      to_date: '2024-01-31'
    }).reduce(mixpanel.reducer.count())
  }
)>
```

### GDPR Export
```bash
POST /api/app/data-retrievals/v3.0/?token=PROJECT_TOKEN
Headers: Authorization: Bearer OAUTH_TOKEN
Body: {
  "distinct_ids": ["user123"],
  "compliance_type": "GDPR"
}
```

### Feature Flag Evaluation
```bash
GET /flags?token=PROJECT_TOKEN
&context=<urlencoded({
  "distinct_id": "user123",
  "custom_properties": {
    "plan": "premium"
  }
})>
```

## Rate Limits

| API | Limit | Concurrent |
|-----|-------|------------|
| Query | 60/hour | 5 max |
| Export | 100/hour | 3 max |
| JQL | 60/hour | - |
| GDPR | 1/second | ~5 years data |
| Ingestion Import | 2GB/hour | - |

## HTTP Response Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 201 | Created | Resource created |
| 400 | Bad Request | Check parameters |
| 401 | Unauthorized | Check credentials |
| 402 | Payment Required | Check quota/plan |
| 403 | Forbidden | Check permissions |
| 404 | Not Found | Check endpoint/resource |
| 429 | Rate Limited | Retry with backoff |
| 500 | Server Error | Retry later |
| 502 | Bad Gateway | Retry later |
| 503 | Service Unavailable | Retry later |

## Query Filter Syntax

### Basic Operations
```javascript
// Equality
properties["browser"] == "Chrome"
properties["age"] >= 18

// Boolean
properties["premium"] == true and properties["active"] == true
properties["source"] == "web" or properties["source"] == "mobile"

// Sets
properties["country"] in ["US", "CA", "UK"]
not properties["beta_user"]

// Existence
defined(properties["email"])
not defined(properties["deleted_at"])

// Strings
properties["email"] contains "@company.com"

// Dates
properties["created"] > datetime(2024, 1, 1)
event["$time"] >= datetime("2024-01-01T00:00:00")
```

## JQL Essentials

### Data Sources
```javascript
Events({from_date: '2024-01-01', to_date: '2024-01-31'})
People({user_selectors: [{selector: 'user["plan"] == "premium"'}]})
join(People({}), Events({}), {type: 'inner'})
```

### Common Operations
```javascript
.filter(e => e.properties.amount > 100)
.map(e => ({user: e.distinct_id, amount: e.properties.amount}))
.groupBy(['properties.country'], mixpanel.reducer.count())
.groupByUser(mixpanel.reducer.sum('properties.amount'))
.reduce(mixpanel.reducer.avg('properties.rating'))
```

### Reducers
```javascript
mixpanel.reducer.count()
mixpanel.reducer.sum('properties.amount')
mixpanel.reducer.avg('properties.rating')
mixpanel.reducer.min('properties.price')
mixpanel.reducer.max('properties.score')
mixpanel.reducer.percentiles('properties.load_time', [50, 90, 99])
```

## Pagination Patterns

### Query API
```javascript
// Use date ranges for pagination
from_date: '2024-01-01'
to_date: '2024-01-07'  // Week 1
// Then: '2024-01-08' to '2024-01-14' // Week 2
```

### Export API
```javascript
?page=0&limit=1000  // Page 1
?page=1&limit=1000  // Page 2
```

### User Profiles
```javascript
?session_id=xxx&page=0  // First request returns session_id
?session_id=xxx&page=1  // Use session_id for subsequent pages
```

## Common Pitfalls

1. **Wrong Authentication** - Each API uses different auth methods
2. **Missing Region** - Always specify data residency
3. **Date Format** - Must be YYYY-MM-DD
4. **Rate Limits** - Implement exponential backoff
5. **Large Exports** - Use streaming/pagination
6. **Time Zones** - Query API uses project timezone
7. **URL Encoding** - JQL scripts and contexts must be encoded
8. **Batch Limits** - Max 50 events per batch, 2000 IDs for GDPR
