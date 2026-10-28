# Spec delta: dashboard — deterministic reporting in Databricks

## ADDED Requirements

### Requirement: Dashboard reads gold with SQL only

Every dataset of the dashboard SHALL be a SQL query on `gold` tables or views. It SHALL NOT call a model or an external service.

### Requirement: Pages

The dashboard SHALL have pages Overview, Spend, Recurring and yearly, Funding and founder, and Data quality.

### Requirement: Figures are defined

Cash SHALL be the closing balance of the latest transaction. Monthly outflow SHALL be the mean of total debits (founder payouts included) over the last three full months. Runway SHALL be cash divided by monthly outflow. The dashboard SHALL state these definitions.

### Requirement: Partial months are marked

A month that is not complete SHALL be marked as partial in charts and SHALL NOT enter the monthly outflow average.

### Requirement: Data quality is visible

The Data quality page SHALL show, per statement, whether it reconciled, and the counts and amounts of `unclassified` and `human-intervention-required` rows.

### Requirement: Dashboard is code

The dashboard definition SHALL be in the bundle and SHALL deploy from git.
