# Databricks notebook source
# MAGIC %md
# MAGIC # M0 feasibility: can serverless Databricks send the weekly cash report?
# MAGIC
# MAGIC **Why this notebook exists.** The `weekly-cash-report` change sends an email through Microsoft Graph and converts INR to USD with a public rate API. Before building the report, this one-off checks from serverless compute that:
# MAGIC 1. the mailer app signs in and Graph accepts one plain test message from the sender mailbox to the dry-run address only;
# MAGIC 2. the rate API answers for USD to INR, including a weekend date;
# MAGIC 3. the sender mailbox is accepted and no other mailbox is needed.
# MAGIC
# MAGIC **Safe to rerun.** Sends one short test mail with no data to `mail_dry_run_to` (the owner). Reports statuses only; never secrets or addresses. Spec: `openspec/changes/weekly-cash-report` (bolt M0).

# COMMAND ----------

import requests

import sys
from pathlib import Path
BASE = "/Workspace" + str(Path(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()).parents[1])  # the deployed repo root
sys.path.insert(0, f"{BASE}/src")
import settings as _settings
S = _settings.load()
CAT, SCOPE = S["catalog"], S["secret_scope"]
g = lambda k: dbutils.secrets.get(SCOPE, k)
tenant, cid, csec = g("sp_tenant_id"), g("mail_client_id"), g("mail_client_secret")
sender, to = g("mail_sender"), g("mail_dry_run_to").split("|")[0].strip()
report = []

# COMMAND ----------

try:
    t = requests.post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", timeout=30, data={
        "grant_type": "client_credentials", "client_id": cid, "client_secret": csec, "scope": "https://graph.microsoft.com/.default"})
    report.append(f"token: HTTP {t.status_code}")
    msg = {"message": {"subject": "bank-etl M0 test from Databricks", "body": {"contentType": "Text",
           "content": "Test message sent by a Databricks serverless job (bolt M0). No data, nothing to do."},
           "toRecipients": [{"emailAddress": {"address": to}}]}, "saveToSentItems": True}
    r = requests.post(f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail", headers={"Authorization": "Bearer " + t.json()["access_token"]}, json=msg, timeout=30)
    report.append(f"sendMail: HTTP {r.status_code}" + (f" {r.json().get('error', {}).get('code', '')}" if r.status_code >= 300 else ""))
except Exception as e:  # noqa: BLE001 - the report must say where it stopped
    report.append(f"MAIL STOPPED: {type(e).__name__}: {str(e)[:120]}")

# COMMAND ----------

try:
    for day in ("2026-10-16", "2026-10-17"):  # a Friday and the Saturday after it
        x = requests.get(f"https://api.frankfurter.dev/v1/{day}?base=USD&symbols=INR", timeout=20)
        j = x.json()
        report.append(f"rate {day}: HTTP {x.status_code}, rate date {j.get('date')}, INR per USD {j.get('rates', {}).get('INR')}")
except Exception as e:  # noqa: BLE001
    report.append(f"RATE STOPPED: {type(e).__name__}: {str(e)[:120]}")

# COMMAND ----------

dbutils.notebook.exit(" | ".join(report))
