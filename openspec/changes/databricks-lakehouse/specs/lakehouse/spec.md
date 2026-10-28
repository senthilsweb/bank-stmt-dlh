# Spec delta: lakehouse — catalog, layers and merge

## ADDED Requirements

### Requirement: Dedicated catalog with three layers

A new Unity Catalog catalog SHALL hold schemas `bronze`, `silver` and `gold`. No table of this project SHALL live in another catalog.

### Requirement: Silver merge is idempotent

`silver.transactions` SHALL be written with `MERGE` on `txn_id`. Running the job twice on the same input SHALL leave identical tables.

### Requirement: Gold is rebuilt from silver and reference tables

Every gold table SHALL be derivable from silver plus the reference tables (`dim_category`, `payee_map`, `category_rules`, `recurring_declared`, `jev_labels`). Rebuilding gold from scratch SHALL give the same rows.

### Requirement: Reference data comes from git

`dim_category`, `payee_map`, `category_rules` and `recurring_declared` SHALL be loaded from `config/*.yaml` at deploy time. Editing them in the workspace SHALL NOT be the way to change them.

### Requirement: Local parity

The local DuckDB pipeline and the Databricks job SHALL call the same Python functions for parse, normalize and categorize.

#### Scenario: Parity
- **WHEN** both run on the same 10 statements
- **THEN** transaction count, `txn_id` set, totals per month and totals per category are equal
