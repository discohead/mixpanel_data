---
title: Authentication
category:
  uri: Warehouse Connectors API
content:
  excerpt: ''
privacy:
  view: public
---
A [service account](ref:service-accounts) is necessary to authenticate Warehouse Connectors API requests. Once you have created a service account and obtained your user name and secret, you can make a request to trigger a warehouse import.

```bash cURL Basic Auth
curl -X PUT https://mixpanel.com/api/app/projects/<your_project_id>/warehouse-sources/imports/<your_import_id>/manual-sync \
	--user "<serviceaccount_username>:<serviceaccount_secret>"
```
```shell cURL Header
curl -X PUT https://mixpanel.com/api/app/projects/<your_project_id>/warehouse-sources/imports/<your_import_id>/manual-sync \
	--header 'authorization: Basic <serviceaccount_username>:<serviceaccount_secret>'
```
```python Python Requests
import requests
requests.put(
  'https://mixpanel.com/api/app/projects/<your_project_id>/warehouse-sources/imports/',
  auth=('<serviceaccount_username>', '<serviceaccount_secret>'),
)
```
