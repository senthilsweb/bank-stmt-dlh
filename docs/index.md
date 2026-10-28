# bank-stmt-dlh

Bank statement PDFs (HDFC Bank current account layout) go in. A reconciled ledger comes out, with category,
recurring-payment, cash and runway reports. It runs on a laptop with DuckDB, or as a scheduled Databricks job
that reads the PDFs from an S3-compatible bucket and serves an AI/BI dashboard and a weekly cash report by email.

**Deterministic first.** Parsing, reconciliation, rules, recurring detection, reports and the dashboard are plain
code and SQL. The one optional AI step is Jev (TypeSafe AI), used only for payments the rules cannot place, behind a
confidence gate.

```
PDF statements  (local folder | S3-compatible bucket | SharePoint folder)
   -> bronze   file list + raw parsed lines
   -> silver   reconciled statements + transactions (weekly/monthly duplicates tagged once)
   -> gold     categorized facts, recurring series, views  -> reports, dashboard, weekly email
```

| Step | Method |
|---|---|
| Parse and reconcile | `pdfplumber` + balance arithmetic (`src/extract.py`) |
| Channel, counterparty, `txn_id` | regex and hashing (`src/normalize.py`) |
| Categorize | payee map, then rules, then founder logic (`config/*.yaml`, `src/categorize.py`) |
| Recurring and yearly payments | gap and amount test, plus a declared list (`src/recurring.py`) |
| Reports, dashboard, weekly email | SQL views and plain rendering |
| Leftovers | Jev, optional, confidence 0.9 or more |

!!! note "Never load an unreconciled statement"
    Every statement is checked against the bank's own STATEMENT SUMMARY: debit and credit counts, totals and the
    closing balance. One that does not match goes to quarantine and is never loaded further.

## Where to go

- [Getting started](getting-started.md): run the synthetic samples in two minutes, then your own statements.
- [Configuration](configuration.md): `.env`, `config/settings.yaml`, payees, rules, categories.
- [Databricks lakehouse](databricks.md): bucket, secrets, deploy, jobs, dashboard.
- [Data model](data-model.md): bronze, silver and gold tables and views.
- Cookbooks: the optional Microsoft 365 pieces, a [SharePoint statement source](cookbook/sharepoint-source-setup.md)
  and the [weekly report mail](cookbook/graph-mail-setup.md).
- [Process](process.md): how changes are made (OpenSpec, AI-DLC), and how the public copy is produced.

Source: [github.com/senthilsweb/bank-stmt-dlh](https://github.com/senthilsweb/bank-stmt-dlh). MIT licence.
