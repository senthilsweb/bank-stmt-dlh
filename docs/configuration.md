# Configuration

Two files, one rule: secrets in `.env`, names in `config/settings.yaml`. Nothing personal is in code.

## `.env`

| Variable | Used for |
|---|---|
| `PDF_PASSWORD` | Opens the statement PDFs. Empty for the synthetic samples |
| `STATEMENTS_DIR` | Folder with the PDFs (local runs, `make upload`). Relative paths are from the repo root |
| `TYPESAFE_API_KEY` | Jev, optional. Empty means no AI step at all |
| `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_HTTP_PATH` | Workspace, token and SQL warehouse path |
| `DATABRICKS_USER` | Your workspace login. Code is deployed under `/Users/<DATABRICKS_USER>/bank-stmt-dlh` |
| `DATABRICKS_CATALOG` | Catalog for the local SQL runner (same as `catalog` in settings) |
| `ALERT_EMAIL` | Who gets a mail when a job fails (defaults to `DATABRICKS_USER`) |
| `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` | S3-compatible statement source |
| `SP_*` | SharePoint app and folder ids ([cookbook](cookbook/sharepoint-source-setup.md)) |
| `MAIL_*` | Weekly report sender, recipients and mode ([cookbook](cookbook/graph-mail-setup.md)) |

`.env.sample` is the contract and is kept complete.

## `config/settings.yaml`

```yaml
company_name: ConceptLabs        # report and dashboard title
catalog: bank_stmt_dlh           # Unity Catalog catalog, created once by hand
secret_scope: bank-stmt-dlh      # Databricks secret scope filled by `make secrets`
minio_bucket: bank-stmt-dlh      # statement_source: minio
minio_prefix: statements/        # monthly under the prefix, weekly under <prefix>weekly/
jev_confidence_threshold: 0.9    # Jev label accepted at or above this
review_amount_threshold: 5000    # unlabelled rows at or above this (INR) need a person
statement_source: minio          # minio | sharepoint
report_body_currency: INR        # weekly email body: INR | USD (PDFs are always sent in both)
```

`src/settings.py` reads this file next to the package, so the same code runs on a laptop and in the deployed
workspace copy.

## Categories, payees, rules

Categorization is deterministic and ordered. First match wins.

1. **Payee map**, `config/merchant_map.yaml`. A name matches as whole words in the cleaned counterparty, case
   insensitive. An entry can be a plain name, `re:<regex>` for narrations the bank splits oddly, or a mapping with
   `direction` and `from` / `until` dates.
2. **Rules**, `config/rules.yaml`. A regex over counterparty and narration, optionally limited to a direction.
3. **Founder logic**, the `founder` block of the payee map. Every debit to the founder is `operations`; a credit that
   matches an earlier debit of the same amount is a loan repayment, any other credit is founder funding.
4. **Stored Jev label**, then **Jev** for what is left, only with a key and only at confidence 0.9 or more.
5. Otherwise `unclassified`, or `human-intervention-required` when the amount is at or above the review threshold
   or the row is a credit.

`config/categories.yaml` is the master list with a type per category (income, expense, statutory, debt, transfer,
funding, operations). `config/recurring_declared.yaml` lists payments that repeat but cannot be detected (yearly, fewer
than three occurrences) and engagements that have ended.

Every row carries `category_source` (`map`, `rule`, `founder`, `jev`, `unclassified`, `review`) and a confidence,
so a label can always be traced.

## Jev, the only AI step

Jev is a decision model, not a text-generating LLM. It answers a typed `choice` question with a probability and a
confidence. It sees only `Counterparty: X. Channel: upi. Direction: debit.`, never amounts, dates or account numbers.
Every answer is stored, so the same request is never sent twice. No key means no call.
