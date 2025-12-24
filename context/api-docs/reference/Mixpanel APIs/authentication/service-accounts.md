---
title: Service Accounts
category:
  uri: Mixpanel APIs
content:
  excerpt: ''
privacy:
  view: public
---
<Callout icon="👍" theme="okay">
  Recommended Authentication
</Callout>

A service account is a special type of Mixpanel user intended to represent a non-human entity such as a script or back end service. Similar to a normal user it can be granted access to any number of projects and workspaces within an organization. Permissions are set by defining the role of the service account for each project or workspace. A service account can only belong to one organization.

## Authenticating with a Service Account

Service Account authentication is performed via [HTTP Basic Auth](https://developer.mozilla.org/en-US/docs/Web/HTTP/Authentication#Basic_authentication_scheme). While the Basic access standard calls for a base64 encoding of the colon-joined credentials our authentication accepts both base64 encoding and plain-text.

Provide a service account's username and secret as the basic authentication credentials.

```curl cURL Basic Auth
curl https://mixpanel.com/api/app/me \
	--user "<serviceaccount_username>:<serviceaccount_secret>"
```
```shell cURL Header
curl https://mixpanel.com/api/app/me \
	--header 'authorization: Basic <serviceaccount_username>:<serviceaccount_secret>'
```
```python Python Requests
import requests
requests.get(
  'https://mixpanel.com/api/app/me', 
  auth=('<serviceaccount_username>', '<serviceaccount_secret>'),
)
```

## Managing Service Accounts

> 🚧 Owner or Admin Permissions Required
>
> You must have Owner or Admin permissions to manage a project's Service Accounts. Learn more in our [permissions help doc](https://mixpanelsupport.zendesk.com/hc/en-us/articles/360024613412).

<HTMLBlock>{`
<div class="mixpanel-custom-two-column">
	<div>
    <p>
      You can view and create service accounts in your organization in the Service Accounts tab in your <a href="https://mixpanel.com/settings/org#serviceaccounts">Organization settings</a>
    </p>
    <p>
      You will be asked to select the role and granted projects of the when creating a service account from the organization's settings page. Deleting a service account from the organization will immediately revoke access to all projects in the organization.
    </p>
  </div>
  <div class="image-container">
  	<img src="https://files.readme.io/a77f1df-org_settings.png"/>    
  </div>
</div>
<div class="mixpanel-custom-two-column">
  <div class="image-container">
  	<img src="https://files.readme.io/37798c5-25f47be-Screen_Shot_2020-07-14_at_4.30.49_PM.png"/>
  </div>
  <div>
    <p>
      You can also manage service accounts in your <a href="https://mixpanel.com/settings/project#serviceaccounts">project settings</a>.
    </p>
  </div>
</div>

<style>
	.mixpanel-custom-two-column {
    display: flex;
    margin: 18px 0;
	}
  
  .mixpanel-custom-two-column div {
  	width: 100%;
    margin: 15px 0;
  }
  
  .mixpanel-custom-two-column .image-container {
  	display: flex;
  }
  
  .mixpanel-custom-two-column .image-container img {
  	height: 300px;
  }
</style>
`}</HTMLBlock>

Any service account you create from the project settings page will be automatically be assigned an admin role. Deleting a service account will revoke access only from that project.

<HTMLBlock>{`
<div class="create-service-account">
  <img src="https://files.readme.io/bcc971b-4f76ee5-Screen_Shot_2020-07-29_at_1.57.16_PM.png"/>
</div>
  
<style>
	.create-service-account {
  	display: flex;
    margin: 18px 0;
  }
  
  .create-service-account img {
    width: 80%;
  }
  
  @media (max-width: 1400px) {
  	.create-service-account img {
      width: 100%;
    }
  }
</style>
`}</HTMLBlock>

> 🚧 Immediately store your credentials in a safe place
>
> It's very important you save your service account secret somewhere secure as you won't be able to access it again after creation.

## Service Account Expiration

By default, service accounts have no expiration. However, when you create a service account you can optionally specify how long you want it to be valid for. This may provide increased security and force a credential rotation policy. After the credentials expire, API requests using the service account will not be authorized.

<Image align="center" border={false} width="80%" src="https://files.readme.io/3668062-image_12.png" />
