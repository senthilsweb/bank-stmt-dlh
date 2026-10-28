"""Read statement PDFs from one SharePoint folder through Microsoft Graph. Used by the Databricks ingest notebook.

The Entra app holds only Files.SelectedOperations.Selected with a read grant on the statements folder, so it cannot
look up sites or paths. The caller passes the drive id and the folder item id (both fixed in config, found once by
the admin; see docs/cookbook/sharepoint-source-setup.md).

Same two calls as minio_reader: list the PDFs, download one. 429 and 5xx answers are retried with backoff and
Retry-After is honoured; a 401 refreshes the token once. Secrets are never printed or put in error text.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import httpx

GRAPH = "https://graph.microsoft.com/v1.0"
LOGIN = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
RETRY_STATUS = {429, 500, 502, 503, 504}


class GraphError(RuntimeError):
    pass


class SharePoint:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, drive_id: str, folder_id: str,
                 http: httpx.Client | None = None, tries: int = 4, base_delay: float = 2.0):
        self._cred = (tenant_id, client_id, client_secret)
        self.drive_id, self.folder_id = drive_id, folder_id
        self.http = http or httpx.Client(timeout=60, follow_redirects=True)
        self.tries, self.base_delay = tries, base_delay
        self._token: str | None = None

    def _auth(self, force: bool = False) -> dict:
        if force or not self._token:
            tenant, cid, secret = self._cred
            r = self.http.post(LOGIN.format(tenant=tenant), data={
                "grant_type": "client_credentials", "client_id": cid, "client_secret": secret,
                "scope": "https://graph.microsoft.com/.default"})
            if r.status_code != 200:
                raise GraphError(f"token request failed: HTTP {r.status_code}")
            self._token = r.json()["access_token"]
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, url: str):
        refreshed = False
        for i in range(self.tries):
            r = self.http.get(url, headers=self._auth())
            if r.status_code == 401 and not refreshed:
                self._auth(force=True)
                refreshed = True
                continue
            if r.status_code in RETRY_STATUS and i < self.tries - 1:
                time.sleep(float(r.headers.get("Retry-After") or self.base_delay * 2**i))
                continue
            if r.status_code != 200:
                raise GraphError(f"Graph GET failed: HTTP {r.status_code}")
            return r
        raise GraphError("Graph GET failed: out of retries")

    def list_pdfs(self) -> list[dict]:
        """[{object_key, etag, size_bytes, item_id}] for every PDF directly in the folder, sorted by name."""
        out, url = [], f"{GRAPH}/drives/{self.drive_id}/items/{self.folder_id}/children?$top=200"
        while url:
            body = self._get(url).json()
            out += [
                {"object_key": x["name"], "etag": x.get("eTag", "").strip('"'), "size_bytes": int(x.get("size", 0)), "item_id": x["id"]}
                for x in body.get("value", [])
                if "file" in x and x["name"].lower().endswith(".pdf")
            ]
            url = body.get("@odata.nextLink")
        return sorted(out, key=lambda o: o["object_key"])

    def subfolders(self) -> dict[str, str]:
        """{folder name: item id} for the sub-folders directly inside the configured folder."""
        out, url = {}, f"{GRAPH}/drives/{self.drive_id}/items/{self.folder_id}/children?$top=200"
        while url:
            body = self._get(url).json()
            out.update({x["name"]: x["id"] for x in body.get("value", []) if "folder" in x})
            url = body.get("@odata.nextLink")
        return out

    def download(self, item: dict, dest: Path) -> str:
        """Download the item to dest and return the SHA-256 of the file."""
        r = self._get(f"{GRAPH}/drives/{self.drive_id}/items/{item['item_id']}/content")
        dest.write_bytes(r.content)
        return hashlib.sha256(r.content).hexdigest()
