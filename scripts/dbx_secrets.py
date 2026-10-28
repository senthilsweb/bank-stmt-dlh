"""Copy selected .env values into the Databricks secret scope (`secret_scope` in config/settings.yaml). Values are never printed.

    python scripts/dbx_secrets.py                 # every group: core (pdf password, Jev key), sp, minio, mail
    python scripts/dbx_secrets.py mail            # one group (core | sp | minio | mail)
    python scripts/dbx_secrets.py SP_TENANT_ID    # only the named .env keys

An empty value is skipped. It counts as a failure only when its group is needed: core and mail always, and the
statement source named in settings.yaml (sp or minio).

Secret key = the .env name in lower case (SP_CLIENT_ID -> sp_client_id).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import settings  # noqa: E402

S = settings.load()
SCOPE = S["secret_scope"]
GROUPS = {
    "core": ["PDF_PASSWORD", "TYPESAFE_API_KEY"],
    "sp": ["SP_TENANT_ID", "SP_CLIENT_ID", "SP_CLIENT_SECRET", "SP_DRIVE_ID", "SP_FOLDER_ID"],
    "minio": ["MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"],
    "mail": ["MAIL_CLIENT_ID", "MAIL_CLIENT_SECRET", "MAIL_SENDER", "MAIL_REPLY_TO", "MAIL_RECIPIENTS", "MAIL_DRY_RUN_TO", "MAIL_MODE"],
}
OPTIONAL = {"MAIL_REPLY_TO", "TYPESAFE_API_KEY"}   # may stay empty
# the statement source that is not configured may be left empty; the configured one must be filled
REQUIRED_GROUPS = {"core", "mail", "sp" if S["statement_source"] == "sharepoint" else "minio"}


def main(keys: list[str]) -> int:
    load_dotenv(ROOT / ".env")
    env = dotenv_values(ROOT / ".env")
    host = os.environ["DATABRICKS_HOST"].strip().rstrip("/")
    host = host if host.startswith("http") else "https://" + host
    h = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}"}
    bad = 0
    groups = [g for g in keys if g in GROUPS] or list(GROUPS)
    wanted = [k for k in keys if k not in GROUPS] or [k for g in groups for k in GROUPS[g]]
    for k in wanted:
        v = env.get(k, "")
        if not v:
            group = next(g for g, ks in GROUPS.items() if k in ks)
            needed = group in REQUIRED_GROUPS and k not in OPTIONAL
            print(f"{k.lower():24} SKIPPED (empty in .env{'' if needed else ', optional'})")
            bad += needed
            continue
        r = httpx.post(f"{host}/api/2.0/secrets/put", headers=h, json={"scope": SCOPE, "key": k.lower(), "string_value": v}, timeout=30)
        print(f"{k.lower():24} {'ok' if r.status_code == 200 else 'FAILED ' + str(r.status_code)}")
        bad += r.status_code != 200
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
