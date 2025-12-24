# Mixpanel Public API Reference for CLI Development

## Overview
This document serves as a comprehensive reference for Mixpanel's public APIs, structured specifically to support CLI tool (`mp`) development.

## Recent Updates
Based on official OpenAPI specifications and reference documentation:
- **Added Identity API**: $identify, $create_alias, and $merge operations for user identity management
- **Added Service Accounts API**: Full CRUD operations for programmatic service account management
- **Enhanced GDPR API**: Updated to v3.0 with CCPA support and detailed rate limits
- **Added Feature Flags API**: Evaluation and definition endpoints with context parameters
- **Updated Authentication**: Added OAuth token support and clarified authentication methods per API
- **Improved Rate Limits**: Specific limits per API including concurrent query restrictions
- **Added Query API Endpoints**: Insights (saved reports) with workspace support
- **Enhanced Error Codes**: Detailed HTTP response codes with descriptions
- **Deprecated Notice**: Data Pipelines API marked as deprecated

## Authentication

### Methods
1. **API Secret (Primary)**
   - Header: `Authorization: Basic <base64(api_secret:)>`
   - Used for: Query API, Export API, Data Management

2. **Project Token**
   - Parameter: `token=<project_token>`
   - Used for: Ingestion API (track, engage, import)

3. **Service Account**
   - Header: `Authorization: Bearer <service_account_token>`
   - Used for: Administrative APIs, Organization management

## Data Residency

### Regional Endpoints
- **US (Default)**
  - Ingestion: `api.mixpanel.com`
  - Query: `mixpanel.com/api`
  - Export: `data.mixpanel.com/api/2.0`

- **EU**
  - Ingestion: `api-eu.mixpanel.com`
  - Query: `eu.mixpanel.com/api`
  - Export: `data-eu.mixpanel.com/api/2.0`

- **India**
  - Ingestion: `api-in.mixpanel.com`
  - Query: `in.mixpanel.com/api`
  - Export: `data-in.mixpanel.com/api/2.0`

## API Categories

### 1. Ingestion API

#### Track Events
**Endpoint:** `POST /track`
```
Parameters:
- data: Base64 encoded JSON array of events
- verbose: 0|1 (detailed response)
- strict: 0|1 (strict validation)
- ip: 0|1 (use IP for geolocation)
- redirect: URL (redirect after tracking)
- callback: JSONP callback function
- test: 0|1 (test mode)

Event Format:
{
  "event": "Event Name",
  "properties": {
    "token": "PROJECT_TOKEN",
    "distinct_id": "user_id",
    "time": 1234567890,
    "ip": "123.123.123.123",
    "$insert_id": "unique_event_id",
    // custom properties
  }
}

Response:
- Success: {"status": 1}
- Error: {"status": 0, "error": "message"}
```

#### Update User Profiles
**Endpoint:** `POST /engage`
```
Parameters:
- data: Base64 encoded JSON array of updates
- verbose: 0|1
- strict: 0|1

Update Format:
{
  "$token": "PROJECT_TOKEN",
  "$distinct_id": "user_id",
  "$set": { /* properties to set */ },
  "$set_once": { /* properties to set once */ },
  "$add": { /* numeric properties to increment */ },
  "$append": { /* list properties to append */ },
  "$union": { /* list properties to union */ },
  "$unset": [ /* properties to remove */ ],
  "$delete": "" /* delete profile */
}

Response: Same as /track
```

#### Import Historical Data
**Endpoint:** `POST /import`
```
Parameters:
- data: Base64 encoded JSON array of events
- strict: 0|1
- project_id: Project ID (required)

Authentication: API Secret required
Event Format: Same as /track with historical timestamps
Rate Limit: 2GB per hour
```

### 2. Identity API

#### Create Identity (Link Anonymous to Known User)
**Endpoint:** `POST /track#create-identity`
```
Event Format:
{
  "event": "$identify",
  "properties": {
    "$identified_id": "ORIGINAL_ID",
    "$anon_id": "ANONYMOUS_ID",
    "token": "PROJECT_TOKEN"
  }
}

Description:
Links an anonymous ID to a canonical user ID. Critical for tracking users
across devices and sessions.
```

