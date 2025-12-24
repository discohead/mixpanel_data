---
title: Authentication
category:
  uri: Event Export API
content:
  excerpt: ''
privacy:
  view: public
---
## Service Account

[Service Account Authentication Details](ref:service-accounts)

Note that when you use Service Account authentication, you must specify the project\_id as a query parameter. E.g. `https://data.mixpanel.com/api/2.0/export?project_id=12345`

**Projects with[Classified Data](https://docs.mixpanel.com/docs/admin/data-governance/data-views-data-classification#data-classification)**

* The Service Account must have permission to access classified data.

## Project Secret

[Project Secret Authentication Details](ref:project-secret)
