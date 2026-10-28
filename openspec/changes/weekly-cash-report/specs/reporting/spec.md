# Spec delta: reporting — weekly cash report email

## ADDED Requirements

### Requirement: One report per week

The job SHALL send at most one report per `week_end` unless started with `force=true`. Every send SHALL be recorded in `gold.report_log`.

#### Scenario: Rerun
- **WHEN** the job runs again for a week already logged as sent
- **THEN** no email is sent and the run ends successfully

### Requirement: Body currency is a setting, attachments in both

The HTML body SHALL show every amount in the currency set by `report_body_currency` (default INR). The email SHALL carry two PDF attachments with the same report, one in USD and one in INR.

### Requirement: One stated exchange rate per report

USD amounts SHALL use one USD/INR rate: the latest published on or before `week_end`. The USD PDF, and the body when it is in USD, SHALL state the rate and its date; an INR body SHALL say which rate the USD PDF uses. The rate SHALL be stored in `gold.fx_rates` and reused on reruns.

#### Scenario: Weekend report date
- **WHEN** `week_end` is a Sunday
- **THEN** the rate dated the previous business day is used and its date is shown

### Requirement: The report is deterministic

Every figure SHALL come from gold SQL. No model SHALL write or alter report content.

### Requirement: Dry run before live

When `MAIL_MODE` is `dry` the report SHALL be sent only to `MAIL_DRY_RUN_TO`. Live mode SHALL send to `MAIL_RECIPIENTS`.

### Requirement: Recipient list is validated

`MAIL_RECIPIENTS` SHALL be `address|Display Name` entries separated by commas. An invalid entry SHALL fail the run before any message is sent.

### Requirement: Send-only, single-mailbox access

The mail app SHALL hold only `Mail.Send` (application) and SHALL be limited by an Exchange application access policy to the sender mailbox.

### Requirement: Privacy of content and logs

The email and PDFs SHALL NOT contain an account number or the bank's password. Logs SHALL NOT contain secrets or recipient addresses.

### Requirement: On-demand run

The job SHALL accept `week_end`, `force` and `mode` parameters so it can be run at any time.

### Requirement: Late statement notice

If no weekly or monthly statement covers the end of the week yet, the report SHALL still be sent with a notice that the statement has not been received.

### Requirement: Every report is kept as sent

The job SHALL write the week's figures to `gold.weekly_cash_snapshot` and `gold.weekly_cash_snapshot_lines` (append-only) before sending, and SHALL render the email and PDFs from that snapshot. A forced rerun SHALL add a new version and keep the earlier one.

#### Scenario: Rules change later
- **WHEN** a payee rule or label changes after a report was sent
- **THEN** the stored snapshot of that report is unchanged

### Requirement: Cash flow can be viewed for any date range

The dashboard SHALL offer a date-range filter that narrows the money in, money out, net change, charts and payment list to the chosen days.
