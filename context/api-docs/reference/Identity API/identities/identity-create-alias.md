---
title: Create Alias
category:
  uri: Identity API
content:
  excerpt: ''
privacy:
  view: public
---
<Callout icon="📘" theme="info">
  The `$create_alias` event payload is only useful for projects using the Original ID Merge system and the Legacy ID Management System; it has no functionality in the Simplified ID Merge system. Please review [this section of our documentation](https://docs.mixpanel.com/docs/tracking-methods/id-management#identity-merge-apis) for more information.
</Callout>

<Callout icon="📘" theme="info">
  You can also use the import endpoint: [https://api.mixpanel.com/import/](https://api.mixpanel.com/import/)
</Callout>

Mixpanel supports adding an alias to a distinct id. An alias is a new value that will be interpreted by Mixpanel as an existing value. That means that you can send messages to Mixpanel using the new value, and Mixpanel will continue to use the old value for calculating funnels and retention reports, or applying updates to user profiles.

**Alias Criteria:**

<Image alt="960" border={false} src="https://files.readme.io/d16f1d3-ID_management_alias_3-HTTP.png" title="Identity Management - Alias" />

**Required[Event Object](https://docs.mixpanel.com/docs/tracking/reference/data-model#anatomy-of-an-event) attributes**

<table>
  <thead>
    <tr>
      <th>Event Object property</th>
      <th>Type</th>
      <th>Description</th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>**event**</td>

      <td>
        <span style={{ fontFamily: "courier" }}>String</span><br /><span style={{ color: "red" }}>required</span>
      </td>

      <td>value must be: <br />`$create_alias`</td>
    </tr>

    <tr>
      <td>**properties**</td>

      <td>
        <span style={{ fontFamily: "courier" }}>Object</span><br /><span style={{ color: "red" }}>required</span>
      </td>

      <td />
    </tr>

    <tr>
      <td>**properties.distinct\_id**</td>

      <td>
        <span style={{ fontFamily: "courier" }}>String</span><br /><span style={{ color: "red" }}>required</span>
      </td>

      <td>A distinct\_id to be merged with the alias.</td>
    </tr>

    <tr>
      <td>**properties.alias**</td>

      <td>
        <span style={{ fontFamily: "courier" }}>String</span><br /><span style={{ color: "red" }}>required</span>
      </td>

      <td>A new distinct\_id to be merged with the original distinct\_id. Each alias can only map to one distinct\_id.</td>
    </tr>

    <tr>
      <td>**properties.token**</td>

      <td>
        <span style={{ fontFamily: "courier" }}>String</span><br /><span style={{ color: "red" }}>required</span>
      </td>

      <td>The project token.</td>
    </tr>
  </tbody>
</table>
