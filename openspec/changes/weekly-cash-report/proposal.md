# Proposal: weekly-cash-report — email a weekly cash report from Databricks

> Status: **APPROVED** (2026-10-24). Follows `sharepoint-source` and `weekly-statements`. Owner: the repo owner.

## Why

The numbers already exist in gold (balances, money in and out, category spend, upcoming payments, review queue),
but someone has to open the dashboard to see them. Founders, including the US-based one, should get the week's
cash position in their inbox without asking, in INR with USD available.

## What changes

- A second Databricks job `bank-stmt-dlh-weekly-cash-report` runs every **Monday 00:00 America/New_York** (the end of Sunday)
  and can be **started on demand** (`make report`, or Run now in Databricks with parameters).
- It sends one email per week: a formatted **HTML body in INR by default** (`report_body_currency` in `config/settings.yaml`, `INR` or `USD`), and **two PDF attachments**, the same
  report in USD and in INR. The PDFs are the job's own summary, not the bank's statement.
- USD uses **one exchange rate per report**: the latest ECB reference rate (Frankfurter API) on or before the report
  date, stored in `gold.fx_rates` and stated in the email and PDFs. INR stays the book of record.
- The email is sent through **Microsoft Graph `sendMail`** from a Databricks task, using a separate send-only Entra
  app limited to one shared mailbox.
- Recipients come from `.env` for now (`MAIL_RECIPIENTS`, comma-separated `email|Display Name`), later from the
  Databricks secret scope.
- `gold.report_log` records every send, so a week is sent once; a dry-run mode sends to the owner only.
- Two **append-only snapshot tables** keep every report as sent: `gold.weekly_cash_snapshot` (one row per report) and `gold.weekly_cash_snapshot_lines` (categories and largest movements). The email and PDFs are rendered from the snapshot, so a resend reproduces what went out and past weeks do not change when rules or labels are fixed later.
- The dashboard gets a **Cash flow by date** page with a date-range filter (built; see `openspec/changes/weekly-cash-report/tasks.md`) and later a **Weekly trend** page from the snapshots.
- Nothing is written by a model. Every figure is SQL on gold.

## Out of scope

Per-transaction day rates, other currencies, HTML dashboards in the email, replies, the bank's own PDF, SMS or chat delivery.

## Risks

| Risk | Handling |
|---|---|
| Serverless may not reach the rate API or Graph mail | Bolt M0 sends one test mail and fetches one rate from a serverless job before any report code is written |
| `Mail.Send` (application) can send as any mailbox | Exchange application access policy limits the app to the one shared mailbox; tested with `Test-ApplicationAccessPolicy` |
| Mail goes to the wrong people | `MAIL_MODE=dry` first (owner only); recipients parsed and validated, a bad entry fails the run before anything is sent |
| Rate API down | Use the latest stored rate and say so; with none, the run fails loudly rather than send a wrong USD PDF (the USD PDF is always attached) |
| Weekly statement not yet in SharePoint | Report still sends, with a notice that the bank statement for the week is not yet received |
| Client secret expires | Calendar reminder; the job failure email tells you |

## Acceptance criteria

1. `MAIL_MODE=dry` run delivers to the owner: HTML body in INR (the default body currency), two PDF attachments (USD, INR), figures equal to gold for the week.
2. The USD figures equal the INR figures divided by the stored rate; the USD PDF states the rate and its date, and the INR body points to it.
3. A rerun for the same week sends nothing; `force=true` sends again and logs it.
4. On-demand run with a `week_end` parameter reports that week.
5. A weekend report date uses Friday's rate.
6. The send app cannot send as any other mailbox (`Test-ApplicationAccessPolicy` shows Denied).
7. No secret, token or recipient address appears in job logs; no account number in the email or PDFs.
