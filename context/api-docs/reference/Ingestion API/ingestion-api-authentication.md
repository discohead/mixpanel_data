---
title: Authentication
category:
  uri: Ingestion API
content:
  excerpt: ''
privacy:
  view: public
---
Most of our Ingestion API calls such as [Import Events](ref:import-events), [Track Events](ref:track-event), [User Profiles](ref:user-profiles), and [Group Profiles](ref:group-profiles) only require a [Project Token](ref:project-token). Because these APIs are often called from our client-side SDKs, we do not want to expose credentials, but we do need to know which project to send data to so we use the Project Token for that purpose. However, a few of the more powerful APIs such as [Lookup Tables](ref:lookup-tables) **do require authentication**. For these, it's recommended to use a [Service Account](ref:service-account). We also have legacy support for [Project Secret](ref:project-secret) but suggest any new integrations use a Service Account.
