# Spec delta: orchestration — when the ETL runs

## ADDED Requirements

### Requirement: New files are picked up on a schedule

The job SHALL run once a day at midnight IST and SHALL process only files in MinIO that are not yet in bronze. `make upload` SHALL start a run right after uploading.

### Requirement: Idle runs are cheap

A run with no new files SHALL finish quickly and change nothing.

### Requirement: Failures are reported

A failed task or a quarantined statement SHALL send an alert to the owner. A quarantine SHALL NOT fail the whole job.

### Requirement: Deploy from git

`databricks bundle deploy` SHALL create or update the schemas, job, trigger and dashboard. Targets `dev` and `prod` SHALL differ only by catalog or schema names and the schedule.

### Requirement: MinIO outage is safe

If MinIO is unreachable, the job SHALL leave all tables unchanged and SHALL alert the owner.
