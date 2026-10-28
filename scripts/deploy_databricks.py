"""Upload code, config, SQL and notebooks to the Databricks workspace.

    python scripts/deploy_databricks.py

Workspace layout under /Users/<DATABRICKS_USER>/bank-stmt-dlh: src/ config/ databricks/sql/ (plain files, importable or readable
by the notebooks) and notebooks/ (Databricks notebooks). Prints names only.
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    load_dotenv(ROOT / ".env")
    WS = f"/Users/{os.environ['DATABRICKS_USER']}/bank-stmt-dlh"
    host = os.environ["DATABRICKS_HOST"].strip().rstrip("/")
    host = host if host.startswith("http") else "https://" + host
    h = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}"}
    bad = 0
    with httpx.Client(headers=h, timeout=120) as c:
        # plain files: raw upload, no notebook conversion
        plain = [*(ROOT / "src").glob("*.py"), *(ROOT / "config").glob("*.yaml"), *(ROOT / "databricks" / "sql").glob("*.sql"), *(ROOT / "assets").glob("*.png")]
        for f in sorted(plain):
            rel = f.relative_to(ROOT).as_posix()
            c.post(f"{host}/api/2.0/workspace/mkdirs", json={"path": f"{WS}/{Path(rel).parent.as_posix()}"})
            r = c.post(f"{host}/api/2.0/workspace-files/import-file{WS}/{rel}", params={"overwrite": "true"}, content=f.read_bytes())
            bad += r.status_code not in (200, 204)
            print(f"{'ok' if r.status_code in (200, 204) else 'FAILED ' + str(r.status_code):10} {rel}")
        # notebooks
        c.post(f"{host}/api/2.0/workspace/mkdirs", json={"path": f"{WS}/notebooks"})
        for f in sorted((ROOT / "databricks" / "notebooks").glob("*.py")):
            r = c.post(f"{host}/api/2.0/workspace/import", json={
                "path": f"{WS}/notebooks/{f.stem}", "format": "SOURCE", "language": "PYTHON", "overwrite": True,
                "content": base64.b64encode(f.read_bytes()).decode()})
            bad += r.status_code != 200
            print(f"{'ok' if r.status_code == 200 else 'FAILED ' + str(r.status_code):10} notebooks/{f.stem}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
