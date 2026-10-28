# Tasks — public-release

Owner prerequisites (not code):
- [x] Approve this proposal (2026-10-27)
- [x] Public repo: `bank-etl` under the owner's GitHub login (decided 2026-10-27). This branch is not merged to main; good parts may be ported later
- [x] Licence MIT (confirmed 2026-10-27)
- [x] Public branding: no company name, text logo for the fictional company ConceptLabs; README centred on local folder and MinIO

Execution — bolts (B1 and B2 are disjoint; B3 after B1; B4 last):
- [x] **B1 Configurability** (2026-10-27): `src/settings.py`; `settings.yaml` keys; notebooks and jobs derive `BASE` and read catalog, scope, bucket; SQL `__CATALOG__`; scripts read `DATABRICKS_USER`, `ALERT_EMAIL`, `DATABRICKS_CATALOG`; `dbx_secrets` groups; MinIO weekly; company name and logo names in the report and dashboard
- [x] **B2 Examples and fixtures** (2026-10-27): `config/examples/`; fictional names in `tests/test_extract.py`; explicit company in `tests/test_weekly_report.py`
- [x] **B3 Docs** (2026-10-27): README rewrite; cookbooks, `.env.sample`, OpenSpec, `CLAUDE.md`, `pyproject.toml` scrubbed; `LICENSE`
- [x] **B4 Publish** (2026-10-27): `config/publish.yaml` maps private -> public (excludes, overlays, text and path replacements); every replacement key is a deny term
- [x] **B5 Samples** (2026-10-27): `scripts/make_sample_statements.py` -> six synthetic statements that reconcile; fictional payee map; `scripts/make_text_logo.py` -> ConceptLabs logos; `docs/README.public.md`: `scripts/publish_public.py`, `make publish`, first export scanned clean

Operations:
- [x] `make test` green on the branch (45 passed, 2026-10-27)
- [ ] `make deploy` and `make run` from the branch against the private workspace: ingest, gold and the weekly report behave as before
- [ ] First public export reviewed by the owner, pushed, friend can `make setup && make test`
