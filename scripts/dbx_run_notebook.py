"""Upload one notebook from databricks/jobs/ and run it once on serverless compute; print its exit value.

    python scripts/dbx_run_notebook.py s0_sharepoint_check
"""
from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def main(name: str) -> int:
    load_dotenv(ROOT / ".env")
    WS = f"/Users/{os.environ['DATABRICKS_USER']}/bank-etl/jobs"
    host = os.environ["DATABRICKS_HOST"].strip().rstrip("/")
    host = host if host.startswith("http") else "https://" + host
    h = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}"}
    api = lambda m, p, **kw: httpx.request(m, f"{host}{p}", headers=h, timeout=60, **kw)
    api("POST", "/api/2.0/workspace/mkdirs", json={"path": WS})
    src = (ROOT / "databricks" / "jobs" / f"{name}.py").read_bytes()
    r = api("POST", "/api/2.0/workspace/import", json={"path": f"{WS}/{name}", "format": "SOURCE", "language": "PYTHON",
                                                          "overwrite": True, "content": base64.b64encode(src).decode()})
    assert r.status_code == 200, r.text[:200]
    run = api("POST", "/api/2.1/jobs/runs/submit", json={"run_name": name, "tasks": [
        {"task_key": "t", "notebook_task": {"notebook_path": f"{WS}/{name}"}}]}).json()["run_id"]
    while True:
        st = api("GET", "/api/2.1/jobs/runs/get", params={"run_id": run}).json()
        if st["state"]["life_cycle_state"] in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            break
        time.sleep(5)
    out = api("GET", "/api/2.1/jobs/runs/get-output", params={"run_id": st["tasks"][0]["run_id"]}).json()
    print("result:", st["state"].get("result_state"), st["state"].get("state_message", "")[:200])
    print(out.get("notebook_output", {}).get("result") or out.get("error", ""))
    return 0 if st["state"].get("result_state") == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
