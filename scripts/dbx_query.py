"""Run one SQL query on the Databricks warehouse and return rows as dicts (for checks and scripts)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def query(sql: str) -> list[dict]:
    load_dotenv(ROOT / ".env")
    host = os.environ["DATABRICKS_HOST"].strip().rstrip("/")
    host = host if host.startswith("http") else "https://" + host
    h = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}"}
    wh = os.environ["DATABRICKS_HTTP_PATH"].rstrip("/").split("/")[-1]
    r = httpx.post(f"{host}/api/2.0/sql/statements", headers=h, timeout=90,
                   json={"warehouse_id": wh, "statement": sql, "wait_timeout": "50s", "on_wait_timeout": "CONTINUE"}).json()
    while r["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(3)
        r = httpx.get(f"{host}/api/2.0/sql/statements/{r['statement_id']}", headers=h, timeout=60).json()
    if r["status"]["state"] != "SUCCEEDED":
        raise RuntimeError(r["status"].get("error", {}).get("message", r["status"]["state"]))
    cols = [c["name"] for c in r["manifest"]["schema"]["columns"]]
    return [dict(zip(cols, row)) for row in r.get("result", {}).get("data_array", [])]
