---
title: Track Events
category:
  uri: Ingestion API
content:
  excerpt: ''
privacy:
  view: public
---
Track events to Mixpanel from client devices. We recommend using one of our client-side SDKs instead of using /track directly, as our SDKs provide queueing, retrying, batching, and more.

## When to use /track vs /import

Typically, we recommend using /import for server-side integrations as it is more scalable and supports ingesting historical data. We only recommend /track for client-side tracking in an environment for which we don't have SDK support or if you're sending data via some other untrusted environment (eg: third-party webhooks that send data to Mixpanel).

|                             | /track                                         | /import                                                               |
| --------------------------- | ---------------------------------------------- | --------------------------------------------------------------------- |
| Events per request          | 2000                                           | 2000                                                                  |
| Authentication              | Project Token, intended for untrusted clients. | Project Secret/Service Account, intended for server-side integration. |
| Compression                 | Gzip allowed                                   | Gzip allowed                                                          |
| Content-Type                | application/x-www-form-urlencoded              | application/json or application/x-ndjson                              |
| Ingesting historical events | Last 5 days only.                              | Any time after 1971-01-01.                                            |

## Limits

The limits for track are the same as /import, [see here](https://developer.mixpanel.com/reference/import-events#rate-limits).

Each event has the following size limits:

- Must be smaller than 1MB of uncompressed JSON.
- Must have fewer than 255 properties.
- All nested object properties must have fewer than 255 keys and max nesting depth is 3.
- All array properties must have fewer than 255 elements.

To ensure real-time ingestion and quality-of-service, we have a rate limit of 2GB of uncompressed JSON/minute or ~30k events per second, measured on a rolling 1 minute basis.

We recommend the following when it comes to sending data to our API at scale:

- Send data as quickly as possible with concurrent clients until the server returns 429. We see the best results with 10-20 concurrent clients sending 2K events per batch.
- When you see 429s, employ an [exponential backoff with jitter](https://docs.aws.amazon.com/general/latest/gr/api-retries.html) strategy. We recommend starting with a backoff of 2s and doubling backoff until 60s, with 1-5s of jitter.
- We recommend gzip compression and using `Content-Encoding: gzip` to reduce network egress and transfer time.
- In the rare event that our API returns a 502 or 503 status code, we recommend employing the same exponential backoff strategy as with 429s.
- Please do not retry validation errors (400 status code), as they will consistently fail and count toward the rate limit.

If you are an Enterprise customer that requires a higher rate limit, please reach out to your CSM with your `project_id` and use case.
