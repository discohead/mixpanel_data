Mixpanel provides an event deduplication mechanism to ensure that duplicate events do not skew your analytics. Deduplication is essential when events may be sent multiple times due to network retries, client-side batching, or integration with multiple data sources.

<br />

## How Deduplication Works

Mixpanel deduplicates events using a combination of four key event properties:

- Event Name (`event`)
- Distinct ID (`distinct_id`)
- Timestamp (`time`)
- Insert ID (`$insert_id`)

If all four of these properties are identical across two or more events, Mixpanel considers them duplicates and will only show the most recent version of that event in your reports. This applies regardless of whether the events are sent via SDKs, APIs, or other integrations. 

The `$insert_id` should be a randomly generated, unique value for each event to ensure proper deduplication. If `$insert_id` are reused, events may be unintentionally deduplicated.

Only the four key event properties listed above are used for deduplication. Additional event properties are not considered for the deduplication mechanism. For example, if two events share the same Event Name, Distinct ID, Timestamp, and Insert ID, but have different $city value, they are still considered duplicate events.

### Deduplication Example

Deduplication occurs when a subset of the event data (event name, distinct_id, timestamp, $insert_id) is identical. Other event properties are not considered.

**Required [Event Object](doc:data-model#anatomy-of-an-event) attributes**

[block:parameters]
{
  "data": {
    "h-0": "Event Object property",
    "h-1": "Type",
    "h-2": "Description",
    "0-0": "**event**",
    "0-1": "<span style=\"font-family: courier\">String</span></br><span style=\"color: red\">required</span>",
    "0-2": "A name for the event. For example, \"Signed up\", or \"Uploaded Photo\".",
    "1-0": "**properties**",
    "1-1": "<span style=\"font-family: courier\">Object</span></br><span style=\"color: red\">required</span>",
    "1-2": "",
    "2-0": "**properties.distinct_id**",
    "2-1": "<span style=\"font-family: courier\">String</span></br><span style=\"color: red\">required</span>",
    "2-2": "The value of `distinct_id` will be treated as a string, and used to uniquely identify a user associated with your event. If you provide a distinct_id property with your events, you can track a given user through funnels and distinguish unique users for retention analyses. You should always send the same distinct_id when an event is triggered by the same user.",
    "3-0": "**properties.token**",
    "3-1": "<span style=\"font-family: courier\">String</span></br><span style=\"color: red\">required</span>",
    "3-2": "The Mixpanel token associated with your project. You can find your Mixpanel token in the project settings dialog in the Mixpanel app. Events without a valid token will be ignored.",
    "4-0": "**properties.time**",
    "4-1": "<span style=\"font-family: courier\">String</span></br><span style=\"color: red\">required</span>",
    "4-2": "The time an event occurred. If present, the value should be a unix timestamp (seconds since midnight, January 1st, 1970 - UTC). If this property is not included in your request, Mixpanel will use the time the event arrives at the server.",
    "5-0": "**properties.$insert_id**",
    "5-1": "<span style=\"font-family: courier\">String</span></br><span style=\"color: red\">required</span>",
    "5-2": "A unique UUID tied to exactly one occurrence of an event."
  },
  "cols": 3,
  "rows": 6,
  "align": [
    "left",
    "left",
    "left"
  ]
}
[/block]


In other words, each event containing an `$insert_id` is checked for duplication after being minimized to the following shape:

```json
{
  "event": "Item Purchased",
  "properties": {
    "token": "my_project_token",
    "distinct_id": "user123xyz",
    "time": 1601412131000,
    "$insert_id": "88B7hahbaschhhB66cbsg"
  },
}
```

If this minimized event object is an exact match to any other minimized event object, it is marked as a duplicate. Ingested events that have been marked as a duplicates will be deduplicated.

If an event is sent to the Ingestion API without an `$insert_id`, one will be generated for it. However, it will not qualify for the deduplication process.

## Deduplication Mechanisms

Mixpanel uses two main deduplication processes:

### Query-Time Deduplication

- When: Happens immediately when you query data in the Mixpanel UI.
- How: If multiple events share the same event_name, distinct_id, timestamp, and $insert_id. In most cases, only the more recent version of the event is shown in reports (based on the API ingestion time). Its important to note that Mixpanel does not guarantee upsert behavior however. 
- Scope: This deduplication is visible in the Mixpanel UI and reports, but not in raw data exports. Raw event export will contain all data as they were ingested, without any deduplication.

### Compaction-Time Deduplication

- When: Runs periodically in the backend, typically after a few hours and again after about 20 days, once data ingestion for a day is complete.
- How: During compaction, Mixpanel scans for events with the same event name, distinct_id, and $insert_id (timestamp does not need to match exactly, just the same calendar day).
- Scope: This process helps reduce storage of duplicate events and may affect event counts if duplicates were present with different timestamps

<br />

## Important Notes

**Raw Event Export** - Deduplication is not applied to raw data exports. If you export events via the API, you may see duplicates. It is recommended to apply the same deduplication logic (event name, distinct_id, timestamp, $insert_id) to your exported data

**Insert ID Best Practice** - Always generate a unique $insert_id for each event. Reusing $insert_id (e.g., setting it to the user’s distinct_id) can cause unintended deduplication and data loss

**Deduplication Timing** - Query-time deduplication is immediate. Compaction-time deduplication timing is not guaranteed and may take hours to days to complete.
