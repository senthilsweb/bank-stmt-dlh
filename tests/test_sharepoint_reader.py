import hashlib
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import sharepoint_reader as sp  # noqa: E402


def make(handler, **kw):
    http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return sp.SharePoint("tenant", "cid", "secret", "drive1", "folder1", http=http, base_delay=0, **kw)


def token_ok(request):
    return httpx.Response(200, json={"access_token": "tok"})


def test_list_pages_and_filters_pdfs():
    page2 = "https://graph.microsoft.com/v1.0/next"

    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            return token_ok(req)
        assert req.headers["Authorization"] == "Bearer tok"
        if str(req.url) == page2:
            return httpx.Response(200, json={"value": [{"id": "3", "name": "a.PDF", "file": {}, "size": 5, "eTag": '"e3"'}]})
        return httpx.Response(200, json={
            "value": [
                {"id": "1", "name": "02.pdf", "file": {}, "size": 10, "eTag": '"e1"'},
                {"id": "2", "name": "notes.txt", "file": {}, "size": 1, "eTag": '"x"'},
                {"id": "9", "name": "sub", "folder": {}},
            ],
            "@odata.nextLink": page2,
        })

    got = make(handler).list_pdfs()
    assert [o["object_key"] for o in got] == ["02.pdf", "a.PDF"]
    assert got[0] == {"object_key": "02.pdf", "etag": "e1", "size_bytes": 10, "item_id": "1"}


def test_download_returns_sha256_and_follows_redirect(tmp_path):
    body = b"%PDF-1.4 hello"

    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            return token_ok(req)
        if req.url.host == "graph.microsoft.com":
            return httpx.Response(302, headers={"Location": "https://files.example.sharepoint.com/dl"})
        assert "Authorization" not in req.headers  # pre-authenticated URL, token must not follow
        return httpx.Response(200, content=body)

    dest = tmp_path / "x.pdf"
    sha = make(handler).download({"item_id": "1"}, dest)
    assert sha == hashlib.sha256(body).hexdigest() and dest.read_bytes() == body


def test_retries_429_then_succeeds():
    calls = {"n": 0}

    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            return token_ok(req)
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"value": []})

    assert make(handler).list_pdfs() == [] and calls["n"] == 3


def test_401_refreshes_token_once():
    seen = {"tokens": 0, "gets": 0}

    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            seen["tokens"] += 1
            return httpx.Response(200, json={"access_token": f"tok{seen['tokens']}"})
        seen["gets"] += 1
        return httpx.Response(401) if req.headers["Authorization"] == "Bearer tok1" else httpx.Response(200, json={"value": []})

    assert make(handler).list_pdfs() == [] and seen == {"tokens": 2, "gets": 2}


def test_error_text_has_status_not_secret():
    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            return httpx.Response(400, json={"error_description": "secret leaked here"})
        return httpx.Response(200, json={})

    with pytest.raises(sp.GraphError) as e:
        make(handler).list_pdfs()
    assert "HTTP 400" in str(e.value) and "secret" not in str(e.value)


def test_non_retryable_error_raises():
    def handler(req):
        return token_ok(req) if req.url.host == "login.microsoftonline.com" else httpx.Response(403)

    with pytest.raises(sp.GraphError, match="HTTP 403"):
        make(handler).list_pdfs()


def test_subfolders_lists_only_folders():
    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            return token_ok(req)
        return httpx.Response(200, json={"value": [
            {"id": "m1", "name": "01 MONTHLY STATEMENTS", "folder": {}},
            {"id": "w1", "name": "02 WEEKLY STATEMENTS", "folder": {}},
            {"id": "f1", "name": "readme.pdf", "file": {}}]})

    assert make(handler).subfolders() == {"01 MONTHLY STATEMENTS": "m1", "02 WEEKLY STATEMENTS": "w1"}