#### Create Alias
**Endpoint:** `POST /track#identity-create-alias`
```
Event Format:
{
  "event": "$create_alias",
  "properties": {
    "distinct_id": "CURRENT_ID",
    "alias": "NEW_ALIAS",
    "token": "PROJECT_TOKEN"
  }
}

Description:
Creates an alias for a user ID. Useful for linking multiple identifiers
to the same user (e.g., email, username, customer ID).
```

#### Merge Profiles
**Endpoint:** `POST /track#identity-merge`
```
Event Format:
{
  "event": "$merge",
  "properties": {
    "$distinct_ids": ["ID1", "ID2", "ID3"],
    "token": "PROJECT_TOKEN"
  }
}

Description:
Merges multiple user profiles into a single canonical profile.
All historical data is preserved and associated with the primary ID.
```

### 3. Query API

Base: `https://mixpanel.com/api/2.0/`

#### Events
**Endpoint:** `GET /events`
```
Parameters:
- event: Event name(s) to filter
- type: "general"|"unique"|"average"
- unit: "minute"|"hour"|"day"|"week"|"month"
- interval: Number of units
- from_date: YYYY-MM-DD
- to_date: YYYY-MM-DD
- where: Segmentation expression
- timezone: Timezone offset

Response:
{
  "data": {
    "series": ["2024-01-01", "2024-01-02"],
    "values": {
      "Event Name": {
        "2024-01-01": 100,
        "2024-01-02": 150
      }
    }
  }
}
```

**Endpoint:** `GET /events/top`
```
Parameters:
- type: "general"|"unique"|"average"
- limit: Number of events to return

Response:
{
  "events": [
    {"event": "Sign Up", "amount": 1000},
    {"event": "Login", "amount": 5000}
  ]
}
```

**Endpoint:** `GET /events/names`
```
Parameters:
- type: "general"|"unique"
- limit: Max events to return

Response:
["Event 1", "Event 2", "Event 3"]
```

#### Event Properties
**Endpoint:** `GET /events/properties`
```
Parameters:
- event: Event name
- name: Property name
- type: "general"|"unique"
- unit: Time unit
- interval: Number of units
- values: Property values to segment
- limit: Max values to return

Response:
{
  "data": {
    "series": ["2024-01-01"],
    "values": {
      "value1": {"2024-01-01": 100},
      "value2": {"2024-01-01": 50}
    }
  }
}
```

**Endpoint:** `GET /events/properties/top`
```
Parameters:
- event: Event name
- limit: Number of properties

Response:
{
  "$browser": 45.2,
  "$os": 38.1,
  "custom_prop": 22.3
}
```

**Endpoint:** `GET /events/properties/values`
```
Parameters:
- event: Event name
- name: Property name
- limit: Max values
- bucket: Bucket for numeric properties

Response:
["Chrome", "Firefox", "Safari"]
```

#### Segmentation
**Endpoint:** `GET /segmentation`
```
Parameters:
- event: Event name
- from_date: YYYY-MM-DD
- to_date: YYYY-MM-DD
- type: "general"|"unique"|"average"
- unit: Time unit
- where: Filter expression
- on: Property to segment on
- limit: Max segments

Response:
{
  "data": {
    "series": ["2024-01-01"],
    "values": {
      "Segment 1": {"2024-01-01": 100},
      "Segment 2": {"2024-01-01": 200}
    }
  }
}
```

#### Funnels
**Endpoint:** `GET /funnels`
```
Parameters:
- funnel_id: Funnel ID
- from_date: YYYY-MM-DD
- to_date: YYYY-MM-DD
- interval: Number of days
- unit: "day"|"week"|"month"
- on: Property to segment

Response:
{
  "data": {
    "2024-01-01": [
      {"count": 1000, "step": 0, "name": "Step 1"},
      {"count": 800, "step": 1, "name": "Step 2"}
    ]
  }
}
```

**Endpoint:** `GET /funnels/list`
```
Response:
[
  {
    "funnel_id": 123,
    "name": "Signup Flow",
    "steps": [...]
  }
]
```

#### Retention
**Endpoint:** `GET /retention`
```
Parameters:
- from_date: YYYY-MM-DD
- to_date: YYYY-MM-DD
- retention_type: "birth"|"compounded"
- born_event: Initial event
- event: Return event
- where: Filter expression
- interval: Number of days
- interval_count: Number of intervals

Response:
{
  "data": {
    "2024-01-01": {
      "counts": [1000, 800, 600, 400],
      "percents": [100, 80, 60, 40]
    }
  }
}
```

