"""Send mail through Microsoft Graph with an app token (client credentials, Mail.Send). Used by the weekly cash report.

The app is limited by an Exchange application access policy to the sender mailbox. 429 and 5xx answers are retried
with backoff and Retry-After is honoured; a 401 refreshes the token once. Secrets, tokens and addresses are never put
in error text.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import httpx

GRAPH = "https://graph.microsoft.com/v1.0"
LOGIN = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTACHMENT_BYTES = 3_000_000   # Graph's limit for attachments inside one sendMail request


class MailError(RuntimeError):
    pass


@dataclass(frozen=True)
class Recipient:
    address: str
    name: str = ""


def parse_recipients(text: str) -> list[Recipient]:
    """'a@x.com|Name A,b@y.com|Name B' -> recipients. A display name is optional; names contain no commas.

    An invalid entry raises MailError naming only its position, so the whole run fails before anything is sent."""
    out = []
    for i, raw in enumerate(p for p in (text or "").split(",") if p.strip()):
        addr, _, name = raw.partition("|")
        addr, name = addr.strip(), name.strip()
        if addr.count("@") != 1 or addr.startswith("@") or addr.endswith("@") or " " in addr:
            raise MailError(f"recipient {i + 1} is not a valid address")
        out.append(Recipient(addr, name))
    if not out:
        raise MailError("no recipients")
    return out


def attachment(name: str, data: bytes, content_type: str, content_id: str | None = None) -> dict:
    a = {"@odata.type": "#microsoft.graph.fileAttachment", "name": name, "contentType": content_type,
         "contentBytes": base64.b64encode(data).decode()}
    if content_id:
        a.update({"isInline": True, "contentId": content_id})
    return a


class GraphMail:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, sender: str,
                 http: httpx.Client | None = None, tries: int = 4, base_delay: float = 2.0):
        self._cred = (tenant_id, client_id, client_secret)
        self.sender = sender
        self.http = http or httpx.Client(timeout=60)
        self.tries, self.base_delay = tries, base_delay
        self._token: str | None = None

    def _auth(self, force: bool = False) -> dict:
        if force or not self._token:
            tenant, cid, secret = self._cred
            r = self.http.post(LOGIN.format(tenant=tenant), data={
                "grant_type": "client_credentials", "client_id": cid, "client_secret": secret, "scope": "https://graph.microsoft.com/.default"})
            if r.status_code != 200:
                raise MailError(f"token request failed: HTTP {r.status_code}")
            self._token = r.json()["access_token"]
        return {"Authorization": f"Bearer {self._token}"}

    def send(self, to: list[Recipient], subject: str, html: str, attachments: list[dict], reply_to: str | None = None) -> int:
        if sum(len(a["contentBytes"]) for a in attachments) > MAX_ATTACHMENT_BYTES:
            raise MailError("attachments are larger than one sendMail request allows")
        message = {"subject": subject, "body": {"contentType": "HTML", "content": html}, "attachments": attachments,
                   "toRecipients": [{"emailAddress": {"address": t.address, **({"name": t.name} if t.name else {})}} for t in to]}
        if reply_to:
            message["replyTo"] = [{"emailAddress": {"address": reply_to}}]
        payload = {"message": message, "saveToSentItems": True}
        refreshed = False
        for i in range(self.tries):
            r = self.http.post(f"{GRAPH}/users/{self.sender}/sendMail", headers=self._auth(), json=payload)
            if r.status_code == 401 and not refreshed:
                self._auth(force=True)
                refreshed = True
                continue
            if r.status_code in RETRY_STATUS and i < self.tries - 1:
                time.sleep(float(r.headers.get("Retry-After") or self.base_delay * 2**i))
                continue
            if r.status_code != 202:
                code = ""
                try:
                    code = r.json().get("error", {}).get("code", "")
                except Exception:  # noqa: BLE001 - an unreadable error body is reported by status only
                    pass
                raise MailError(f"sendMail failed: HTTP {r.status_code} {code}".strip())
            return r.status_code
        raise MailError("sendMail failed: out of retries")
