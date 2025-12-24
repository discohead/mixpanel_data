---
title: Limits
category:
  uri: Lexicon Schemas API
content:
  excerpt: ''
privacy:
  view: public
---
The Schemas API has the following limits:

* requests per organization per minute: 5
* events and properties updated per organization per minute: 4000
* total truncations/deletions per request: 3000

If you approach these limits, consider breaking your requests into smaller batches. These limits are typically reached when performing bulk create or update operations.
