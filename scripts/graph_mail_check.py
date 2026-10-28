"""Send one plain test mail through Microsoft Graph from MAIL_SENDER to MAIL_DRY_RUN_TO only (no data, no attachment).

    python scripts/graph_mail_check.py                 # send as MAIL_SENDER
    python scripts/graph_mail_check.py --as OTHER@x    # expect HTTP 403 when the access policy is in place

Prints the HTTP status only; never the secret, token or addresses of other people.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str]) -> int:
    e = dotenv_values(ROOT / ".env")
    sender = argv[argv.index("--as") + 1] if "--as" in argv else e["MAIL_SENDER"].strip()
    to = (e.get("MAIL_DRY_RUN_TO") or "").split("|")[0].strip()  # accepts "address" or "address|Display Name"
    if "@" not in to:
        print("MAIL_DRY_RUN_TO is empty or not an address")
        return 2
    tok = httpx.post(f"https://login.microsoftonline.com/{e['SP_TENANT_ID'].strip()}/oauth2/v2.0/token", timeout=30, data={
        "grant_type": "client_credentials", "client_id": e["MAIL_CLIENT_ID"].strip(), "client_secret": e["MAIL_CLIENT_SECRET"].strip(),
        "scope": "https://graph.microsoft.com/.default"})
    if tok.status_code != 200:
        print("token failed: HTTP", tok.status_code)
        return 1
    msg = {"message": {"subject": "bank-etl mail test", "body": {"contentType": "Text", "content": "Test message from the bank-etl weekly cash report setup. No data, nothing to do."},
                       "toRecipients": [{"emailAddress": {"address": to}}],
                       **({"replyTo": [{"emailAddress": {"address": e["MAIL_REPLY_TO"].strip()}}]} if e.get("MAIL_REPLY_TO") else {})},
           "saveToSentItems": True}
    r = httpx.post(f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail", headers={"Authorization": "Bearer " + tok.json()["access_token"]}, json=msg, timeout=30)
    err = ""
    if r.status_code >= 300:
        err = r.json().get("error", {}).get("code", "")
    print(f"sendMail as {'MAIL_SENDER' if '--as' not in argv else 'other mailbox'}: HTTP {r.status_code} {err}")
    return 0 if r.status_code == 202 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
