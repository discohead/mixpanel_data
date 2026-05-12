# Research: Mixpanel API Client

**Date**: 2025-12-20
**Feature**: 002-api-client

## Research Topics

1. Mixpanel API Authentication
2. Regional Endpoint Routing
3. Rate Limiting Strategies
4. Streaming JSONL Parsing with httpx
5. Profile Export Pagination
6. Error Response Formats

---

## 1. Mixpanel API Authentication

### Decision: HTTP Basic Auth with Service Account Credentials

### Rationale
Mixpanel supports three authentication methods, but service accounts are the recommended approach for automated systems:

| Method | Support | Use Case |
|--------|---------|----------|
| Service Account (Basic Auth) | ✅ Recommended | Automated systems, libraries |
| Project Secret (Basic Auth) | ⚠️ Deprecated | Legacy systems |
| OAuth Token (Bearer) | Limited | GDPR/privacy APIs only |

### Implementation
```python
import base64

auth = base64.b64encode(f"{username}:{secret}".encode()).decode()
headers = {"Authorization": f"Basic {auth}"}
# Plus: project_id in query params
```

### Alternatives Considered
- **OAuth2**: Only supported for limited privacy APIs; adds complexity without benefit
- **API Key in Header**: Not supported by Mixpanel

---

## 2. Regional Endpoint Routing

### Decision: Build URLs dynamically based on region from Credentials

### Rationale
Mixpanel uses different base URLs for different data residency regions. The URL structure varies by API type (Query vs Export).

| Region | Query API Base | Export API Base |
|--------|---------------|-----------------|
| US (default) | `https://mixpanel.com/api/query` | `https://data.mixpanel.com/api/2.0/export` |
| EU | `https://eu.mixpanel.com/api/query` | `https://data-eu.mixpanel.com/api/2.0/export` |
| India | `https://in.mixpanel.com/api/query` | `https://data-in.mixpanel.com/api/2.0/export` |

### Implementation
```python
ENDPOINTS = {
    "us": {"query": "https://mixpanel.com/api/query", "export": "https://data.mixpanel.com/api/2.0"},
    "eu": {"query": "https://eu.mixpanel.com/api/query", "export": "https://data-eu.mixpanel.com/api/2.0"},
    "in": {"query": "https://in.mixpanel.com/api/query", "export": "https://data-in.mixpanel.com/api/2.0"},
}
```

### Alternatives Considered
- **Single endpoint with header**: Not supported by Mixpanel
- **Environment variable override**: Added complexity; region is already in Credentials

---

## 3. Rate Limiting Strategies

### Decision: Exponential backoff with jitter, respecting Retry-After header

### Rationale
Mixpanel rate limits vary by API:

| API | Rate Limit | Concurrent |
|-----|-----------|------------|
| Export | 60/hour, 3/second | 100 |
| Query | 60/hour | 5 |
| Lexicon | 5/minute | N/A |

When rate limited, Mixpanel returns HTTP 429 with optional `Retry-After` header.

### Implementation
```python
def calculate_backoff(attempt: int, base: float = 1.0, max_delay: float = 60.0) -> float:
    delay = min(base * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
    return delay + jitter
```

### Alternatives Considered
- **Fixed delay**: Less adaptive to burst patterns
- **Per-endpoint tracking**: Adds complexity; not needed for single-client use
- **Global rate limiter**: Would require shared state; complicates testing

---

## 4. Streaming JSONL Parsing with httpx

### Decision: Use httpx streaming with line-by-line parsing

### Rationale
The Export API returns JSONL (newline-delimited JSON) as `text/plain`. Each line is a complete JSON object representing one event. For 1M+ events, we must stream to avoid memory exhaustion.

### Implementation
```python
def export_events(self, ...) -> Iterator[dict]:
    with self._client.stream("GET", url, params=params) as response:
        for line in response.iter_lines():
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(f"Skipping malformed line: {line[:100]}")
```

### Key Considerations
- `iter_lines()` handles buffering across chunk boundaries
- Skip empty lines (trailing newlines)
- Log and skip malformed JSON (don't fail entire export)
- Support gzip via `Accept-Encoding: gzip` header

### Alternatives Considered
- **Load all into memory**: Fails for large exports
- **ijson streaming parser**: Overkill for JSONL; adds dependency
- **Custom chunked parser**: httpx already handles this well

---

## 5. Profile Export Pagination

### Decision: Iterate with session_id pagination, yield profiles as iterator

### Rationale
Unlike events (JSONL stream), profiles use `POST /engage` with JSON response and pagination via `session_id`. The response includes:
- `results`: Array of profile objects
- `session_id`: Token for next page (omit on first request)
- `page`: Current page number

### Implementation
```python
def export_profiles(self, ...) -> Iterator[dict]:
    session_id = None
    page = 0
    while True:
        params = {"page": page}
        if session_id:
            params["session_id"] = session_id
        response = self._client.post(url, json=params).json()

        for profile in response.get("results", []):
            yield profile

        if not response.get("results"):
            break
        session_id = response.get("session_id")
        page += 1
```

### Alternatives Considered
- **Return all profiles at once**: Memory issues for large profile sets
- **Async pagination**: Adds complexity; sync is sufficient for MVP

---

## 6. Error Response Formats

### Decision: Parse error body, map to exception hierarchy

### Rationale
Mixpanel returns errors in consistent format:
```json
{
    "error": "Details about the error",
    "status": "error"
}
```

HTTP status codes map to exceptions:

| Status | Exception | Behavior |
|--------|-----------|----------|
| 400 | QueryError | Include error message in details |
| 401 | AuthenticationError | Check credentials |
| 429 | (retry) or RateLimitError | Retry with backoff; raise after max attempts |
| 5xx | MixpanelDataError | Suggest retry |

### Implementation
```python
def _handle_response(self, response: httpx.Response) -> Any:
    if response.status_code == 401:
        raise AuthenticationError("Invalid credentials")
    if response.status_code == 429:
        raise RateLimitError(retry_after=response.headers.get("Retry-After"))
    if response.status_code == 400:
        error = response.json().get("error", "Unknown error")
        raise QueryError(error)
    if response.status_code >= 500:
        raise MixpanelDataError(f"Server error: {response.status_code}")
    response.raise_for_status()
    return response.json()
```

### Alternatives Considered
- **Generic exception for all errors**: Loses specificity for callers
- **httpx default exception handling**: Doesn't provide Mixpanel-specific context

---

## Summary

All research questions resolved. No NEEDS CLARIFICATION items remain.

| Topic | Decision | Confidence |
|-------|----------|------------|
| Authentication | HTTP Basic with service account | High |
| Regional routing | Dynamic URL by region | High |
| Rate limiting | Exponential backoff + jitter | High |
| Streaming | httpx iter_lines() for JSONL | High |
| Profile pagination | session_id iteration | High |
| Error handling | Map to exception hierarchy | High |
