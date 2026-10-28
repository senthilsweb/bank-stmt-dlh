# Spec delta: ingestion — deterministic statement parsing

## ADDED Requirements

### Requirement: Each file is ingested once

A statement PDF in MinIO SHALL be identified by its object key and SHA-256. A file already in `bronze.statement_files` SHALL NOT be parsed or loaded again.

#### Scenario: Same file dropped twice
- **WHEN** a PDF with an existing hash is added to the MinIO bucket
- **THEN** no row in bronze, silver or gold changes

### Requirement: Parsing is code, not a model

The primary parser SHALL be deterministic Python. It SHALL read debit or credit from the running balance, not from column position.

### Requirement: A statement must reconcile before it is loaded

Debit count, credit count, debit total, credit total and closing balance parsed from the rows SHALL equal the bank's STATEMENT SUMMARY. A statement that does not SHALL be written to `silver.quarantine` with the reason and SHALL NOT reach silver or gold.

#### Scenario: Parser break
- **WHEN** one row is missed and the closing balance differs
- **THEN** the statement is quarantined and the job finishes with a warning that names the file

### Requirement: Model parsing is a fallback only

`ai_parse_document` MAY be used for a quarantined file. Its rows SHALL pass the same reconciliation, and rows that pass SHALL be marked `parser = 'ai_parse_document'`.

### Requirement: Secrets stay out of logs

The PDF password SHALL come from a secret scope and SHALL NOT appear in any log, table or file.

### Requirement: MinIO is the only home of raw files

Raw statement PDFs SHALL be stored in MinIO bucket `bank-etl` only. The pipeline SHALL read them from MinIO and SHALL NOT store a copy in a Databricks volume, table or workspace file.

#### Scenario: MinIO unreachable
- **WHEN** MinIO cannot be reached during discover
- **THEN** no table changes, the run reports the failure, and the next run retries
