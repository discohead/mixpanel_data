---
title: Query Profiles
category:
  uri: Query API
content:
  excerpt: ''
privacy:
  view: public
---
Query user (or group) profile data and return list of users (or groups) that fit specified parameters.

API responses will return at most `page_size` records for each request. To request additional records, callers should repeat their call to the API using the same `where` param, but provide a `session_id` parameter with a value taken from the first response, and include a `page` parameter with a value one greater than the value of page in the response.

A caller trying to retrieve all of the records for a particular query might use an algorithm something like this:

```javascript
// Get the first page of data associated with our selector expression
this_page = query_api(where=YOUR_SELECTOR_EXPRESSION)
do_something_with_response(this_page)

// If we get fewer records than the page_size returned with our results,
// then there are no more records to get. Otherwise, keep querying for additional pages.
while (length of this_page.results) >= this_page.page_size:
    next_page_number = this_page.page + 1
    this_page = query_api(where=YOUR_SELECTOR_EXPRESSION, session_id=this_page.session_id, page=next_page_number)
    do_something_with_response(this_page)
```

The Query API has a rate limit of 60 queries per hour and a maximum of 5 concurrent queries.
