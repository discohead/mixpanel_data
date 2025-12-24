---
title: Query Frequency Report
category:
  uri: Query API
content:
  excerpt: ''
privacy:
  view: public
---
Get data about how frequently users are performing events.

Let's breakdown an example response. If you specify `day` as \"unit\" and `hour` as \"addiction\_unit\", you will get a response that looks like this:

```json
{
  "2012-01-01": [
    305, 107, 60, 41, 32, 20, 12, 7, 4, 3, 3, 3, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1,
    1, 1
  ],
  "2012-01-02": [
    495, 204, 117, 77, 53, 36, 26, 20, 12, 7, 4, 3, 3, 1, 1, 1, 1, 0, 0, 0, 0,
    0, 0, 0
  ],
  "2012-01-03": [
    671, 324, 176, 122, 81, 63, 48, 31, 21, 14, 9, 5, 3, 1, 1, 1, 0, 0, 0, 0, 0,
    0, 0, 0
  ]
}
```

One day's worth of data is shown for each date, split into hours. On 2012-01-02, 495 users did the event `Viewed report` during at least 1 hour out of the next 24 hour period (the period specified by `unit`). 204 users did the event during at least 2 hours. 117 users did the event during at least 3 hours.

The Query API has a rate limit of 60 queries per hour and a maximum of 5 concurrent queries.
