# CLAUDE.md

## What this repo is

ConceptLabs bank statement ETL. HDFC current account PDFs go in, Parquet and
DuckDB (local) or a Databricks lakehouse come out, for category, recurring and trend reports
and a weekly cash report by email. Source is shared publicly through `make publish`;
the company's data and `docs/artifacts/` stay private.

## Workflow (non-negotiable)

- **OpenSpec first.** Nontrivial changes start as `openspec/changes/<name>/` with
  `proposal.md`, `specs/`, `design.md`, `tasks.md`. Use the `/opsx:*` commands.
  No code before the intent is written and approved.
- **AI-DLC phases: Intent → Execution → Operations.** Intent = proposal + specs +
  design. Execution = bolts (B1, B2, ...) in `tasks.md`; disjoint-file bolts fan
  out to parallel subagents. Operations = validation on the real statements
  (every statement reconciles, totals equal the bank's), then update specs and memory.
- Current change: `openspec/changes/public-release/` (APPROVED).

## Rules

- **Deterministic first.** Parsing, reconciliation, rules and recurring
  detection are plain Python. AI (Jev) is only for rows the rules cannot
  label, and always behind a 0.9 confidence gate.
- **Never load an unreconciled statement.** Counts, totals and closing balance
  must match the bank's STATEMENT SUMMARY.
- **Privacy.** PDFs, Parquet and DuckDB are gitignored. Never commit `.env`.
  Send Jev only the cleaned counterparty, channel and direction.
- **Secrets** via environment variables; `.env.sample` is the contract.
- Python 3.12+, `uv`, `make` targets only. Docs short and plain.
- Naming: lowercase hyphen slugs for repo, files and folders.
- **No personal identifiers in code or docs.** Workspace user, catalog, scope, hosts and
  addresses come from `.env` or `config/settings.yaml`. Real payee names live only in
  `config/merchant_map.yaml` and `config/recurring_declared.yaml`, which `make publish` replaces
  with `config/examples/`.
