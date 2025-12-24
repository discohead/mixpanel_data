---
title: Download Data
category:
  uri: Event Export API
content:
  excerpt: >-
    Every data point sent to Mixpanel is stored as JSON in our data store. The
    raw export API allows you to download your event data as it is received and
    stored within Mixpanel, complete with all event properties (including
    distinct_id) and the exact timestamp the event was fired.

    The raw export API has a rate limit of 60 queries per hour, 3 queries per
    second, and a maximum of 100 concurrent queries. If you exceed the rate
    limit, a 429 error will be returned.
privacy:
  view: public
---

