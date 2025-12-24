---
title: Replace a Lookup Table
category:
  uri: Ingestion API
content:
  excerpt: ''
privacy:
  view: public
---
Lookup Tables must be [created via our UI](https://docs.mixpanel.com/docs/data-structure/lookup-tables#how-do-i-upload-a-lookup-table). Once a Lookup Table is created, its contents can be replaced via this API.

```sh
curl -XPUT 'https://api.mixpanel.com/lookup-tables/ID?project_id={YOUR_PROJECT_ID}' \
     -u 'SERVICE_ACCOUNT_USER:SERVICE_ACCOUNT_PASS' \
     -H 'Content-Type: text/csv' \
     --data 'id,artist,genre,is_platinum,name,num_listens,release_date,is_top_40
c994bb,Drake,Pop,True,Hotline Bling,1700000000,2015-10-18T22:00:00,true
d8d949,Gipsy Kings,Flamenco,False,Bamboleo,1170000,1987-07-12T05:00:00,false
a43fb8,Daft Punk,House,False,Aerodynamic,41000000,2001-03-12T07:30:00,false
'
```
```python
import requests

data = """id,artist,genre,is_platinum,name,num_listens,release_date,is_top_40
c994bb,Drake,Pop,True,Hotline Bling,1700000000,2015-10-18T22:00:00,true
d8d949,Gipsy Kings,Flamenco,False,Bamboleo,1170000,1987-07-12T05:00:00,false
a43fb8,Daft Punk,House,False,Aerodynamic,41000000,2001-03-12T07:30:00,false
"""

id = "LOOKUP_TABLE_ID"
project_id = "PROJECT_ID"

resp = requests.put(
    f"https://api.mixpanel.com/lookup-tables/{id}?project_id={project_id}",
    headers={"Content-Type": "text/csv",
    auth=(SERVICE_ACCOUNT_USER, SERVICE_ACCOUNT_PASS),
    data=data
)
print(resp.json()
```

### Validation

* The first column of the lookup table is assumed to be the ID of the row. All ID values must be unique.
* The first row of the lookup table is a header row. The values in the header must be unique, as each one uniquely identifies a column of the table. These will appear as properties of the lookup table in Mixpanel's UI.
* The CSV must be valid according to RFC4180.
* If the `Content-Encoding: gzip` header is supplied, the table will be decompressed before parsing.

#### Types

* Integers or floats will be parsed as numbers.
* RFC3339 timestamps (`2021-08-21T05:36:01Z`) will parsed as datetimes.
* `true` or `false` (case-insensitive) will be parsed as boolean.
* Empty fields (two adjacent commas) will be treated as `undefined`
* Comma separated, quoted strings in square brackets (`"[""Free"",""Paid"",""Enterprise""]"`) will be parsed as list of strings.
* All other values will be treated as strings.

#### Errors

Lookup Tables are replaced in their entirety or not replaced at all. When the Lookup Table fails to meet the above validation, we return an error that looks as follows:

```json
{
  "error": "some data points in the request failed validation",
  "failed_records": [
    {
      "index": 2,
      "message": "invalid row: row indexes 1 and 2 have the same primary key"
    },
    {
      "index": 3,
      "message": "invalid row: wrong number of fields"
    }
  ],
  "status": 0
}
```

We will return at most the first 10 rows that failed validation.

### Limits

This endpoint will return a 429 error if called more than 100 times in a rolling 24 hour window. We recommend updating lookup tables at most hourly to stay within this limit.

This endpoint will return a 413 error if a Lookup Table exceeds 100MB uncompressed. In practice, this translates to 1-2M rows. If you have a lookup table that exceeds the limit, we recommend pruning the number of columns to those that are useful to analysis. Removing long URLs or user-generated content can bring a lookup table within this limit. If you still exceed the limit, please reach out to us at [apis@mixpanel.com](mailto:apis@mixpanel.com) -- we'd love to hear your use case!
