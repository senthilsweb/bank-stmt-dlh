"""Run a .sql file on the Databricks SQL warehouse named in .env.

    python databricks/run_sql.py databricks/sql/00_init.sql

Statements are split on ';' and run one by one. Needs DATABRICKS_HOST,
DATABRICKS_TOKEN and DATABRICKS_HTTP_PATH. Prints status only, never the token.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import settings  # noqa: E402


def statements(sql: str) -> list[str]:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def main(path: str) -> int:
    load_dotenv(ROOT / ".env")
    host = os.environ["DATABRICKS_HOST"].strip().rstrip("/")
    if not host.startswith("http"):
        host = "https://" + host
    headers = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}"}
    warehouse = os.environ["DATABRICKS_HTTP_PATH"].rstrip("/").split("/")[-1]
    failed = 0
    catalog = os.environ.get("DATABRICKS_CATALOG") or settings.load()["catalog"]
    for stmt in statements(Path(path).read_text().replace("__CATALOG__", catalog)):
        body = {"warehouse_id": warehouse, "statement": stmt, "wait_timeout": "50s", "on_wait_timeout": "CONTINUE"}
        r = httpx.post(f"{host}/api/2.0/sql/statements", headers=headers, json=body, timeout=90).json()
        while r.get("status", {}).get("state") in ("PENDING", "RUNNING"):
            time.sleep(3)
            r = httpx.get(f"{host}/api/2.0/sql/statements/{r['statement_id']}", headers=headers, timeout=60).json()
        state = r.get("status", {}).get("state")
        err = r.get("status", {}).get("error", {}).get("message", "")
        print(f"{state:9} {stmt.splitlines()[0][:90]}" + (f"\n          {err}" if err else ""))
        failed += state != "SUCCEEDED"
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
