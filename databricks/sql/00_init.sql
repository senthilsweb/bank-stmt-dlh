-- Bootstrap for the __CATALOG__ lakehouse. Safe to run again.
-- Run:  make db-init     (or paste into a Databricks SQL editor)
-- The catalog itself is created once by hand: CREATE CATALOG __CATALOG__;

-- Layers
CREATE SCHEMA IF NOT EXISTS __CATALOG__.bronze COMMENT 'Raw statement files, never edited';
CREATE SCHEMA IF NOT EXISTS __CATALOG__.silver COMMENT 'Parsed and reconciled statements and transactions';
CREATE SCHEMA IF NOT EXISTS __CATALOG__.gold   COMMENT 'Categorized facts, reports and dashboard tables';

-- No landing volume: raw PDFs live only in the SharePoint statements folder (MinIO until decommissioned).
-- The job reads them from there and keeps no copy in Databricks.
