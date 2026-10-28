# Cookbook: SharePoint statement source (one-time setup)

Goal: let the Databricks job read the monthly statement PDFs from one SharePoint folder, read-only,
with an Entra app, and nothing else in the tenant. Needs a Microsoft 365 / Entra admin.
Design and reasons: `openspec/changes/sharepoint-source/design.md`.

| Item | Value (non-secret) |
|---|---|
| SharePoint host | `<tenant>.sharepoint.com` (root site, no `/sites/...` part) |
| Library | `Shared Documents` |
| Folder | Grant on `<path to the statements folder>` (covers both sub-folders); the job reads only `01 MONTHLY STATEMENTS`, weekly skipped for now |
| Entra app | `bank-stmt-dlh-reader`, single tenant, no redirect URI |
| Permission | Microsoft Graph, Application, `Files.SelectedOperations.Selected` + read grant on the folder |

Why a folder-level grant: the folder lives in the root site next to other operations documents.
`Sites.Selected` would expose the whole site.

## 1. Create the app
1. https://entra.microsoft.com -> Entra ID -> App registrations -> **New registration**.
2. Name `bank-stmt-dlh-reader`; account type *Single tenant*; no redirect URI; **Register**.
3. On Overview copy **Application (client) ID** and **Directory (tenant) ID**.

## 2. Create the client secret
1. Manage -> Certificates & secrets -> Client secrets -> **New client secret** (12 or 24 months).
2. Copy the **Value** at once (not the Secret ID). It is shown only once.
3. Calendar reminder 30 days before expiry; the job fails when it expires.

## 3. Add the permission
1. Manage -> API permissions -> Add a permission -> Microsoft Graph -> **Application permissions**.
2. Add `Files.SelectedOperations.Selected`, then **Grant admin consent**. Status must show a green tick.

## 4. Fill `.env` (gitignored; never paste secrets in chat or git)
```
SP_TENANT_ID=<Directory (tenant) ID>
SP_CLIENT_ID=<Application (client) ID>
SP_CLIENT_SECRET=<secret Value>
SP_SITE_HOST=<tenant>.sharepoint.com
SP_SITE_PATH=
SP_LIBRARY=Shared Documents
SP_FOLDER=<path to the statements folder>
SP_SITE_ID=<from step 5.1, reference only>
SP_DRIVE_ID=<from step 5.2>
SP_FOLDER_ID=<from step 5.3, the year folder that holds the grant>
SP_MONTHLY_FOLDER_ID=<child '01 MONTHLY STATEMENTS' of the year folder; the job reads this one>
SP_WEEKLY_FOLDER_ID=<child '02 WEEKLY STATEMENTS'; not read for now>
```
The app can only read the granted folder, so it cannot look up sites or paths. The job uses `SP_DRIVE_ID` and
`SP_FOLDER_ID` directly. They are not secret.
No quotes, no spaces around `=`. Save the file.

## 5. Grant the app read on the folder (admin, one time)
The Entra permission alone gives no access: the app sees nothing until a folder is granted to it. Do this in
Graph Explorer (https://developer.microsoft.com/graph/graph-explorer), signed in as the **tenant admin**
(check the profile icon; not a personal account).

**5.0 Consent once (your own sign-in, not the app).** Tab *Modify permissions* -> **Consent** for
`Sites.Read.All` and `Files.Read.All`. Without it you get `accessDenied: Request Doesn't have the required Permission scopes to access a site`.
Before the final POST also consent to `Files.ReadWrite.All`.

**5.1 Site id.** `GET https://graph.microsoft.com/v1.0/sites/<tenant>.sharepoint.com`
-> `id` (looks like `<tenant>.sharepoint.com,<guid>,<guid>`, with commas) -> `SP_SITE_ID`.

**5.2 Drive id.** `GET https://graph.microsoft.com/v1.0/sites/{site-id}/drives`
-> the entry named **Documents** -> `id` (starts with `b!`) -> `SP_DRIVE_ID`.
Do not use `/sites/{site-id}/root:/path`; that is a Bad Request. Paths go through the drive.

**5.3 Year folder id.**
`GET https://graph.microsoft.com/v1.0/drives/{drive-id}/root:/<path to the statements folder>`
-> `id` (starts with `01`) -> `SP_FOLDER_ID`. A 404 means a folder name differs; list the parent with
`.../root:/<parent folder>:/children` and compare names. Replace spaces with `%20` if needed.

**5.4 Grant.** Method **POST**, URL
`https://graph.microsoft.com/v1.0/drives/{drive-id}/items/{folder-id}/permissions`,
and the JSON in the **Request body** tab (under the URL bar; a blank tab gives `Empty Payload. JSON content expected`):
```json
{"roles":["read"],"grantedTo":{"application":{"id":"<SP_CLIENT_ID>","displayName":"bank-stmt-dlh-reader"}}}
```
Use `grantedTo`. The site-style `grantedToIdentities` is rejected on folders with `'grantedTo' must be provided`.
`id` is the app's **Application (client) ID**, not the object id or tenant id. Success is `201 Created` with
`"roles":["read"]` and the app name in the response. Allow a minute or two to take effect.

**5.5 Sub-folder ids.** The grant on the year folder covers its children. Read their ids:
`GET .../drives/{drive-id}/items/{folder-id}/children` -> `01 MONTHLY STATEMENTS` -> `SP_MONTHLY_FOLDER_ID`,
`02 WEEKLY STATEMENTS` -> `SP_WEEKLY_FOLDER_ID` (saved, not read for now). The job reads only the monthly folder.

**Check a grant:** `GET .../drives/{drive-id}/items/{folder-id}/permissions` lists `bank-stmt-dlh-reader` with role `read`.
**Revoke:** `DELETE .../items/{folder-id}/permissions/{permission-id}` (the `id` from that list).
**Each new year:** repeat 5.3-5.5 for the new `OPSyyyy` year folder and add its ids.

## 6. Check
Bolt S0 (`scripts/sharepoint_check.py`): token OK; folder lists the 10 PDFs; one downloads; a file outside
the folder returns 403. Expected token roles: `Files.SelectedOperations.Selected` only.

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| `AADSTS7000215` invalid client secret | Copied the Secret ID instead of the Value, or it expired. Make a new secret |
| `AADSTS700016` app not found | Wrong tenant or client ID |
| 403 on the folder | Step 5.4 not done, or done on a different folder id than `SP_FOLDER_ID` |
| `accessDenied ... required Permission scopes to access a site` | Graph Explorer consent missing (5.0) |
| `Empty Payload` | Request body tab was blank (5.4) |
| `'grantedTo' must be provided` | Used `grantedToIdentities`; use `grantedTo` (5.4) |
| Bad Request on `/sites/{id}/root:/...` | Wrong shape; use `/drives/{drive-id}/root:/...` (5.2-5.3) |
| Permission not in the list | Choose *Application*, not *Delegated*; else fall back to a dedicated site + `Sites.Selected` |
| Token has no `roles` | Admin consent not granted |

Verified 2026-10-24: token role `Files.SelectedOperations.Selected`; year folder lists 10 monthly + 9 weekly PDFs; one PDF downloads (HTTP 200, `%PDF-`); drive root lists nothing and paths above the year folder return 404. Note: the grant body field is `grantedTo` (`grantedToIdentities` is rejected on folders).
