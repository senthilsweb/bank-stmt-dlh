# Design — weekly-cash-report

## Job `bank-etl-weekly-cash-report` (serverless, notebook tasks)

| Task | Does |
|---|---|
| 1 ingest | notebook 02 (any weekly or monthly PDF dropped that day is loaded; duplicates tagged) |
| 2 week | picks the window Monday to Sunday ending `week_end` (default: the Sunday just ended), checks `gold.report_log` (skip unless `force`) |
| 3 rate | fetch USD/INR for the latest date <= `week_end`, upsert into `gold.fx_rates` |
| 3b snapshot | write the week's figures to `gold.weekly_cash_snapshot` and `_lines` (version = previous + 1 on a forced rerun) |
| 4 render | HTML body (INR by default, USD if `report_body_currency: USD`) and two PDFs (USD, INR) **from the snapshot**, not from live views |
| 5 send | Graph `sendMail` from `MAIL_SENDER`, attachments base64 (each well under 3 MB) |
| 6 log | one row per send in `gold.report_log` |

Parameters: `week_end` (date, optional), `force` (true/false), `mode` (dry/live; default from `MAIL_MODE`).
Schedule: `0 0 0 ? * MON`, `America/New_York`. On demand: `make report [WEEK_END=2026-10-18 FORCE=true MODE=dry]`.

## Data

| Object | Content |
|---|---|
| `gold.weekly_cash_report` (view) | opening, closing, money in, money out, counts for a week window; opening = closing of the previous day's balance from the ledger |
| `gold.weekly_by_category` (view) | money out by category |
| `gold.weekly_transactions` (view) | every payment of the week |
| `gold.fx_rates` (table) | rate_date, base `USD`, quote `INR`, rate, source `frankfurter`, fetched_at |
| `gold.weekly_cash_snapshot` (table, append-only) | report_id, week_start, week_end, version, opening, closing, money_in_inr, money_out_inr, payments, rate, rate_date, mode, created_at: the figures exactly as reported |
| `gold.weekly_cash_snapshot_lines` (table, append-only) | report_id, kind (`category` or `movement`), label, amount_inr, payments, rank: category totals and the largest movements as reported |
| `gold.report_log` (table) | week_end, mode, sent_at, recipients (count only, not addresses), rate, rate_date, status, message_id |

Upcoming payments and the review count come from existing views (`upcoming_payments`, `review_summary`).

## Currency

INR is the book of record. USD figure = INR figure / rate, rounded to cents, line by line; totals are converted
from the INR total, so totals can differ from the sum of lines by a cent (footnote says so). Rate:
`GET https://api.frankfurter.dev/v1/{date}?base=USD&symbols=INR` (ECB reference rates; a weekend date returns the
previous business day). Fallback source if serverless cannot reach it: the ECB daily file, crossed through EUR.

## Sending (Microsoft Graph)

`POST https://graph.microsoft.com/v1.0/users/{MAIL_SENDER}/sendMail` with an app token (client credentials,
`Mail.Send` application permission, separate Entra app `bank-etl-mailer`). Body `contentType: HTML`, two
`fileAttachment` items, `saveToSentItems: true`. Limited to the shared mailbox by an Exchange application access
policy. Retries on 429/5xx. Setup steps: `docs/cookbook/graph-mail-setup.md`. SMTP AUTH is not used: it needs a
mailbox password and Microsoft is phasing out basic authentication for it.

## Recipients and config (.env now, secret scope later)

| Variable | Meaning |
|---|---|
| `MAIL_CLIENT_ID`, `MAIL_CLIENT_SECRET` | the mailer app (tenant id reuses `SP_TENANT_ID`) |
| `MAIL_SENDER` | the shared mailbox address, the From: `noreply@<domain>` (decided 2026-10-24 while sending as `finance-reports` still returned 403 from Graph) |
| `MAIL_REPLY_TO` | `finance-reports@<domain>`, a mailbox people read, so a reply is not lost |
| `MAIL_RECIPIENTS` | `address|Display Name` entries separated by commas |
| `MAIL_MODE` | `dry` (default, owner only) or `live` |
| `MAIL_DRY_RUN_TO` | the owner's address, used in dry mode |

Parsing: split on commas, then on the first `|`; address must contain one `@`; display name may be empty; no commas inside names. Any invalid entry fails the run before sending. `make secrets` later copies them to the scope as `mail_*`.

## Email (HTML body, INR by default)

Body currency comes from `report_body_currency` in `config/settings.yaml` (`INR` default, or `USD`). The USD PDF and the rate always exist, so USD is one setting away. Subject `ConceptLabs weekly cash report · 12–18 Oct 2026`. Header with the ConceptLabs logo (inline image), a notice if the week's bank statement has not arrived, balance tiles, money out by category, largest movements, upcoming payments (14 days), review count, a footnote (in an INR body: which rate the USD PDF uses; in a USD body: the rate and its date), footer with the attachment names. Inline CSS and tables only; palette `emerald` by default. PDFs: `conceptlabs-weekly-cash-report-YYYY-MM-DD-usd.pdf` and `-inr.pdf`, one or two pages, every payment of the week, no account number.

## Renderer

`src/weekly_report.py`: pure functions from view rows to HTML and PDF (`reportlab`). `src/graph_mail.py`: token, `sendMail`, retries, recipient parser. Both unit tested without network.

## History and reproducibility

Gold is rebuilt every run, so category labels and rules always show the latest. A past week recomputed later could differ
from what was emailed. The snapshot tables are append-only: they hold the week's figures at send time. A resend renders from
the latest snapshot version; `force=true` creates a new version and keeps the old one. The PDFs themselves are not stored in
Databricks (raw files stay out); the mailbox's Sent Items holds the emails. Delta time travel is only a short-term safety net.

## Dashboard: cash flow by date range (built 2026-10-24)

Page **Cash flow by date** in the ConceptLabs Finance dashboard: one date-range filter on the field `txn_date` that drives three
counters (money in, money out, net), a weekly money in/out chart, a daily closing balance line, money out by category with its
table, and the list of payments in the range. Datasets are `gold.cashflow_daily` and `gold.balance_daily` (SQL views over
`gold.fact_transactions`). Checked: 1 to 18 Oct 2026 gives money in 25,116.00, money out 68,849.85, net -43,733.85, equal to SQL.
A **Weekly trend** page from the snapshot tables comes with M4.
