---
title: Rate Limits
category:
  uri: Mixpanel APIs
content:
  excerpt: ''
privacy:
  view: public
---
We enforce a rate limit on our API to ensure the integrity of our system as well as prevent a single project from monopolizing the available resources for other projects. Getting a 429 response code from our API means that you have reached our rate-limit.

The rate limits are as follows:

### [**Ingestion API**](ref:ingestion-api)

2GB of uncompressed JSON/minute or \~30k events per second, measured on a rolling 1 minute basis. Please click [here](https://developer.mixpanel.com/reference/import-events#rate-limits) for more details.

### [**Query API**](ref:query-api)

A maximum of 5 concurrent queries and 60 queries per hour.

### [**Raw Data Export API**](ref:raw-data-export-api)

A maximum of 100 concurrent queries, 60 queries per hour, and 3 queries per second.

### [**Lexicon Schemas API**](ref:lexicon-schemas-api)

A maximum of 5 requests per minute, under 4000 events and properties updated in each minute, and less than 3000 total truncations/deletions per request.

### You can reduce rate-limiting errors using one of the two approaches:

* Spread your queries out over a longer period of time.
* Consolidate multiple queries into a single query (for example, multiple queries filtering on a single property may be combined into a single segmentation query).