#### Insights (Saved Reports)
**Endpoint:** `GET /insights`
```
Parameters:
- project_id: Project ID (required)
- workspace_id: Workspace ID (required)
- bookmark_id: The saved report ID (required)

Response:
{
  "computed_at": "2020-09-21T16:35:41.252314+00:00",
  "date_range": {
    "from_date": "2020-08-31T00:00:00-07:00",
    "to_date": "2020-09-12T23:59:59.999000-07:00"
  },
  "series": {
    "Logged in": {
      "2020-08-31T00:00:00-07:00": 9852,
      "2020-09-07T00:00:00-07:00": 4325
    }
  }
}
```

#### JQL (JavaScript Query Language)
**Endpoint:** `POST /jql`
```
Headers:
- Content-Type: application/x-www-form-urlencoded

Parameters:
- script: JavaScript code (URL encoded)

Example Script:
function main() {
  return Events({
    from_date: '2024-01-01',
    to_date: '2024-01-31',
    event_selectors: [{event: "Signup"}]
  })
  .groupBy(["properties.$browser"], mixpanel.reducer.count())
}

Response:
[
  ["Chrome", 1500],
  ["Firefox", 800],
  ["Safari", 600]
]
```

### 4. Export API

#### Raw Event Export
**Endpoint:** `GET /export`
```
Parameters:
- from_date: YYYY-MM-DD (required)
- to_date: YYYY-MM-DD (required)
- event: Event names to filter (optional)
- where: Filter expression
- limit: Max events per page
- page: Page number

Response: JSONL format (one JSON object per line)
{"event": "Login", "properties": {...}}
{"event": "Signup", "properties": {...}}

Rate Limits:
- 60 requests per hour
- 3 concurrent requests
- Max 100 days per request
```

### 5. User Profiles API

#### List Users
**Endpoint:** `GET /engage`
```
Parameters:
- where: Filter expression
- session_id: Pagination session
- page: Page number
- page_size: Results per page (max 1000)

Response:
{
  "results": [
    {
      "$distinct_id": "user123",
      "$properties": {...}
    }
  ],
  "page": 0,
  "page_size": 1000,
  "session_id": "session123",
  "total": 5000
}
```

#### Query User
**Endpoint:** `GET /engage/query`
```
Parameters:
- distinct_id: User ID

Response:
{
  "$distinct_id": "user123",
  "$properties": {
    "$name": "John Doe",
    "$email": "john@example.com",
    ...
  }
}
```

### 6. Data Management API

#### Lexicon Schemas
**Endpoint:** `GET /projects/{projectId}/schemas`
```
Response:
{
  "event_schemas": [
    {
      "name": "Signup",
      "display_name": "User Signup",
      "description": "User creates account",
      "properties": {...}
    }
  ],
  "property_schemas": [...]
}
```

#### Delete Events
**Endpoint:** `POST /projects/{projectId}/delete-events`
```
Parameters:
- event_name: Event to delete
- start_date: YYYY-MM-DD
- end_date: YYYY-MM-DD

Response:
{
  "status": "pending",
  "deletion_job_id": "job123"
}
```

### 7. Organization & Project Management

#### List Projects
**Endpoint:** `GET /projects`
```
Response:
[
  {
    "id": 12345,
    "name": "Production",
    "token": "abc123",
    "timezone": "US/Pacific"
  }
]
```

#### Create Project
**Endpoint:** `POST /projects`
```
Body:
{
  "name": "New Project",
  "timezone": "US/Pacific"
}

Response:
{
  "id": 12346,
  "name": "New Project",
  "token": "xyz789",
  "api_secret": "secret123"
}
```

### 8. Service Accounts API

#### List Service Accounts
**Endpoint:** `GET /organizations/{organizationId}/service-accounts`
```
Response:
[
  {
    "id": "sa_123",
    "name": "API Integration",
    "created_at": "2024-01-01T00:00:00Z",
    "projects": ["project1", "project2"]
  }
]
```

