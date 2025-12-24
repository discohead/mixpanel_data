---
title: Authentication
category:
  uri: Service Accounts API
content:
  excerpt: ''
privacy:
  view: public
---
## Service Account

<Callout icon="📘" theme="info">
  Roles & Permissions

  To modify (create, delete) a service account, the service account used for authentication must have the role of admin or owner.
</Callout>

[Service Account Authentication Details](ref:authentication#service-accounts)

```sh
curl --request GET \
     --url https://mixpanel.com/api/app/organizations/12345/service-accounts \
     --header 'Accept: application/json' \
     --header 'Authorization: Basic dGVzdDp0ZXN0'
```
