# Design — sharepoint-source

## Reader contract (unchanged for the notebook)

| Function | Returns |
|---|---|
| `list_pdfs(cfg)` | `[{object_key, etag, size_bytes}]`. `object_key` = path under the library root (e.g. `Bank Statements/HDFC-Current/06-2026-bank-stmt(jun).pdf`); `etag` = Graph `eTag` |
| `download(cfg, item, dest)` | writes to `dest`, returns SHA-256 |

Flow: token (POST `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`, scope
`https://graph.microsoft.com/.default`) -> `GET /drives/{drive_id}/root:/{folder}:/children` (follow
`@odata.nextLink`) -> per file `GET /drives/{drive_id}/items/{id}/content` (302 to a short-lived download URL).
Only `.pdf` files; each configured folder is read including sub-folders. Token cached for the run. Retry on 429/5xx, `Retry-After` honoured.
The app holds only `Files.SelectedOperations.Selected`, so it **cannot look up sites or paths**. The reader therefore uses ids fixed in config: `drive_id` and the folder `item_id` (`GET /drives/{drive_id}/items/{item_id}/children`), found once by the admin in Graph Explorer (setup step 4).

## Ingest change

Today a file is new if `(object_key, etag)` is unknown. SharePoint changes both for existing files, so:

1. Candidates = listed files whose `(object_key, etag)` is unknown.
2. Download each candidate, compute SHA-256.
3. SHA-256 already in `bronze.statement_files` -> **not parsed**; insert the new `(object_key, etag, source)` row only.
4. Otherwise parse and reconcile as today.

Add column `source STRING` to `bronze.statement_files` (`ALTER TABLE ... ADD COLUMN`, idempotent in the notebook).
Cost of step 2 on cutover: 10 small downloads, once.

## Config

`config/settings.yaml`:
```yaml
statement_source: sharepoint        # minio | sharepoint (minio kept for rollback until decommission)
sharepoint:
  site_host: <tenant>.sharepoint.com
  site_path: ""                     # root site (the folder is on https://<tenant>.sharepoint.com itself)
  library: Shared Documents         # the "Documents" library
  folders:                          # one folder per year; add OPS2027 when it starts
    - <path to the statements folder>/01 MONTHLY STATEMENTS   # weekly statements are skipped for now
```
Secrets (scope `bank-stmt-dlh`): `sp_tenant_id`, `sp_client_id`, `sp_client_secret`. `.env.sample` gets `SP_DRIVE_ID`, `SP_FOLDER_ID`, `SP_TENANT_ID`, `SP_CLIENT_ID`, `SP_CLIENT_SECRET`; the non-secret values (`SP_SITE_HOST`, `SP_SITE_PATH`, `SP_LIBRARY`, `SP_FOLDER`) are already in the local `.env`.

## SharePoint and Entra setup (one time)

Where the statements are (found from the share link): site = root `https://<tenant>.sharepoint.com`, library
`Shared Documents`, folder `<path to the statements folder>` (one `OPSyyyy` folder per year), which holds two sub-folders:
`01 MONTHLY STATEMENTS` and `02 WEEKLY STATEMENTS`. **Weekly statements are out of scope for now:** the grant is on the year folder (the app can technically see both), but the job reads only `SP_MONTHLY_FOLDER_ID`.

**Scope problem.** The folder sits in the root site, next to other operations documents. `Sites.Selected` would
give the app read on the *whole site*. Use the folder-level permission instead:
`Files.SelectedOperations.Selected` (Graph, Application) plus a `read` grant on that one folder.
If it turns out not to work in this tenant, fall back to a dedicated site (`Sites.Selected`) and move the statements there.

1. **App registration.** Entra admin center -> App registrations -> New: `bank-stmt-dlh-reader`, single tenant, no redirect URI. Note *Tenant ID* and *Client ID* (-> `.env`).
2. **Secret.** Certificates & secrets -> New client secret (12 months). Copy the *Value* at once into `.env` (`SP_CLIENT_SECRET`). Never paste it in chat or git.
3. **Permission.** API permissions -> Add -> Microsoft Graph -> *Application* permissions -> `Files.SelectedOperations.Selected` -> **Grant admin consent**.
4. **Find the ids** (Graph Explorer, signed in as admin; consent to `Sites.Read.All` / `Files.Read.All` when asked):
   - `GET /v1.0/sites/<tenant>.sharepoint.com` -> site `id`
   - `GET /v1.0/sites/{site-id}/drives` -> the drive named `Documents` -> `drive-id`
   - `GET /v1.0/drives/{drive-id}/root:/<path to the statements folder>/01 MONTHLY STATEMENTS` -> folder `id` (`item-id`)
5. **Grant the app that one folder** (admin, one time):
   `POST /v1.0/drives/{drive-id}/items/{item-id}/permissions` body
   `{"roles":["read"],"grantedTo":{"application":{"id":"<client-id>","displayName":"bank-stmt-dlh-reader"}}}`
   (needs `Files.ReadWrite.All` consent in Graph Explorer for this call). Next year, repeat for the `OPS2027` monthly folder.
6. **Check** (bolt S0 script): token OK, list shows the 10 PDFs, a download works, a file outside the folder returns 403.
7. **Secrets to Databricks:** `sp_*` into scope `bank-stmt-dlh` (script, values from `.env`).

Alternative if admin consent is a problem: delegated sign-in (device code) with a refresh token. Not recommended: tokens expire, a person's account becomes a job dependency.

## Decision: if Databricks cannot reach Microsoft

S0 decides. Fallbacks in order: (a) run only the *fetch* step outside Databricks (a small scheduled
GitHub Action or laptop job that lists SharePoint and triggers `run-now`) — but then Databricks has no
way to read the file without a copy, which breaks "no copy in Databricks"; (b) keep MinIO and sync
SharePoint -> MinIO. Both need a new proposal; do not decide now.

## Weekly statements (deferred)

Not in this change. When added later, weekly files overlap the monthly ones. This is already safe: `txn_id` is built from date, reference, amount and
narration (not from the file), so the same transaction in a weekly and a monthly file merges to one row, and
`monthly_summary` takes the statement with the latest `period_to` per month. Open points for the first run:
the weekly PDF layout may differ (the parser then quarantines it, which is the designed outcome), and the
opening/closing balances of a weekly file must still reconcile to its own summary.

## Rollback

Set `statement_source: minio`, redeploy. MinIO stays untouched until the cutover is confirmed.
