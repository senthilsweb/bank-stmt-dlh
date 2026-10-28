# Spec delta: ingestion — SharePoint as the source

## MODIFIED Requirements

### Requirement: SharePoint is the only home of raw files

Raw statement PDFs SHALL be stored in one SharePoint document-library folder only. The pipeline SHALL
read them through Microsoft Graph and SHALL NOT store a copy in a Databricks volume, table or workspace file.
(Replaces "MinIO is the only home of raw files".)

#### Scenario: SharePoint or Graph unreachable
- **WHEN** the token call or the folder listing fails after retries
- **THEN** no table changes, the run fails with the reason, and the next run retries

### Requirement: Each file is ingested once

A statement PDF SHALL be identified by its SHA-256. A file whose SHA-256 is already in `bronze.statement_files`
SHALL NOT be parsed or loaded again, whatever its location or etag. A changed location or etag SHALL only add a row.

#### Scenario: Cutover from MinIO
- **WHEN** the 10 loaded statements are listed from SharePoint with new etags
- **THEN** none is parsed, 10 rows with `source = 'sharepoint'` are added, silver and gold are unchanged

## ADDED Requirements

### Requirement: Read-only, folder-scoped access

The Entra app SHALL hold `Files.SelectedOperations.Selected` (or `Sites.Selected` on a dedicated statements site) with a `read` grant on the statements folder only. It SHALL NOT
hold any write permission or any tenant-wide Sites or Files permission.

#### Scenario: Another folder
- **WHEN** the app token is used on any file outside the granted folder
- **THEN** Graph answers 403

### Requirement: Graph credentials live in the secret scope

`sp_tenant_id`, `sp_client_id` and `sp_client_secret` SHALL be read from secret scope `bank-stmt-dlh` and
SHALL NOT appear in git, logs, tables or notebook output.

### Requirement: Source is switchable

`statement_source` SHALL select `minio` or `sharepoint` without code change, until MinIO is decommissioned.
