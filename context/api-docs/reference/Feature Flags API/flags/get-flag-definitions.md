---
title: Get Flag Definitions
category:
  uri: Feature Flags API
content:
  excerpt: >-
    This endpoint returns the flag definitions for all enabled feature flags
    within a Mixpanel project.
privacy:
  view: public
---

This endpoint returns a set of the flag definitions that are currently provisioned within a Mixpanel project and are enabled. This is used in local evaluation by Mixpanel service side SDK's such as the Python SDK. Local evaluation polls for flag definitions according to provided configuration and assignment to a variant is implemented directly by the SDK without making a network request.
