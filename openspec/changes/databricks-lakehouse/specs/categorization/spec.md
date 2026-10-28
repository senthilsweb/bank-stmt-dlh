# Spec delta: categorization — rules first, Jev only for leftovers

## ADDED Requirements

### Requirement: Fixed order of decision

A transaction SHALL be categorized by, in order: payee map (with direction and date limits), rules, founder logic, stored Jev label, new Jev call, then `unclassified` or `human-intervention-required`. The first that decides wins.

### Requirement: Jev is bounded

Jev SHALL be called only for transactions that nothing earlier decided. The request SHALL contain only the cleaned counterparty, channel and direction. A label SHALL be accepted only when `confidence >= jev_confidence_threshold`.

#### Scenario: Low confidence
- **WHEN** Jev answers with confidence 0.6 for a debit of 800
- **THEN** the row becomes `unclassified` and nothing is written to `jev_labels`

### Requirement: Jev answers are cached

An accepted label SHALL be stored in `gold.jev_labels` keyed by the request text. The same request SHALL NOT be sent again.

### Requirement: Nothing is silently dropped

Every transaction SHALL end with a category. A row that is unlabelled and either at or above `review_amount_threshold` or a credit SHALL be `human-intervention-required`. Other unlabelled rows SHALL be `unclassified`.

### Requirement: Every label shows its source

Each row SHALL carry `category_source` (`map`, `rule`, `founder`, `jev`, `unclassified`, `review`) and `category_confidence`.
