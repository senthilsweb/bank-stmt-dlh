# Databricks lakehouse

The same parser runs inside a scheduled Databricks job. Raw PDFs stay in your bucket; each one is downloaded to
temporary disk, parsed, reconciled and dropped. Nothing is kept in Databricks but the tables.

## What you need

- A Databricks workspace. Free Edition with serverless compute is enough.
- An S3-compatible bucket: MinIO, AWS S3, Cloudflare R2. Use a key limited to that bucket, not a root account.
- Optional: a Microsoft 365 tenant admin, once, if you want the SharePoint source or the weekly email.

## One-time setup

1. Fill the `DATABRICKS_*` and `MINIO_*` values in `.env`. In `config/settings.yaml` set `statement_source: minio`,
   `minio_bucket` and `catalog`.
2. Create the catalog by hand in the SQL editor: `CREATE CATALOG bank_stmt_dlh;` (or your name).
3. `make db-init` creates the `bronze`, `silver` and `gold` schemas.
4. `make secrets` copies the PDF password, the Jev key and the bucket keys from `.env` into the secret scope.
   Groups: `core`, `minio`, `sp`, `mail`. An empty group that the configured source does not need is skipped.
5. `make deploy` uploads `src/`, `config/`, `databricks/sql/`, `assets/` and the notebooks to
   `/Users/<DATABRICKS_USER>/bank-stmt-dlh`. The repo is the source of truth; do not edit notebooks online.
6. `make etl` creates or updates the two jobs and starts the ETL once.
7. `make dashboard` generates the AI/BI dashboard definition from `databricks/dashboards/build_dashboard.py`
   and publishes it.

## Daily loop

```bash
make upload            # STATEMENTS_DIR -> bucket, then start the job (WEEKLY=1 for weekly statements)
make run               # start the ETL job now
make weekly-report     # run the weekly cash report now (WEEK_END=2026-10-18 FORCE=1 MODE=dry)
make deploy            # after a code or config change, then make run
```

Weekly statements go under `statements/weekly/` in the bucket; everything else under the prefix is monthly.

## Jobs and notebooks

Job `bank-stmt-dlh` runs once a day at midnight IST. Task order: `02` (ingest) -> did it find new data? ->
`01` (seed) -> `03` (gold). The last two run only when there is something new, or when the job is started with
`force=true` (what `make run` does). Job `bank-stmt-dlh-weekly-cash-report` runs the same chain and then `04`
every Monday 00:00 America/New_York.

| Notebook | What it does | Deterministic? |
|---|---|---|
| `01_reference_seed` | Copies categories, payee map, rules, declared payments and settings from `config/*.yaml` into gold tables | Yes |
| `02_ingest_bronze_silver` | Lists the bucket, skips content already loaded (SHA-256), parses, reconciles, tags weekly/monthly duplicates, merges to silver. Unreconciled files go to quarantine | Yes |
| `03_gold_build` | Categorizes, finds recurring payments, rebuilds gold tables and the views in `databricks/sql/20_gold_views.sql` | Mostly. Holds the only AI call (Jev), if a key is set |
| `04_weekly_cash_report` | Snapshots the week, fetches one USD/INR rate (ECB via Frankfurter), renders the email (INR or USD body, PDFs in both) and sends it through Microsoft Graph | Yes |
| `jobs/b0_feasibility`, `jobs/b0_diagnose` | One-off checks that serverless compute can reach the bucket and parse a statement | Yes |
| `jobs/s0_sharepoint_check`, `jobs/m0_mail_rate_check` | Health checks for the optional SharePoint source and mailer | Yes |

Notebooks find the deployed repo root from their own path and read catalog, secret scope and bucket from
`config/settings.yaml`, so no user name or workspace id is in the code. SQL files use the token `__CATALOG__`,
replaced at run time.

## Dashboard

Pages: Overview (cash, monthly outflow, runway), Spend, Recurring and yearly (next due, lapsed), Funding and
founder, Cash flow by date (date-range filter), Data quality (statements loaded, quarantined files, duplicate
lines, rows for review, reports sent). Every tile is SQL on the gold views; no model writes anything.

## Weekly cash report

One email per week with opening and closing balance, money in and out, spend by category, the largest movements,
upcoming payments and the review queue. The body is in INR by default; two PDFs (INR and USD) are attached, at
one stated exchange rate. Append-only snapshot tables keep every report as sent, so a resend reproduces what went
out and past weeks do not change when rules are fixed later. `gold.report_log` records every send; a dry-run mode
sends to one address only.

Sending needs a shared mailbox and a send-only Entra app limited to it: see the
[mail cookbook](cookbook/graph-mail-setup.md).

## Troubleshooting

- A 403 from the bucket behind a proxy: rerun `jobs/b0_diagnose`, which probes list, HEAD and ranged GET.
- A quarantined file is listed on the dashboard's Data quality tab with the reconciliation errors.
- Secrets expire (SharePoint and mailer client secrets): renew, then `make secrets`.
- Graph throttling (429) and 5xx answers are retried with backoff.
