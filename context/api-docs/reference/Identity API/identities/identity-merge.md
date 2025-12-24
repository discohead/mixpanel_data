---
title: Merge Identities
category:
  uri: Identity API
content:
  excerpt: ''
privacy:
  view: public
---
<Callout icon="📘" theme="info">
  The `$merge` event payload is only useful for projects using the Original ID Merge system; it has no functionality in other ID management systems. Please review [this section of our documentation](https://docs.mixpanel.com/docs/tracking-methods/id-management#identity-merge-apis) for more information.
</Callout>

<Callout icon="❗️" theme="error">
  Merging identities is irreversible

  `$merge` is a very powerful tool, so we will only accept `$merge` events that are sent via `https://api.mixpanel.com/import`, which is protected by the project api secret. You **cannot** unmerge `distinct_id`.
</Callout>

**Merge Criteria:**

<Image alt="960" border={false} src="https://files.readme.io/be66940-merge_.png" title="Identity Management - Merge" />
