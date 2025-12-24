# App API - Data Definitions
Used to populate the lexicon application

## Version: 1.0.0

**Contact information:**  
https://mixpanel.com/get-support  

### /projects/{projectId}/events/{eventName}/history

#### GET
##### Summary:

Event Definition History

##### Description:

Get all History for an Event Definition

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
|  |  |  | No | [projectId](#projectid) |
| eventName | path | The name of the event definition | Yes | string |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Success |
| 401 |  |
| 403 |  |

### /projects/{projectId}/properties/{propertyName}/history

#### GET
##### Summary:

Event Definition History

##### Description:

Get all History for an Event Definition

##### Parameters

| Name | Located in | Description | Required | Schema |
| ---- | ---------- | ----------- | -------- | ---- |
|  |  |  | No | [projectId](#projectid) |
| propertyName | path | The name of the property definition | Yes | string |
| entity_type | query | The type of entity it is tied to | Yes | string |

##### Responses

| Code | Description |
| ---- | ----------- |
| 200 | Success |
| 401 |  |
| 403 |  |

### Models


#### UserDetails

Information about the user who made a change

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| name | string | The user's full name | No |
| id | number | The id of the user entry in app db | No |
| email | string | The user's email address | No |

#### HistoryEntry

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| HistoryEntry |  |  |  |

#### HistoryResponse

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| results | [ [HistoryEntry](#historyentry) ] |  | No |
| status | string |  | No |

#### ErrorResponse

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| error | string | Details about the error that occurred | No |
| status | string |  | No |