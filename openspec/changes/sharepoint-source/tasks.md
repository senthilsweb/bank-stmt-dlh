# Tasks — sharepoint-source

Owner prerequisites (not code):
- [ ] Approve this proposal (`PROPOSED` -> `APPROVED`)
- [x] SharePoint host `<tenant>.sharepoint.com`; owner is tenant admin, so steps 4-5 of `design.md` are covered (2026-10-24)
- [x] Statements already in SharePoint: root site, `Shared Documents/<path to the statements folder>/01 MONTHLY STATEMENTS` (weekly statements skipped for now) (2026-10-24). Check the folder's own permissions are owners-only
- [x] Entra app `bank-stmt-dlh-reader` created, secret in `.env` (`SP_TENANT_ID`, `SP_CLIENT_ID`, `SP_CLIENT_SECRET`), `Files.SelectedOperations.Selected` consented and granted `read` on the folder (design steps 3-5)

Execution — bolts (S0 first; S1 and S3 are disjoint files and can run in parallel after S0):
- [x] **S0 Feasibility** (2026-10-24, passed on laptop and on serverless: token 200, monthly folder lists 10 PDFs, one downloads as a real PDF, drive root shows 0 entries to the app; `sp_*` secrets pushed with `scripts/dbx_secrets.py`; run with `scripts/dbx_run_notebook.py s0_sharepoint_check`) (`scripts/sharepoint_check.py` + `databricks/jobs/s0_sharepoint_check.py`): from laptop and from a serverless job: token, list folder (expect 10 PDFs), download one, other-site 403. Gate: if the job cannot reach Microsoft, stop and write the fallback proposal
- [x] **S1 Reader** (2026-10-24, 6 tests, no network) (`src/sharepoint_reader.py` + `tests/test_sharepoint_reader.py`): token, paged list, download with SHA-256, retry/backoff and `Retry-After`; tests use a fake HTTP transport, no network
- [x] **S2 Ingest** (2026-10-24) (`databricks/notebooks/02_ingest_bronze_silver.py`): `statement_source` switch, SHA-256-first dedup, `source` column on `bronze.statement_files`; local tests still pass
- [x] **S3 Config and secrets** (2026-10-24; `make secrets`): `config/settings.yaml` block, `.env.sample` (`SP_*`), `scripts/deploy_databricks.py` pushes `sp_*` to the scope
- [~] **S4 Tooling** (`make run` and `make secrets` added; `make upload` and MinIO scripts stay until decommission): `make upload` replaced by `make run` (job run-now, no file copy); `scripts/upload_statements.py` and `bootstrap_minio.py` removed at decommission, not before
- [~] **S5 Docs** (README done 2026-10-24; `CLAUDE.md` and `openspec/config.yaml` context line still to do): README (architecture line, notebook table, end user guide = "drop the PDF in the SharePoint folder", developer setup, env table), `CLAUDE.md`, `00_init.sql` comment, `openspec/config.yaml` context line

Operations:
- [x] Parity run with `sharepoint` (2026-10-24): 0 parsed, 10 registered by SHA-256, 282 transactions, same debit and credit totals; rerun adds no rows (acceptance 1, idempotent). `source` backfilled to `minio` on the 10 old rows
- [ ] Drop a new statement in the folder, watch the next run; drop it again (acceptance 2)
- [ ] Break a PDF on purpose, confirm quarantine (acceptance 3)
- [ ] Other-site 403 and secret/log check (acceptance 4, 5)
- [ ] Cutover: remove `minio_*` secrets and `MINIO_*` env (acceptance 6); MinIO bucket read-only for a month, then delete
- [ ] Mark the MinIO scoped-key task cancelled in `databricks-lakehouse/tasks.md`; archive both changes
