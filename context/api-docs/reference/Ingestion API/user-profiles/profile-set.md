---
title: Set Property
category:
  uri: Ingestion API
content:
  excerpt: >-
    Takes a JSON object containing names and values of profile properties. If
    the profile does not exist, it creates it with these properties. If it does
    exist, it sets the properties to these values, overwriting existing values.
privacy:
  view: public
---
<Callout icon="📘" theme="info">
  This API will return a `200 OK` even if there are data validation issues. To ensure the request actually succeeded, you need to check the response body.
</Callout>

<Callout icon="📘" theme="info">
  This API does not support gzip encoding.
</Callout>