#### Create Service Account
**Endpoint:** `POST /organizations/{organizationId}/service-accounts`
```
Body:
{
  "name": "New Service Account",
  "project_ids": [12345, 67890],
  "role": "admin"
}

Response:
{
  "id": "sa_124",
  "name": "New Service Account",
  "secret": "sa_secret_xyz",  // Only shown once
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### Add to Projects
**Endpoint:** `POST /organizations/{organizationId}/service-accounts/add-to-project`
```
Body:
{
  "service_account_ids": ["sa_123"],
  "project_ids": [12345],
  "role": "analyst"
}
```

#### Delete Service Account
**Endpoint:** `DELETE /organizations/{organizationId}/service-accounts/{serviceAccountId}`

### 9. GDPR Compliance API (v3.0)

#### Create Data Retrieval
**Endpoint:** `POST /api/app/data-retrievals/v3.0/?token={project_token}`
```
Headers:
- Authorization: Bearer {oauth_token}

Body:
{
  "distinct_ids": ["user123", "user456"],  // Max 2000 IDs
  "compliance_type": "GDPR",  // or "CCPA"
  "disclosure_type": "DATA"    // CCPA only: DATA, CATEGORIES, or SOURCES
}

Response:
{
  "status": "ok",
  "results": [{
    "status": "PENDING",
    "tracking_id": "1583792934719392965",
    "project_id": 1978118,
    "distinct_id_count": 2
  }]
}

Rate Limit: 1 request/second, max 5 years of data scans
```

#### Check Retrieval Status
**Endpoint:** `GET /api/app/data-retrievals/v3.0/{tracking_id}?token={project_token}`
```
Response:
{
  "results": {
    "status": "SUCCESS",  // PENDING, STAGING, STARTED, SUCCESS, FAILURE, REVOKED
    "destination_url": "https://..."  // When SUCCESS
  }
}
```

#### Create Data Deletion
**Endpoint:** `POST /api/app/data-deletions/v3.0/?token={project_token}`
```
Headers:
- Authorization: Bearer {oauth_token}

Body:
{
  "distinct_ids": ["user123"],
  "compliance_type": "GDPR"  // or "CCPA"
}

Response:
{
  "status": "ok",
  "results": [{
    "status": "PENDING",
    "deletion_job_id": "job123"
  }]
}
```

## Rate Limits

### API-Specific Limits
- Query API: 60 queries/hour, max 5 concurrent queries
- Export API: 100 requests/hour, 3 concurrent requests
- Ingestion API: 2GB/hour for imports
- JQL API: 60 requests/hour
- GDPR API: 1 request/second, max 5 years of data scans
- Feature Flags API: Standard rate limits apply

### Response Codes
- 200: Success - Request completed successfully
- 201: Created - Resource created successfully
- 400: Bad Request - Invalid parameters or malformed request
- 401: Unauthorized - Invalid or missing credentials
- 402: Payment Required - Quota exceeded or feature not in plan
- 403: Forbidden - Valid credentials but insufficient permissions
- 404: Not Found - Resource or endpoint not found
- 429: Too Many Requests - Rate limit exceeded
- 500: Internal Server Error - Server-side error
- 502: Bad Gateway - Upstream service error
- 503: Service Unavailable - Temporary service outage

## Additional APIs

### 10. Data Pipelines API (Deprecated)

**Note:** This API is deprecated. Use the Mixpanel UI for creating and managing pipelines.

### 11. Data Pipelines API (Legacy)

#### Warehouse Import
**Endpoint:** `POST /data-pipelines/warehouse/sync`
```
Body:
{
  "warehouse_id": "warehouse123",
  "sync_type": "incremental"|"full",
  "tables": ["users", "events"]
}

Response:
{
  "sync_id": "sync123",
  "status": "running",
  "started_at": "2024-01-01T00:00:00Z"
}
```

#### Pipeline Status
**Endpoint:** `GET /data-pipelines/status/{sync_id}`
```
Response:
{
  "sync_id": "sync123",
  "status": "completed"|"failed"|"running",
  "rows_processed": 1000000,
  "errors": []
}
```

### 12. Cohorts API

#### List Cohorts
**Endpoint:** `GET /cohorts/list`
```
Parameters:
- project_id: Project ID

