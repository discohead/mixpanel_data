---
title: Overview
category:
  uri: GDPR API
content:
  excerpt: ''
privacy:
  view: public
---
## GDPR and CCPA API (v3)

The following retrieval and deletion API calls are updated for version 3 and are made for GDPR and CCPA compliance.

#### Create Retrieval

Request Type: **POST**\
Description: Creates a data retrieval job.\
Endpoint: `https://mixpanel.com/api/app/data-retrievals/v3.0/?token=<your_project_token>`\
Parameters:

| Parameter        | Parameter Type                    | Data Type              | Description                                                                                                                                                        |
| ---------------- | --------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Token            | URL. Passed in request URL.       | Query String Parameter | Your Mixpanel [project token](https://docs.mixpanel.com/docs/orgs-and-projects/managing-projects#find-your-project-tokens).                                        |
| distinct\_ids    | Body. Passed in JSON blob format. | Array of strings       | A list of distinct IDs associated with the users whose data you would like to export. You can add up to 2000 distinct IDs.                                         |
| compliance\_type | Body. Passed in JSON blob format. | String                 | Select CCPA or GDPR. Default is GDPR.                                                                                                                              |
| disclosure\_type | Body. Passed in JSON blob format. | String                 | Only required if compliance\_type = CCPA. Can be [Data, Categories, or Sources. Default is Data](https://docs.mixpanel.com/docs/privacy/end-user-data-management). |

Authorization:

| Authorization Type | Pass As                           | Description                                                                                                             |
| ------------------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Bearer             | Body. Passed in JSON blob format. | Your [OAuth token](https://docs.mixpanel.com/docs/privacy/end-user-data-management#generate-oauth-token) for GDPR APIs. |

Example Request:

```text
curl "https://mixpanel.com/api/app/data-retrievals/v3.0/?token=591b3354bb2bdd96f72f23bf56911673"
-H "Authorization: Bearer vZcErNw8JCq42BZUJyWoZmDWCKBxXc"
```

##### Rate Limit

We place a rate limit in place to ensure the integrity of our system as well as prevent a single project from monopolizing the available resources for other projects. Getting a 429 response code from our GDPR API means that you have reached our rate limit. We currently have a rate limit of 1 request per second for GDPR APIs. We also limit the maximum number of outstanding scans for a single project to approximately 5 years.

GDPR data retrieval process works by dividing the job of extracting the events by the granularity of the day, getting the events belonging to each distinct\_id in the request for each day going back to the first day for which we have events in Mixpanel. Since user activity can go back several years, this means that even a single data retrieval request might require scans of many hundred days.

To maximize the throughput of data retrievals, we recommend sending the maximum number of distinct IDs per request, now at 2000, and then retrying with exponential backoff. Depending on the amount of data that needs to be scanned, retrying for several hours might sometimes be necessary.

Example Return:\
`{"status":"ok","results":[{"status":"PENDING", "disclosure_type":"DATA", "date_requested":"2020-03-09T22:28:55.078315", "tracking_id":"1583792934719392965",  "project_id":1978118, "compliance_type":"ccpa", "destination_url":null, "requesting_user":"pat.davis@mixpanel.com", "distinct_id_count":1}]}`

#### Check Status of Retrieval

Request Type: GET

Description: Checks the status of a data retrieval job.

Endpoint: `https://mixpanel.com/api/app/data-retrievals/v3.0/<tracking_id>?token=<your_project_token>`

Return Format:\
`200 OK {
    "results": {
         "status":  oneOf [
                         "PENDING",
                         "STAGING",
                         "STARTED",
                         "SUCCESS",
                         "FAILURE",
                         "REVOKED",
                         "NOT_FOUND",
                         "UNKNOWN",
          ],
     }
}`

Return Key:

| Name       | Type   | Description                                                                                           |
| ---------- | ------ | ----------------------------------------------------------------------------------------------------- |
| PENDING    | String | Task ID returned from POST.                                                                           |
| STAGING    | String | The staging process of the retrieval task has started. The task can still be canceled during staging. |
| STARTED    | String | The retrieval task has started, and cannot be canceled.                                               |
| SUCCESS    | String | The retrieval task is complete.                                                                       |
| FAILURE    | String | The retrieval task has failed. Check the original task input parameters and create a new task.        |
| REVOKED    | String | The retrieval task has been canceled through a DELETE operation.                                      |
| NOT\_FOUND | String | The retrieval task cannot be found.                                                                   |
| UNKNOWN    | String | An error occurred while locating the retrieval task.                                                  |

Parameters:

| Parameter | Parameter Type              | Type                   | Description                                                                                                                 |
| --------- | --------------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Token     | URL. Passed in request URL. | Query String Parameter | Your Mixpanel [project token](https://docs.mixpanel.com/docs/orgs-and-projects/managing-projects#find-your-project-tokens). |
| Task ID   | URL. Passed in request URL. | Query String Parameter | The tracking ID shown in the response.                                                                                      |

Authorization:

| Authorization Type | Pass As                           | Description                                                                                                             |
| ------------------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Bearer             | Body. Passed in JSON blob format. | Your [OAuth token](https://docs.mixpanel.com/docs/privacy/end-user-data-management#generate-oauth-token) for GDPR APIs. |

Example Request:\
`curl "https://mixpanel.com/api/app/data-retrievals/v3.0/1583958896131033662/?token=591b3354bb2bdd96f72f23bf56911673"
-H "Authorization: Bearer vZcErNw8JCq42BZUJyWoZmDWCKBxXc"`

Example Return:\
`{"status": "ok", "results": {"status": "PENDING", "result": "", "distinct_ids": ["1"]}}`

#### Create a Deletion Task

Request Type: POST

Description: Creates a task that specifies a list of users in a particular project to delete. This will schedule a deletion job that will delete all data, including events and user profile data, for the users specified by distinct\_ids. This deletion job may be canceled until it reaches the STARTED stage. It may take up to 30 days to complete a deletion task in a customer’s Mixpanel database. Mixpanel may retain records of deletion tasks for legal compliance purposes or for a short time based on our legitimate interest in providing a service continuity.

Endpoint: `https://mixpanel.com/api/app/data-deletions/v3.0/?token=<your_project_token>`

Parameters:

| Parameter        | Parameter Type                    | Type                   | Description                                                                                                                 |
| ---------------- | --------------------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Token            | URL. Passed in request URL.       | Query String Parameter | Your Mixpanel [project token](https://docs.mixpanel.com/docs/orgs-and-projects/managing-projects#find-your-project-tokens). |
| distinct\_ids    | Body. Passed in JSON blob format. | Array of strings       | A list of distinct IDs associated with the users whose data you would like to export. You can add up to 1999 distinct IDs.  |
| compliance\_type | Body. Passed in JSON blob format. | String                 | Select CCPA or GDPR. Default is GDPR.                                                                                       |

Authorization:

| Authorization Type | Pass As                           | Description                                                                                                             |
| ------------------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Bearer             | Body. Passed in JSON blob format. | Your [OAuth token](https://docs.mixpanel.com/docs/privacy/end-user-data-management#generate-oauth-token) for GDPR APIs. |

Example Request:\
`curl "https://mixpanel.com/api/app/data-deletions/v3.0/?token=591b3354bb2bdd96f72f23bf56911673"
-H "Authorization: Bearer vZcErNw8JCq42BZUJyWoZmDWCKBxXc" -d '{"compliance_type":"CCPA", "distinct_ids":["1"]}'`

Example Return:\
`{"status":"ok","results":[{"status":"PENDING", "disclosure_type":"DATA", "date_requested":"2020-03-09T22:28:55.078315", "tracking_id":"1583792934719392965",  "project_id":1978118, "compliance_type":"ccpa", "destination_url":null, "requesting_user":"pat.davis@mixpanel.com", "distinct_id_count":1}]}`

#### Check Status of a Deletion Task

Request Type: **GET**

Description: Checks the status of an existing deletion task.

Endpoint: `https://mixpanel.com/api/app/data-deletions/v3.0/<tracking_id>?token=<your_project_token>`

Return Format:\
` "results": {
         "status":
//You will get one of the following returns
oneOf [
                         "PENDING",
                         "STAGING",
                         "STARTED",
                         "SUCCESS",
                         "FAILURE",
                         "REVOKED",
                         "NOT_FOUND",
                         "UNKNOWN",
          ],
     }
}`

Return Key:

| Name       | Type   | Description                                                                                          |
| ---------- | ------ | ---------------------------------------------------------------------------------------------------- |
| PENDING    | String | Task ID returned from POST.                                                                          |
| STAGING    | String | The staging process of the deletion task has started. The task can still be canceled during staging. |
| STARTED    | String | The deletion task has started, and cannot be canceled.                                               |
| SUCCESS    | String | The deletion task is complete.                                                                       |
| FAILURE    | String | The deletion task has failed. Check the original task input parameters and create a new task.        |
| REVOKED    | String | The deletion task has been canceled through a DELETE operation.                                      |
| NOT\_FOUND | String | The deletion task cannot be found.                                                                   |
| UNKNOWN    | String | An error occurred while locating the deletion task.                                                  |

Parameters:

| Parameter | Parameter Type              | Type                   | Description                                                                                                                 |
| --------- | --------------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Token     | URL. Passed in request URL. | Query String Parameter | Your Mixpanel [project token](https://docs.mixpanel.com/docs/orgs-and-projects/managing-projects#find-your-project-tokens). |
| Task ID   | URL. Passed in request URL. | Query String Parameter | The tracking ID shown in the response.                                                                                      |

Authorization:

| Authorization Type | Pass As                           | Description                                                                                                             |
| ------------------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Bearer             | Body. Passed in JSON blob format. | Your [OAuth token](https://docs.mixpanel.com/docs/privacy/end-user-data-management#generate-oauth-token) for GDPR APIs. |

Example Request:\
`curl "https://mixpanel.com/api/app/data-deletions/v3.0/35bd8477-f71f-4088-af55-c88a6fb4ad4b/?token=591b3354bb2bdd96f72f23bf56911674" -H "Authorization: Bearer vZcErNw8JCq42BZUJyWoZmDWCKBxXc"`

Example Return:\
`{"status": "ok", "results": {"status": "PENDING", "result": "", "distinct_ids": ["1"]}}`

#### Cancel Deletion

Request Type: **DELETE**

Description: Cancels an existing deletion task. Deletion jobs can be canceled until the STARTED stage initiates.

Endpoint: `https://mixpanel.com/api/app/data-deletions/v3.0/?token=<your_project_token>`

Return Format: `204 NoContent` or `405 MethodNotAllowed`

Return Key:

| Name                 | Type                              | Description                                                                                                                 |
| -------------------- | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 204 NoContent        | Query String Parameter `required` | Your Mixpanel [project token](https://docs.mixpanel.com/docs/orgs-and-projects/managing-projects#find-your-project-tokens). |
| 405 MethodNotAllowed | Query String Parameter `required` | Task ID returned from POST.                                                                                                 |

Parameters:

| Parameter     | Parameter Type                    | Type                   | Description                                                                                                                 |
| ------------- | --------------------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Token         | URL. Passed in request URL.       | Query String Parameter | Your Mixpanel [project token](https://docs.mixpanel.com/docs/orgs-and-projects/managing-projects#find-your-project-tokens). |
| distinct\_ids | Body. Passed in JSON blob format. | Array of strings       | A list of distinct IDs associated with the users whose data you would like to export. You can add up to 1999 distinct IDs.  |

Authorization:

| Authorization Type | Pass As                           | Description                                                                                                             |
| ------------------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Bearer             | Body. Passed in JSON blob format. | Your [OAuth token](https://docs.mixpanel.com/docs/privacy/end-user-data-management#generate-oauth-token) for GDPR APIs. |

Example Request:\
`curl "https://mixpanel.com/api/app/data-deletions/v3.0/?token=591b3354bb2bdd96f72f23bf56911673"
-H "Authorization: Bearer vZcErNw8JCq42BZUJyWoZmDWCKBxXc" -d '{"distinct_ids":["1"]}'`

Example Return:\
`{"status": "ok", "results": {"task_id": "35bd8477-f71f-4088-af55-c88a6fb4ad4a"}}`
