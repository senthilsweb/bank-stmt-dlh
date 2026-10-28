# Design — weekly-statements

## Line-item key

`txn_id = sha1(date | ref_no | amount | balance)[:16]`. Narration is dropped because the weekly and monthly PDFs
print it differently for some lines. The running balance makes equal-looking transactions distinct and is the
same figure in every statement that contains the line.

## Tables

| Table | Change |
|---|---|
| `bronze.statement_files` | `+ statement_kind STRING` (from the folder) |
| `silver.statements` | `+ statement_kind STRING` |
| `silver.transactions` | one row per line item; `source_file`, `file_sha256`, `narration` come from the preferred appearance (monthly over weekly) |
| `silver.transaction_sources` (new) | `txn_id, file_sha256, source_file, statement_kind, seq, narration, first_seen_at, is_duplicate, duplicate_of_file` — one row per appearance |

`is_duplicate` is false for the first appearance by load time and true for every later one; `duplicate_of_file`
names the first. The monthly appearance replaces the weekly one as the row in `silver.transactions` but keeps
its own flag, so history is not rewritten.

## Ingest flow (notebook 02)

1. List both folders; tag each file `monthly` or `weekly`.
2. Hash, skip known content, parse and reconcile as today.
3. For each parsed line: look up `txn_id` in `silver.transaction_sources`. Found -> insert the appearance with
   `is_duplicate = true`; not found -> insert with false and add the row to `silver.transactions`.
4. If the new appearance is monthly and the existing row came from a weekly file, update the
   `silver.transactions` row's narration, file and sequence from the monthly line.
5. Guard: the same `txn_id` twice inside one file fails that file (quarantine, reason "key collision").
6. Print per file: lines, new, duplicate.

## Views

`monthly_summary`, month-end balance and the statement list read `silver.statements` where
`statement_kind = 'monthly'`. The running month's latest balance may come from the newest weekly statement and is
labelled as such.

## Migration (once)

Rebuild silver from `bronze.raw_lines` with the new key, fill `silver.transaction_sources` for all 10 monthly files,
then run the job with `force=true`. Verify 282 transactions and the earlier totals before loading weekly files.
