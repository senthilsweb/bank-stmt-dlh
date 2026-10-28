# Tasks — databricks-lakehouse

Owner prerequisites (not code):
- [x] Approve this proposal (`PROPOSED` → `APPROVED`, 2026-10-18)
- [x] Databricks workspace confirmed: Free Edition on AWS us-east-2, serverless starter warehouse, Unity Catalog on, no external locations
- [x] MinIO route chosen: MinIO is the single home of raw PDFs, Databricks reads from it (2026-10-18). Bucket `bank-stmt-dlh` created; 10 statements uploaded
- [x] Catalog `bank_stmt_dlh` created by the owner (2026-10-18); schemas bronze, silver, gold created by `databricks/sql/00_init.sql`
- [x] Create secret scope `bank-stmt-dlh` (2026-10-18) with `pdf_password`, `typesafe_api_key`, `minio_endpoint`, `minio_access_key`, `minio_secret_key`
- [x] MinIO reachable from the internet (the MinIO console)
- [ ] Replace the root MinIO key with a key limited to bucket `bank-stmt-dlh`; add it to the secret scope

Intent (done by this change):
- [x] Proposal, specs, design written

Execution — bolts (B1 first; the rest can fan out where files are disjoint):
- [x] **B1 Code reuse** (2026-10-18): instead of a wheel, `scripts/deploy_databricks.py` syncs `src/`, `config/` and `databricks/sql/` to the workspace and notebooks import them. Parser keeps statement row order (`seq`); `categorize` takes a persistent Jev cache. Local tests still pass
- [x] **B2 Reference seed** (notebook `01_reference_seed`): load `config/*.yaml` into `dim_category`, `payee_map`, `category_rules`, `recurring_declared` (script plus table DDL in `databricks/sql/`)
- [x] **B3 Bronze and silver** (notebook `02_ingest_bronze_silver`): `bronze.statement_files` (object key, etag, sha256, size), `bronze.raw_lines`, discover/parse/reconcile/merge tasks, `silver.quarantine`
- [x] **B4 Gold** (notebook `03_gold_build` + `databricks/sql/20_gold_views.sql`): SQL for `fact_transactions` (categorize task), `recurring_series`, `monthly_summary`, `monthly_by_category`, `founder_monthly`, `upcoming_payments`, `review_queue`
- [x] **B5 Jev task** (inside `03_gold_build`; `gold.jev_labels` cache): batch call, threshold, `jev_labels` cache, secret-scope key, no-key = skip
- [x] **B6 Dashboard** (`databricks/dashboards/`, AI/BI, 5 pages): five pages, SQL datasets on gold, definitions text
- [x] **B7 Job and schedule**: job `bank-stmt-dlh`, daily midnight (IST) schedule, failure email, run-now after upload. Deployed with Python scripts (`dbx_job.py`, `deploy_databricks.py`) instead of a Databricks Asset Bundle; no `databricks.yml` yet (CLI not installed here)
- [x] **B8 MinIO reader** (`src/minio_reader.py`): boto3 listing and download inside the job, key from the secret scope, clear error when MinIO is unreachable
- [x] **B0 Feasibility job** (2026-10-18): serverless installs `pdfplumber`; MinIO reachable (list 0.2 s, download 0.2 s); Jan statement parsed in the job: 3 pages, 28 transaction lines, same as local. One earlier run got a transient HTTP 403 on HeadObject from Cloudflare; two reruns and a diagnostic run passed. The MinIO reader must retry with backoff (B8)

Operations:
- [x] Parity run (2026-10-18): 282 transactions, same `txn_id` set, same debit and credit totals; only Jev-labelled rows differ in category (Jev answers vary between runs, now cached)
- [ ] Drop a new statement in MinIO and watch the next run pick it up (acceptance 2); drop it again (idempotency)
- [ ] Break a statement on purpose and confirm quarantine (acceptance 3)
- [ ] Check logs for secrets and names (acceptance 5)
- [ ] `bundle deploy` from a clean target (acceptance 6)
- [ ] Update specs, `README.md`, `CLAUDE.md`; archive the change
