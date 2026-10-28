# Design: databricks-lakehouse

## Layers

| Layer | Schema | Tables | Notes |
|---|---|---|---|
| Landing | MinIO `bank-stmt-dlh/statements/` | raw PDFs | The only copy of the files. Nothing is stored in Databricks |
| Bronze | `bronze` | `statement_files`, `raw_lines` | One row per PDF: object key, etag, `file_sha256`, size, `ingested_at`; plus the parsed raw lines. Never edited |
| Silver | `silver` | `statements`, `transactions`, `quarantine` | Parsed and reconciled only. `txn_id` is the merge key |
| Gold | `gold` | `fact_transactions`, `recurring_series`, `monthly_summary`, `monthly_by_category`, `founder_monthly`, `review_queue`, `upcoming_payments` | What the dashboard reads |
| Reference | `gold` | `dim_category`, `payee_map`, `category_rules`, `recurring_declared`, `jev_labels` | Seeded from `config/*.yaml`; git stays the source of truth |

## Flow (one Databricks Job, serverless, tasks in order)

1. **discover**: list MinIO `statements/` with `boto3`, anti-join with
   `bronze.statement_files` on object key and etag. Only new or changed files continue.
2. **parse**: download each new file to the job's temporary disk, hash it, run the
   current parser (`src/extract.py`) with the password from a secret scope, then
   delete the temporary file. Output rows plus the bank's summary.
3. **reconcile**: debit and credit counts, totals and closing balance must match
   the statement summary. Pass goes to `silver`, fail goes to `silver.quarantine`
   with the reason, and the job ends with a warning.
4. **normalize**: channel, clean counterparty, `txn_id` (`src/normalize.py`).
5. **merge**: `MERGE INTO silver.transactions` on `txn_id`. Re-running is safe.
6. **categorize**: payee map, then rules, then founder logic. Rows left over are
   sent to Jev in one batch, and answers at or above the threshold are written
   to `gold.jev_labels` and reused. Everything else becomes `unclassified` or
   `human-intervention-required`.
7. **publish**: rebuild the gold tables and views, then refresh the dashboard.

The Python in steps 2 to 6 is the same code that runs locally. It is packaged as a
wheel and called from the job, so local tests protect the Databricks run.

## Storage and MinIO (decided 2026-10-18)

MinIO is the single home of the raw PDFs. Databricks keeps **no copy**: the job
reads each new file from MinIO over HTTPS, parses it in the job's temporary disk
and discards it. Only parsed rows and file metadata are stored as tables.

- Unity Catalog cannot map MinIO on Free Edition (only the managed location exists,
  external access is off), so there is no volume or external location.
- The job needs the MinIO endpoint, access key and secret in the secret scope.
  The key must be limited to bucket `bank-stmt-dlh`, not the root account.
- If MinIO is unreachable the job stops after the discover task, tables keep their
  last good data, and the owner gets an alert.
- Feasibility (bolt B0) passed on 2026-10-18: serverless compute installs `pdfplumber`,
  reaches MinIO through Cloudflare, and parses a statement. One run met a transient
  403 from Cloudflare, so every MinIO call retries with backoff (3 tries) before the
  run fails.

## Trigger

A file-arrival trigger cannot watch MinIO. The job instead runs on a schedule
(once a day at midnight IST) and `make upload` calls the Jobs run-now API after it uploads, so
a new statement is processed at once. Every run is idempotent, and a run with no
new files finishes in seconds.

## Determinism rules

- Parsing, reconciliation, rules, recurring detection, projections, reports and
  dashboard queries are code and SQL only. No LLM call is allowed in them.
- Jev is allowed in exactly one task (`categorize`), for rows no map or rule
  matched. It sees `Counterparty, channel, direction`, never amounts or account
  numbers. Threshold 0.9 from `config/settings.yaml`. Answers are cached.
- Rows above the review amount, and unlabelled credits, are never auto-labelled
  by Jev unless confidence passes the gate; otherwise `human-intervention-required`.
- `ai_parse_document` runs only on a file that failed reconciliation, and its
  result is reconciled the same way. If it still fails the file stays quarantined.

## Dashboard

An AI/BI (Lakeview) dashboard with these pages: Overview (cash, outflow,
runway, funding, client receipts), Spend (by category, month, payee group),
Recurring and yearly (next due, lapsed), Funding and founder, Data quality
(unlabelled counts, reconciliation status per statement). Datasets are SQL on
gold only. The dashboard is a file in the bundle.

## Security

- Unity Catalog grants: job principal writes, owner reads. Nobody else by default.
- Secrets in a Databricks secret scope: `pdf_password`, `typesafe_api_key`,
  `minio_endpoint`, `minio_access_key`, `minio_secret_key`. Nothing in code, logs or the bundle.
- Raw narrations contain names of individuals. They stay in bronze and silver;
  gold keeps `counterparty_clean`. The dashboard shows categories and aggregates,
  and payee names only on the recurring table.
- The local `data/` stays gitignored. No statement leaves git-ignored paths.

## Bundle layout (added to the repo)

```
databricks.yml            bundle: targets dev and prod, job, dashboard
databricks/
  jobs/statement_etl.yml  job and trigger definition
  sql/                    gold views and tables, one file each
  dashboards/finance.lvdash.json
src/                      existing code, packaged as a wheel
config/                   categories, rules, payee map, settings (seed source)
```

## Parity check (Operations phase)

Run the local pipeline and the Databricks job on the same 10 statements and
compare: transaction count, totals per month, totals per category, and the set of
`txn_id`. Any difference blocks the cut-over.
