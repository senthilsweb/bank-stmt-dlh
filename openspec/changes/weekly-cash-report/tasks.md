# Tasks — weekly-cash-report

Owner prerequisites (not code):
- [x] Approve this proposal (2026-10-24)
- [x] Shared mailbox `finance-reports@<domain>` created (2026-10-24), 4 members; `MAIL_SENDER` set in `.env`
- [x] Entra app `bank-etl-mailer` created, `Mail.Send` (Application) consented, secret in `.env` (2026-10-24; token role `Mail.Send` verified)
- [x] Exchange application access policy created (group `bank-etl-mailer-scope` = finance-reports and noreply); owner reports Test-ApplicationAccessPolicy Granted for both and Denied for another mailbox (2026-10-24). Still to confirm from the job side: `graph_mail_check.py --as <personal mailbox>` returns 403
- [x] `.env` filled (sender finance-reports@<domain>, dry run to the owner): `MAIL_CLIENT_ID`, `MAIL_CLIENT_SECRET`, `MAIL_SENDER`, `MAIL_RECIPIENTS`, `MAIL_DRY_RUN_TO`, `MAIL_MODE=dry`

Execution — bolts (M0 first; M1 and M2 are disjoint and can run in parallel after M0):
- [x] **M0 Feasibility** (2026-10-24, passed on serverless): token 200; `sendMail` HTTP 202 from `noreply@<domain>` (sender switched from `finance-reports`, which Graph still answered 403 although Exchange says Granted); rate API 200, weekend date returns Friday's rate. Rerun: `scripts/dbx_run_notebook.py m0_mail_rate_check`. A full test report (real week 12-18 Oct, INR body, USD and INR PDFs) also reached the owner's inbox from `scripts/send_test_report.py`
- [ ] **M1 Views, rates, snapshots, log** (`databricks/sql`, notebook 03/04): `gold.weekly_cash_*` views, `gold.fx_rates`, `gold.report_log`, append-only `gold.weekly_cash_snapshot` and `_lines`; check totals against the 9 weekly statements
- [x] **M2 Renderer** (2026-10-24, `src/weekly_report.py`, `tests/test_weekly_report.py`): HTML body in USD, PDFs in USD and INR (reportlab; "INR" text in the PDF because the base fonts lack the rupee sign), rounding rule, late-statement notice, no account number; sample rendered and viewed
- [~] **M3 Sender and job** (`src/graph_mail.py` and tests done 2026-10-24; notebook, job and schedule to do) (`src/graph_mail.py`, notebook `04_weekly_cash_report`, `scripts/dbx_job.py`): recipient parser, `sendMail`, retries, log; job with the Monday 00:00 ET schedule, parameters, `make report`
- [ ] **M4 Docs and dashboard**: README, cookbook, `.env.sample`, a "Reports sent" table on the Data quality tab, a "Weekly trend" page from the snapshots, `make secrets` copies `mail_*`

- [x] **D1 Cash flow by date** (built early, 2026-10-24): `gold.cashflow_daily`, `gold.balance_daily`, dashboard page with a date-range filter; checked in the browser for 1 to 18 Oct 2026

Operations:
- [ ] Dry run to the owner: acceptance 1, 2
- [ ] Rerun sends nothing; `force=true` sends again (acceptance 3)
- [ ] On-demand run with `week_end` (acceptance 4); weekend date uses Friday's rate (acceptance 5)
- [ ] Policy denial test and log/privacy check (acceptance 6, 7)
- [ ] Switch `MAIL_MODE=live`, first live send; move recipients to the secret scope
- [ ] Update specs, README; archive
