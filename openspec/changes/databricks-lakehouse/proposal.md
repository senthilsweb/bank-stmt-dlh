# Proposal: databricks-lakehouse — move the bank ETL to a Databricks lakehouse

> Status: **APPROVED** (2026-10-18). Secrets live in a Databricks secret scope, not in code or the bundle.
> Owner: the repo owner.
> Builds on: the local pipeline (pdfplumber, DuckDB, Parquet) already in `src/`.

## Why

The local pipeline works: 10 statements, 282 transactions, every statement
reconciles to the bank's own totals. But it runs by hand, on one laptop, and the
dashboard built from it is a one-off snapshot.

The owner wants:

- a lakehouse (bronze, silver, gold) in a **new Databricks catalog**, with raw
  statements in the home-lab **MinIO**;
- reports and the dashboard **inside Databricks**, fully **deterministic**;
- the ETL to run **when a new statement is dropped**, or on a schedule;
- LLM or Jev **only where a rule cannot decide**.

## What changes

- New catalog (working name `bank_stmt_dlh`) with schemas `bronze`, `silver`, `gold`.
- The existing deterministic parser and reconciliation move into a Databricks Job
  as plain Python. `ai_parse_document` is **not** the primary parser: the PDFs are
  text-based, the code parser is exact and free, and reconciliation proves it.
  `ai_parse_document` is used only as a fallback for a file that fails
  reconciliation, and its output goes through the same reconciliation.
- Bronze loads each PDF once (keyed by SHA-256). Silver holds statements and
  transactions. Gold holds the categorized fact table, recurring payments,
  monthly summary and the review queue.
- Categorization stays rules and payee map first. The payee map, rules and
  categories become **tables** seeded from the YAML in git. Jev labels only the
  leftovers and every label is stored, so no row is asked twice.
- An **AI/BI dashboard** reads gold tables with SQL only.
- A **Databricks Asset Bundle** (`databricks.yml`) deploys the job, schemas and
  dashboard, so the whole thing is reproducible from git.
- **MinIO is the single home of the raw PDFs.** Databricks reads them from MinIO
  and keeps no copy. The job runs once a day at midnight IST and right after `make upload`
  (a run-now call). A file-arrival trigger is not used: it only watches Unity
  Catalog storage, and Free Edition cannot map MinIO into it.
- The local DuckDB path stays as the dev and test path, using the same Python
  functions.

## Out of scope

Other banks and accounts, real-time ingestion, ML forecasting, any change to the
category or payee decisions already made.

## Acceptance criteria

1. Running the job on the 10 existing statements gives the same result as the
   local pipeline: 282 transactions, 10 of 10 reconciled, identical totals per
   month and per category.
2. A new statement PDF dropped in MinIO is processed by the next scheduled run
   (by the next midnight run), or at once via `make upload`, and only that file is
   processed. Dropping the same file again changes nothing.
3. A statement that does not reconcile is quarantined, never loaded to silver or
   gold, and the job reports it.
4. Gold and the dashboard contain no AI output except Jev labels that passed the
   confidence gate and are marked `category_source = 'jev'`.
5. No PDF password, API key or counterparty text appears in job logs.
6. `databricks bundle deploy` recreates the job and dashboard from a clean state.

## Risks and open questions

See `design.md`. The largest: Free Edition serverless compute may not allow
outbound calls to MinIO or installing `pdfplumber`. Both are tested first (bolt
B0). MinIO is exposed to the internet, so its key must be limited to one bucket.
