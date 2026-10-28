import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import graph_mail as gm  # noqa: E402


def mailer(handler, **kw):
    return gm.GraphMail("tenant", "cid", "secret", "sender@example.com", http=httpx.Client(transport=httpx.MockTransport(handler)), base_delay=0, **kw)


def token(req):
    return httpx.Response(200, json={"access_token": "tok"})


def test_parse_recipients():
    got = gm.parse_recipients("a@x.com|Name A, b@y.com|Name B ,c@z.com")
    assert got == [gm.Recipient("a@x.com", "Name A"), gm.Recipient("b@y.com", "Name B"), gm.Recipient("c@z.com", "")]


@pytest.mark.parametrize("bad", ["", "   ", "nope", "a@b@c.com", "a b@x.com", "@x.com", "ok@x.com,broken"])
def test_parse_recipients_rejects_bad_entries_without_echoing_them(bad):
    with pytest.raises(gm.MailError) as e:
        gm.parse_recipients(bad)
    assert "broken" not in str(e.value) and "nope" not in str(e.value)


def test_send_builds_html_message_with_inline_and_pdf_attachments():
    seen = {}

    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            return token(req)
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["Authorization"], json.loads(req.content)
        return httpx.Response(202)

    atts = [gm.attachment("logo.png", b"png", "image/png", "logo-white"), gm.attachment("r-usd.pdf", b"%PDF-", "application/pdf")]
    status = mailer(handler).send([gm.Recipient("a@x.com", "A")], "Subject", "<p>hi</p>", atts, reply_to="r@x.com")
    b = seen["body"]
    assert status == 202 and seen["url"].endswith("/users/sender@example.com/sendMail") and seen["auth"] == "Bearer tok"
    assert b["saveToSentItems"] is True and b["message"]["body"] == {"contentType": "HTML", "content": "<p>hi</p>"}
    assert b["message"]["toRecipients"] == [{"emailAddress": {"address": "a@x.com", "name": "A"}}]
    assert b["message"]["replyTo"] == [{"emailAddress": {"address": "r@x.com"}}]
    assert b["message"]["attachments"][0]["isInline"] is True and b["message"]["attachments"][0]["contentId"] == "logo-white"
    assert "isInline" not in b["message"]["attachments"][1]


def test_retries_429_then_sends():
    n = {"c": 0}

    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            return token(req)
        n["c"] += 1
        return httpx.Response(429, headers={"Retry-After": "0"}) if n["c"] < 3 else httpx.Response(202)

    assert mailer(handler).send([gm.Recipient("a@x.com")], "s", "h", []) == 202 and n["c"] == 3


def test_403_raises_with_code_but_no_secret_or_address():
    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            return token(req)
        return httpx.Response(403, json={"error": {"code": "ErrorAccessDenied", "message": "a@x.com secret"}})

    with pytest.raises(gm.MailError) as e:
        mailer(handler).send([gm.Recipient("a@x.com")], "s", "h", [])
    assert str(e.value) == "sendMail failed: HTTP 403 ErrorAccessDenied"


def test_401_refreshes_token_once():
    seen = {"t": 0}

    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            seen["t"] += 1
            return httpx.Response(200, json={"access_token": f"tok{seen['t']}"})
        return httpx.Response(401) if req.headers["Authorization"] == "Bearer tok1" else httpx.Response(202)

    assert mailer(handler).send([gm.Recipient("a@x.com")], "s", "h", []) == 202 and seen["t"] == 2


def test_oversized_attachments_are_refused_before_any_call():
    def handler(req):
        raise AssertionError("no network call expected")

    big = gm.attachment("big.pdf", b"x" * 2_500_000, "application/pdf")
    with pytest.raises(gm.MailError, match="larger"):
        mailer(handler).send([gm.Recipient("a@x.com")], "s", "h", [big])
