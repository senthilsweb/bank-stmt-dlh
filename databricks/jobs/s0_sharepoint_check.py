# Databricks notebook source
# MAGIC %md
# MAGIC # S0 feasibility: can serverless Databricks read the SharePoint statements folder?
# MAGIC
# MAGIC **Why this notebook exists.** The `sharepoint-source` change moves the raw PDFs from MinIO to a SharePoint folder, read through Microsoft Graph. Before building the reader, this one-off checks from serverless compute that:
# MAGIC 1. the Microsoft sign-in host and Graph are reachable (Free Edition may restrict outbound domains);
# MAGIC 2. the app token works with the keys in secret scope `bank-etl`;
# MAGIC 3. the monthly folder lists PDFs and one downloads (the download host is a SharePoint domain);
# MAGIC 4. the app sees nothing outside the granted folder.
# MAGIC
# MAGIC **Safe to rerun.** Read-only. Reports statuses and counts only, never secrets or file contents. Spec: `openspec/changes/sharepoint-source` (bolt S0).

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
tenant, cid, csec = g("sp_tenant_id"), g("sp_client_id"), g("sp_client_secret")
drive, monthly_id = g("sp_drive_id"), g("sp_monthly_folder_id")
GRAPH = "https://graph.microsoft.com/v1.0"
report = []

# COMMAND ----------

try:
    r = requests.post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", timeout=30, data={
        "grant_type": "client_credentials", "client_id": cid, "client_secret": csec, "scope": "https://graph.microsoft.com/.default"})
    report.append(f"1-2 token: HTTP {r.status_code}")
    h = {"Authorization": "Bearer " + r.json()["access_token"]}

    r = requests.get(f"{GRAPH}/drives/{drive}/items/{monthly_id}/children?$top=200", headers=h, timeout=30)
    pdfs = [x for x in r.json().get("value", []) if x["name"].lower().endswith(".pdf")]
    report.append(f"3 list monthly folder: HTTP {r.status_code}, pdfs {len(pdfs)}")

    d = requests.get(f"{GRAPH}/drives/{drive}/items/{pdfs[0]['id']}/content", headers=h, timeout=60, allow_redirects=True)
    report.append(f"3 download: HTTP {d.status_code}, bytes {len(d.content)}, looks like PDF {d.content[:5] == b'%PDF-'}")

    o = requests.get(f"{GRAPH}/drives/{drive}/root/children", headers=h, timeout=30)
    report.append(f"4 drive root entries visible to the app: {len(o.json().get('value', []))} (expect 0)")
except Exception as e:  # noqa: BLE001 - the report must say where it stopped
    report.append(f"STOPPED: {type(e).__name__}: {str(e)[:160]}")

# COMMAND ----------

dbutils.notebook.exit(" | ".join(report))