Response:
[
  {
    "id": "cohort123",
    "name": "Power Users",
    "count": 5000,
    "created": "2024-01-01"
  }
]
```

#### Create Cohort
**Endpoint:** `POST /cohorts`
```
Body:
{
  "name": "New Cohort",
  "project_id": 12345,
  "filter": {
    "type": "user",
    "selector": {...}
  }
}
```

### 13. Annotations API

#### List Annotations
**Endpoint:** `GET /annotations`
```
Parameters:
- from_date: YYYY-MM-DD
- to_date: YYYY-MM-DD

Response:
[
  {
    "id": 123,
    "date": "2024-01-01",
    "description": "Product launch"
  }
]
```

#### Create Annotation
**Endpoint:** `POST /annotations`
```
Body:
{
  "date": "2024-01-01",
  "description": "New feature release"
}
```

### 14. Feature Flags API

Base: `https://api.mixpanel.com/flags` (or regional equivalent)

#### Evaluate Feature Flags
**Endpoint:** `GET /flags?token={project_token}`
```
Parameters:
- token: Project token (required)
- context: URL-encoded JSON with evaluation context

Context Format (before encoding):
{
  "distinct_id": "user123",      // Required
  "device_id": "device456",      // Optional
  "custom_properties": {         // Optional
    "plan": "premium",
    "country": "US"
  }
}

Response:
{
  "feature_flag_1": "variant_a",
  "feature_flag_2": true,
  "feature_flag_3": "control"
}
```

#### Get Flag Definitions
**Endpoint:** `GET /flags/definitions?token={project_token}`
```
Response:
{
  "flags": [
    {
      "id": "flag_123",
      "name": "new_checkout_flow",
      "enabled": true,
      "variants": [
        {"key": "control", "value": false},
        {"key": "variant_a", "value": true}
      ],
      "rollout_percentage": 50,
      "targeting_rules": [...]
    }
  ]
}
```

## Response Format Details

### Standard Success Response
```json
{
  "status": "success",
  "results": {...},
  "pagination": {
    "page": 1,
    "page_size": 100,
    "total": 1000
  }
}
```

### Standard Error Response
```json
{
  "status": "error",
  "error": "Invalid parameter",
  "error_code": "INVALID_PARAM",
  "details": {
    "parameter": "from_date",
    "message": "Must be in YYYY-MM-DD format"
  }
}
```

### Streaming Response (Export/JQL)
- Content-Type: `application/x-jsonlines`
- Each line is a complete JSON object
- No overall wrapper object
- Supports chunked transfer encoding

## Authentication Details

### API Secret Authentication
```bash
# Basic Auth header (Query API, Export API)
Authorization: Basic $(echo -n "API_SECRET:" | base64)

# URL parameter (deprecated but supported)
?api_key=API_SECRET
```

### Project Token Authentication
```bash
# In request body (Ingestion API)
{
  "properties": {
    "token": "PROJECT_TOKEN"
  }
}

# URL parameter (Feature Flags, GDPR APIs)
?token=PROJECT_TOKEN
```

### Service Account Authentication
```bash
# Basic Auth header
Authorization: Basic $(echo -n "SERVICE_ACCOUNT_USERNAME:SERVICE_ACCOUNT_SECRET" | base64)

# Used for: Organization management, Service Account APIs, Lexicon APIs
```

### OAuth Token Authentication
```bash
# Bearer token header (GDPR API)
Authorization: Bearer OAUTH_TOKEN

# Generate OAuth token:
POST /oauth/token
{
  "grant_type": "client_credentials",
  "client_id": "...",
  "client_secret": "..."
}

# Used for: GDPR compliance operations requiring special permissions
```

## Query Expression Language

### Filter Syntax (WHERE parameter)
```javascript
// Basic comparison
properties["$browser"] == "Chrome"
properties["age"] > 18

// Boolean operations
properties["plan"] == "premium" and properties["active"] == true
properties["source"] == "web" or properties["source"] == "mobile"

// Set operations
properties["country"] in ["US", "CA", "UK"]
not properties["beta_user"]

// Null checking
defined(properties["email"])
not defined(properties["deleted_at"])

// String operations
"premium" in properties["tags"]
properties["name"] contains "John"

// Date operations
properties["created"] > datetime(2024, 1, 1)ß
```
