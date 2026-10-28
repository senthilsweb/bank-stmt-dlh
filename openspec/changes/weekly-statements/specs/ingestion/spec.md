# Spec delta: ingestion — weekly and monthly statements

## MODIFIED Requirements

### Requirement: A line item has one identity across statements

A line item SHALL be identified by its date, reference number, amount and running balance. Its narration SHALL
NOT be part of the identity.

#### Scenario: Same line printed differently
- **WHEN** a weekly and a monthly statement contain the same line with different narration text
- **THEN** one transaction exists in `silver.transactions` and the monthly narration is the one kept

## ADDED Requirements

### Requirement: Repeated line items are tagged, not dropped silently

Every appearance of a line item in a statement SHALL be recorded in `silver.transaction_sources`. Each appearance after
the first SHALL have `is_duplicate = true` and name the file it duplicates.

#### Scenario: Weekly after monthly
- **WHEN** a weekly statement whose lines are all in loaded monthly statements is ingested
- **THEN** its lines are recorded as duplicates, `silver.transactions` is unchanged, and the run reports the duplicate count

#### Scenario: Order does not matter
- **WHEN** the weekly statements are ingested before the monthly ones
- **THEN** silver.transactions is the same as when they are ingested after

### Requirement: Month-end figures come from monthly statements

Month-end balances and the statement list SHALL use statements with `statement_kind = 'monthly'` only.

### Requirement: A key must not repeat inside one file

If a `txn_id` occurs twice in one statement the file SHALL be quarantined with reason "key collision".
