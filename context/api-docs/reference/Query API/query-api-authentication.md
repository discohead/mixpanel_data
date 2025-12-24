---
title: Authentication
category:
  uri: Query API
content:
  excerpt: ''
privacy:
  view: public
---
## Service Account

[Service Account Authentication Details](ref:service-accounts)

<Callout icon="👍" theme="okay">
  This is the preferred authentication method for Query API.
</Callout>

* Requests parameters must include a `project_id`.

**Projects with[Data Views](https://help.mixpanel.com/hc/en-us/articles/360043782572-Data-Views)**

* In addition to `project_id`, you should include the global data view's `workspace_id` as a request parameter.

**Projects with[Classified Data](https://help.mixpanel.com/hc/en-us/articles/360044295131-Data-Classification)**

* Your results may be filtered based on the Service Account's sensitivity settings.

## Project Secret

[Project Secret Authentication Details](ref:project-secret)

<Callout icon="❗️" theme="error">
  Please migrate existing integrations to use Service Account authentication

  Project Secret authentication is in the process of being deprecated. This authentication method does not currently have an EOL date.
</Callout>
