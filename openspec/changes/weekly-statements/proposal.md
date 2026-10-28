# Proposal: weekly-statements — read weekly and monthly statements and tag duplicate line items

> Status: **APPROVED** (2026-10-24). (2026-10-24). Follows `sharepoint-source`. Owner: the repo owner.

## Why

Weekly statements (`02 WEEKLY STATEMENTS`) show fresher data inside the running month. They overlap the
monthly statements. Today the pipeline would **silently merge** repeated line items and, worse, miss some.

Measured on the real files (2026-10-24, nothing loaded, counts only):

- All 9 weekly PDFs parse and reconcile with the current parser (57 line items, 17 Aug to 15 Oct).
- All 57 weekly line items also appear in the monthly statements.
- With today's `txn_id` (date, ref, amount, **narration**), only 48 of the 57 match. For 9 items the
  narration text differs between weekly and monthly, so they would be **counted twice**.
- With the bank's running **balance** in the key instead of narration, all 57 match, and there are no
  collisions inside any single file (282 monthly keys, 282 unique).
- Another trap: the monthly views choose "the statement with the latest end date for each month". A weekly
  statement 28 Sep to 4 Oct would win for September and give a wrong month-end balance.

## What changes

- A line item's identity becomes **date + reference + amount + running balance** (no narration).
- Every appearance of a line item in any file is recorded in a new table `silver.transaction_sources`
  (file, statement kind, sequence, narration as printed). The **second and later appearances are tagged
  `is_duplicate = true`**; they never reach `silver.transactions` twice.
- `silver.transactions` keeps one row per line item. Where the weekly and monthly narration differ, the
  **monthly** text wins (it is the final record); until the month closes, the weekly text is used.
- `bronze.statement_files` and `silver.statements` get `statement_kind` (`monthly` | `weekly`), taken from the
  folder. Month-end balances and the statement list use **monthly statements only**.
- Each run prints, per file: line items found, new, duplicate. The dashboard's Data quality tab gets a
  duplicates table (file, count, duplicates of which file).
- The job reads both folders (`SP_MONTHLY_FOLDER_ID`, `SP_WEEKLY_FOLDER_ID`).

## Out of scope

Statements from other accounts; any change to categories or payee decisions; fuzzy matching of lines
whose date, reference, amount and balance all differ.

## Risks

| Risk | Handling |
|---|---|
| Changing the key changes all 282 `txn_id` values | One-off migration: rebuild silver from bronze (`raw_lines` already holds every parsed line), then run gold with `force`. Check that the Jev label cache is keyed on payee text, not `txn_id` (task W0) |
| Two genuinely different transactions with equal date, reference, amount and balance | Not possible: the balance moves after each transaction. A check in the run fails the file if a key repeats inside one file |
| Weekly file for a day the monthly does not yet cover (running month) | Weekly rows are the only appearance, so they are loaded as normal and later become the duplicate side when the monthly arrives |

## Acceptance criteria

1. Loading all 9 weekly files on top of the 10 monthly ones leaves **282** transactions (not 282 + 57 or 291) and totals unchanged.
2. `silver.transaction_sources` holds 339 appearances: 282 first, 57 duplicates, each pointing at the file it duplicates.
3. Loading the weekly files **before** the monthly ones gives the same silver result.
4. Month-end balances in gold equal the bank's monthly closing figures.
5. The run log and the dashboard show the duplicate counts.
