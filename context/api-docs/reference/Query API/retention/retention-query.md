---
title: Query Retention Report
category:
  uri: Query API
content:
  excerpt: ''
privacy:
  view: public
---
Get cohort analysis.

If you specify neither an `interval` nor a `unit`, the `interval` is 1 day. This means that each user gets 24 hours in each interval to do the specified event.

An example response with a `born_event` of 'event integration' and `event` of 'viewed report' might look like this:

```json
{
  "2012-01-01": {
    "counts": [2, 1, 2],
    "first": 2
  },
  "2012-01-02": {
    "counts": [9, 7, 6],
    "first": 10
  },
  "2012-01-03": {
    "counts": [9, 6, 4],
    "first": 10
  }
}
```

These results indicate that on 2012-01-02, 10 users did the `born_event` (\"event integration\"), as indicated by the first field. If the `retention_type=compounded`, then first will instead indicate the number of users who did `event` (\"viewed report\") on the specified date. 9 of those users did `event` (\"viewed report\") within 24 hours (the \"0th\" interval) of doing the `born_event`. Seven of those did `event` between 24 and 48 hours (interval 1) of the `born_event`. These 7 are a subset of the initial 10, but not necessarily a subset of the 9 (retention is not a funnel; see the number increase between 72 and 96 hours). And finally, 6 users did `event` between 48 and 72 hours (interval 2) after the `born_event`.

In the Mixpanel retention UI, \"First time\" corresponds to `retention_type=birth`, and \"Recurring\" corresponds to `retention_type=compounded`.

The Query API has a rate limit of 60 queries per hour and a maximum of 5 concurrent queries.
