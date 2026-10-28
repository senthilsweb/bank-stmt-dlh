# Spec: release

## Configurability

The code SHALL contain no personal identifier (email address, user name, tenant host, home-lab host, folder path).
Workspace user (`DATABRICKS_USER`), alert address (`ALERT_EMAIL`, default `DATABRICKS_USER`) and catalog
(`DATABRICKS_CATALOG`) SHALL come from `.env` for local scripts. Catalog, secret scope, MinIO bucket and prefix, and
company name SHALL come from `config/settings.yaml` inside Databricks. A notebook SHALL find the deployed repo root
from its own path, never from a literal user path.

SQL files SHALL use the token `__CATALOG__`; the runner and the notebooks substitute the configured catalog.

## Statement sources

`statement_source` SHALL accept `minio` (any S3-compatible endpoint) or `sharepoint`. The MinIO source SHALL treat
keys under `<prefix>weekly/` as weekly statements and all other keys under the prefix as monthly. `make secrets`
SHALL copy the SharePoint, mail, MinIO and core (PDF password, Jev key) groups; a group with no values is reported
and skipped, not failed, except the group the configured source needs.

## Example configuration and tests

`config/examples/` SHALL hold `merchant_map.yaml` and `recurring_declared.yaml` with fictional names and the same
structure as the real files. Unit tests SHALL NOT contain the name of a real person or company. Report functions
SHALL take the company name as an argument with the configured value as default.

## Publishing

`make publish` SHALL copy the tracked files of the current branch into the public repo directory (`PUBLIC_REPO_DIR`),
excluding `docs/artifacts/`, the real payee and declared files, and `config/examples/` after copying its files into
`config/`. It SHALL remove lines holding private page links. It SHALL then scan every exported text file for: every
name in the real payee and declared files, every non-empty `.env` value except catalog, bucket, library and mode, the
owner's addresses and hosts, and common secret patterns. One hit SHALL stop the publish with the file and line, with
the value masked. On success it SHALL commit in the public repo with the source commit id in the message and SHALL
NOT push unless asked (`--push`).

## Documentation

README SHALL explain what the project does, the three ways to run it (local folder, S3-compatible, SharePoint), setup,
and the daily loop, with placeholders only. A `LICENSE` file SHALL exist.
