import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from extract import SUMMARY, TXN_START, _money  # noqa: E402
from normalize import channel_of, counterparty_of  # noqa: E402


def test_txn_line_parses():
    m = TXN_START.match("04/07/26 UPI-AUTOPAY-OPENAI 0000611201168153 04/07/26 1,999.00 65,888.75")
    assert m and m[1] == "04/07/26" and _money(m[5]) == Decimal("1999.00") and _money(m[6]) == Decimal("65888.75")


def test_summary_line_parses():
    m = SUMMARY.match("83,276.73 20 2 51,927.98 50,001.00 81,349.75")
    assert m and int(m[2]) == 20 and int(m[3]) == 2


def test_channel_and_counterparty():
    assert channel_of("UPI-AUTOPAY-OPENAI LLC-OPENAILLC.CFP@CAS") == "upi-autopay"
    assert channel_of("ME DC SI 403875XXXXXX3427 FRAPPE CLOUD") == "card"
    assert counterparty_of("ME DC SI 403875XXXXXX3427 FRAPPE CLOUD") == "FRAPPE CLOUD"
    assert counterparty_of("UPI-CAFE GOKULAM-PAYTM.S1QJR99@PTY-YESB0") == "CAFE GOKULAM"


def test_merchant_map_matching():
    import re
    import pandas as pd
    from categorize import map_category

    def e(pat, cat, direction=None, frm=None, until=None):
        return {"rx": re.compile(pat, re.I), "category": cat, "direction": direction,
                "from": pd.Timestamp(frm) if frm else None, "until": pd.Timestamp(until) if until else None}

    m = [
        e(r"(?<![A-Z])JOHN DOE(?![A-Z])", "payroll-contractors", until="2026-09-30"),
        e(r"(?<![A-Z])JOHN DOE(?![A-Z])", "payroll-employees", frm="2026-10-01"),
        e(r"(?<![A-Z])JANE ROE(?![A-Z])", "interns"),
        e(r"GLOBEX\s*TECHNO", "client-receipts", "credit"),
    ]
    d = pd.Timestamp
    assert map_category("JOHN DOE V", m, "debit", d("2026-09-30")) == "payroll-contractors"
    assert map_category("JOHN DOE V", m, "debit", d("2026-10-01")) == "payroll-employees"
    assert map_category("JANE ROE", m) == "interns"
    assert map_category("SRI JANE MEDICAL", m) is None          # first name alone is not the payee
    assert map_category("VARASIDDHI JANE BHARATPE", m) is None
    assert map_category("TPT HBFINAL GLOBEX TECHNO LOGY", m, "credit") == "client-receipts"
    assert map_category("TPT HBFINAL GLOBEX TECHNO LOGY", m, "debit") is None
