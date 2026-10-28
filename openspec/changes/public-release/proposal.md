# Proposal: public-release — share the code without the company's data

> Status: **APPROVED** (2026-10-27). Follows `weekly-cash-report`. Owner: the repo owner.

## Why

Other people want to run this pipeline on their own statements. The code is generic, but the repo carries
ConceptLabs's workspace identifiers (owner email in notebook paths, catalog, secret scope, bucket), the tenant host and
folder path, and, in `config/merchant_map.yaml` and `config/recurring_declared.yaml`, the names of real people and
companies with notes about them. Those names are also in every commit of the history. A public copy must contain
none of that, and the private repo must keep running unchanged.

## What changes

- **One code base, two repos.** The code becomes configurable (`.env` and `config/settings.yaml`), so the same
  branch serves the private repo (real values) and the public one (placeholders). No fork of the logic.
- **Identifiers out of the code.** Workspace user, alert address, catalog, secret scope, MinIO bucket and prefix,
  company name and logo file names come from configuration, with the current values as defaults where they are not
  personal.
- **MinIO is a first-class source.** S3-compatible storage (MinIO, AWS S3, R2) reads weekly statements too, the
  bucket comes from settings, and `make secrets` copies the MinIO keys. SharePoint stays the Microsoft 365 option.
- **Example configuration.** `config/examples/` holds fictional payee and declared-payment files. Tests use fictional
  names and pass an explicit company name.
- **Docs for strangers.** README rewritten for a new user; cookbooks, `.env.sample` and OpenSpec files use
  placeholders instead of the tenant host, mailboxes and the owner's handle; `docs/artifacts/` stays private.
- **A publish step.** `make publish` exports the tracked files of the current branch into a separate public repo:
  excludes private paths, swaps in the example configs, scans the result for every real name, host, address and
  `.env` value, and commits one sync commit. The first export is a single squashed commit, so the private history
  never leaves.
- **A licence.** MIT, ConceptLabs.

## Out of scope

- Making the private repo itself public (its history holds the names).
- Removing the HDFC-specific parser. Other banks are a parser module each, as before.
- Publishing the `docs/artifacts/` pages (they link to ConceptLabs's workspace and mailboxes).
