# Tasks — weekly-statements

- [x] Approve this proposal (2026-10-24)

Execution — bolts:
- [x] **W0 Check** (`gold.jev_labels` is keyed on the request text, not `txn_id`; only gold.fact_transactions carries `txn_id` and it is rebuilt each run): confirm `gold.jev_labels` and any table keyed on `txn_id`; list what the new key changes
- [x] **W1 Key and tests** (`src/normalize.py`, `src/dedupe.py`, `tests/test_dedupe.py`; 15 tests pass) (`src/normalize.py`, tests): new `txn_id`; tests for weekly-vs-monthly narration difference and same-day look-alike lines
- [x] **W2 Tables and migration** (silver rebuilt from `bronze.raw_lines`: 282 transactions, 282 appearances, totals identical) (`databricks/sql`, notebook 02): `statement_kind`, `silver.transaction_sources`; rebuild silver from `bronze.raw_lines`; verify 282 and totals
- [x] **W3 Ingest** (both folders; weekly is skipped with a message until secret `sp_weekly_folder_id` exists) (notebook 02): read both folders, duplicate tagging, monthly-preferred update, collision guard, per-file counts
- [x] **W4 Views and dashboard** (monthly preferred in `monthly_flow`; `statement_status` one row per file; `duplicate_lines`; Data quality tab) (`20_gold_views.sql`, dashboard): monthly-only month-end and statement list; duplicates table on Data quality
- [x] **W5 Docs** (README done; cookbook and `CLAUDE.md` pending): README (end user guide: weekly folder is read), cookbook, `CLAUDE.md`

Operations:
- [x] Load the 9 weekly files (2026-10-24): 282 transactions, 339 appearances, 57 duplicates, totals unchanged (acceptance 1, 2). The job finds the monthly and weekly sub-folders from the year folder id (`sp_folder_id`); no separate weekly secret
- [x] Order test: covered by `tests/test_dedupe.py::test_order_does_not_change_silver` (acceptance 3)
- [x] Month-end balances unchanged after the weekly load: Oct 221,809.02 (partial), Sep 265,542.87, Aug 118,822.03 (acceptance 4)
- [ ] Update specs, README; archive
