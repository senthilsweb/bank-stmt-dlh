# Design: public-release

## Where each value lives

| Value | Local scripts | Databricks | Default |
|---|---|---|---|
| Workspace user | `DATABRICKS_USER` (`.env`) | notebook path | required |
| Alert email | `ALERT_EMAIL` (`.env`) | job spec | `DATABRICKS_USER` |
| Catalog | `DATABRICKS_CATALOG` (`.env`) | `settings.catalog` | `bank_stmt_dlh` |
| Secret scope | `settings.secret_scope` | same | `bank-stmt-dlh` |
| MinIO bucket, prefix | `MINIO_BUCKET` (`.env`) for upload | `settings.minio_bucket`, `settings.minio_prefix` | `bank-stmt-dlh`, `statements/` |
| Company name | `settings.company_name` | same | `ConceptLabs` |
| Logos | `assets/logo.png`, `assets/logo-white.png` | same | shipped |

`src/settings.py` reads `config/settings.yaml` relative to its own file, so it works on a laptop and under
`/Workspace/Users/<user>/bank-stmt-dlh/src`. A notebook derives `BASE` from
`dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath()` (two levels up from
`notebooks/<name>` or `jobs/<name>`), then adds `BASE/src` to `sys.path`.

## MinIO weekly statements

`scripts/upload_statements.py --weekly` puts files under `<prefix>weekly/`. The ingest notebook labels a key
`weekly` when `/weekly/` is in it, else `monthly`, and the rest of the pipeline is unchanged (it already keys on
`statement_kind`).

## Publish

`scripts/publish_public.py`:
1. `git ls-files` on the current branch; drop the exclude list; copy into a temp tree; copy `config/examples/*`
2. Build the deny list at run time from the real config files and `.env` (never from a committed list of names).
3. Scan; print `file:line key=****` on a hit and exit 1.
4. `rsync --delete` (keeping `.git`) into `PUBLIC_REPO_DIR`, `git init` on first run, commit
   `sync: <short sha> from private repo`. `--push` pushes `main`.

The public repo's first commit is the whole tree, so the private history is never exported.

## Scrubbed at source (stays scrubbed after merge to main)

README, cookbooks, `.env.sample`, OpenSpec files, `pyproject.toml`: tenant host becomes `<tenant>.sharepoint.com`,
mailboxes `noreply@<domain>`, the owner's handle "the owner", the home-lab host "your MinIO endpoint".

## Decisions of 2026-10-27

- The public copy is a separate repo (`bank-stmt-dlh`, first named `bank-etl`) with its own identity: fictional company ConceptLabs, text logo,
  sample statements. `config/publish.yaml` (private) holds the mapping: excluded paths, overlays (`config/examples`
  -> `config`, `assets/public` -> `assets`, `docs/README.public.md` -> `README.md`), text replacements applied to
  contents and file names, lines to drop. Every replacement key doubles as a deny term, so a leftover stops the export.
- This branch stays unmerged. `main` keeps the private README and names; useful generic parts can be ported later.
