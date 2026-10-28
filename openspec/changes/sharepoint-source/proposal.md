# Proposal: sharepoint-source — read statements from a SharePoint folder instead of MinIO

> Status: **APPROVED** (2026-10-24, built S0-S3, parity passed). Change request on top of `databricks-lakehouse`.
> Owner: the repo owner.

## Why

MinIO runs in the home lab, behind Cloudflare, with a root key on a public endpoint
and one transient 403 already seen. Statements are ConceptLabs company records, so they
should live where the company already keeps its files, with Microsoft 365 access
control, versioning and audit, and where anyone with access can drop a file from a
browser.

## What changes

- **SharePoint document-library folder replaces MinIO** as the single home of the raw PDFs.
  Databricks still keeps no copy: each file is downloaded to temp disk, parsed, deleted.
- A new reader `src/sharepoint_reader.py` calls Microsoft Graph with an Entra app
  (client credentials). It has the same two functions as today's reader: list PDFs, download one.
- The app gets **read-only access to one folder only** (`Files.SelectedOperations.Selected` plus a per-folder `read` grant), because the statements sit in the root site beside other operations documents.
- Credentials move to the `bank-etl` secret scope: `sp_tenant_id`, `sp_client_id`,
  `sp_client_secret`. Site, library and the per-year folders (`<path to the statements folder>`) are plain settings in `config/settings.yaml`.
- A setting `statement_source: minio | sharepoint` lets the parity run and a rollback use either source.
- Ingest dedups by **SHA-256 first**, so the 10 files already loaded are not parsed again
  just because their location and etag changed.
- `make upload` (MinIO write) goes away. People drop files in SharePoint; `make run` starts the job
  on demand; the midnight IST schedule is unchanged.
- MinIO is decommissioned after parity: secrets removed, bucket kept read-only for a month, then deleted.

## Out of scope

Writing to SharePoint from code, other banks, change of schedule, any change to parsing,
categories or the dashboard. The pending task "bucket-limited MinIO key" is cancelled by this change.

## Risks

| Risk | Handling |
|---|---|
| Free Edition serverless may block outbound calls to Microsoft domains | Bolt S0 tests `login.microsoftonline.com`, `graph.microsoft.com` and the SharePoint download host from a job before any code is written. If blocked: stop and rethink (see design) |
| Needs a tenant admin once (admin consent and the per-site grant) | Steps written in `design.md`; owner or admin does them once |
| Client secret expires (max 24 months) | Calendar reminder 30 days before; the job already emails on failure |
| Statements visible to too many people, or the app reading the whole root site | Folder-level grant, not site-level; fallback is a dedicated site |
| Graph throttling (HTTP 429) | Reader retries with backoff and honours `Retry-After` |

## Acceptance criteria

1. With `statement_source: sharepoint`, the job on the 10 existing statements reports
   0 files parsed, 10 re-registered by SHA-256, and silver/gold are unchanged (282 transactions).
2. A new PDF dropped in the folder is processed by the next run (or `make run`), and only that file.
   The same file dropped again changes nothing.
3. A file in the folder that does not reconcile is quarantined as today.
4. The app cannot read any other site (a Graph call to any file outside the granted folder returns 403).
5. No secret, token or file name appears in logs beyond the file names already printed today.
6. After cutover MinIO secrets are removed from the scope and `.env`.
