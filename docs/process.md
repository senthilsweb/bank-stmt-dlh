# Process

## OpenSpec first, AI-DLC phases

Every non-trivial change starts as a folder `openspec/changes/<name>/` with four files, before any code:

| File | Holds |
|---|---|
| `proposal.md` | Why, what changes, what is out of scope. Status and owner at the top |
| `specs/<area>/spec.md` | Requirements in SHALL form |
| `design.md` | How: tables, functions, decisions and their reasons |
| `tasks.md` | Owner prerequisites, execution bolts (B1, B2, ...), operations checks. Ticked as they land |

Three phases. **Intent** is proposal, specs and design. **Execution** is the bolts; bolts that touch disjoint files
run in parallel. **Operations** is validation on real statements (every statement reconciles, totals equal the
bank's), then the specs and notes are updated. `CLAUDE.md` at the repo root states the rules for an AI pair.

The changes shipped so far: `databricks-lakehouse`, `sharepoint-source`, `weekly-statements`,
`weekly-cash-report`, `public-release`. Each folder is readable on its own.

## Rules that do not bend

- **Deterministic first.** Parsing, reconciliation, rules and recurring detection are plain Python and SQL.
  AI only where rules cannot decide, behind a 0.9 confidence gate, and only ever sees the cleaned counterparty,
  channel and direction.
- **Never load an unreconciled statement.**
- **Privacy.** PDFs, Parquet and DuckDB are gitignored. `.env` is never committed. No real names, addresses,
  hosts or amounts in code, tests or docs. The synthetic statements in `samples/` are the one tracked PDF set.
- Python 3.12+, `uv`, `make` targets only. Docs short and plain.

## How this public copy is produced

The code is developed in a private repository that holds one company's configuration. This public repository
is an export of a branch: `scripts/publish_public.py` copies the tracked files, swaps in sample configuration and a
generic logo, applies name replacements from a private mapping file, then scans every text file for real names,
environment values, hosts and git authors. One hit stops the export. The first export is one squashed commit, so no
private history is published. `config/publish.yaml` in this copy is an example of that mapping.

## Contributing

- Add a bank: one parser module that returns the same columns as `src/extract.py`, plus a synthetic sample.
- Add a category or rule: edit `config/`, run `make test`, then `make deploy` and `make run`.
- Open a change folder under `openspec/changes/` for anything larger and say what you intend before coding.
