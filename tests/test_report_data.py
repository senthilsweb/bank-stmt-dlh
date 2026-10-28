import sys
from datetime import date, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import report_data as rd  # noqa: E402

NOW = datetime(2026, 10, 19, 0, 0)


def fake_query(sql: str) -> list[dict]:
    """Answers each report query with fixed rows (week 12-18 Oct 2026)."""
    if "limit 1" in sql:
        return [{"balance": 240000.0 if "txn_date <" in sql and "<=" not in sql else 221800.0}]
    if "sum(case when direction='credit'" in sql:
        return [{"i": 105000.0, "o": 123200.0, "n": 3}]
    if "group by 1 order by 3 desc" in sql:
        return [{"category": "payroll-contractors", "n": 2, "a": 78000.0}, {"category": None, "n": 1, "a": 1999.0}]
    if "counterparty_clean" in sql:
        return [{"txn_date": date(2026, 10, 13), "counterparty_clean": "CLIENT A", "category": "client-receipts", "direction": "credit", "amount": 100000.0},
                {"txn_date": "2026-10-14", "counterparty_clean": "CONTRACTOR", "category": "payroll-contractors", "direction": "debit", "amount": 45000.0}]
    if "upcoming_payments" in sql:
        return [{"payee": "SOFTWARE", "next_expected": date(2026, 10, 24), "typical_amount": 1999.0}]
    if "review_summary" in sql:
        return [{"n": 2, "a": 6500.0}]
    if "max(period_to)" in sql:
        return [{"m": date(2026, 10, 18)}]
    raise AssertionError(sql)


def test_default_week_end_is_the_sunday_just_ended():
    assert rd.default_week_end(date(2026, 10, 19)) == date(2026, 10, 18)   # Monday 00:00 ET run
    assert rd.default_week_end(date(2026, 10, 18)) == date(2026, 10, 18)   # run on the Sunday itself
    assert rd.default_week_end(date(2026, 10, 22)) == date(2026, 10, 18)   # mid-week on-demand run


def test_build_figures_and_window():
    r = rd.build(fake_query, date(2026, 10, 18), 94.96, date(2026, 10, 16))
    assert (r.week_start, r.week_end) == (date(2026, 10, 12), date(2026, 10, 18))
    assert (r.opening, r.closing, r.money_in, r.money_out, r.payments) == (240000.0, 221800.0, 105000.0, 123200.0, 3)
    assert [c["label"] for c in r.categories] == ["Payroll contractors", "Unclassified"]
    assert [m["amount"] for m in r.movements] == [100000.0, -45000.0] and r.movements[1]["date"] == date(2026, 10, 14)
    assert r.upcoming[0]["expected"] == date(2026, 10, 24) and r.review_count == 2 and r.late_statement is False


def test_late_statement_when_no_statement_reaches_the_week_end():
    q = lambda sql: [{"m": date(2026, 10, 15)}] if "max(period_to)" in sql else fake_query(sql)
    assert rd.build(q, date(2026, 10, 18), 94.96, date(2026, 10, 16)).late_statement is True
    qn = lambda sql: [{"m": None}] if "max(period_to)" in sql else fake_query(sql)
    assert rd.build(qn, date(2026, 10, 18), 94.96, date(2026, 10, 16)).late_statement is True


def test_snapshot_round_trip_reproduces_the_report():
    r = rd.build(fake_query, date(2026, 10, 18), 94.96, date(2026, 10, 16))
    snap, lines = rd.to_snapshot(r, 2, "dry", NOW)
    assert snap["report_id"] == "20261018-dry-v2" and {l["report_id"] for l in lines} == {"20261018-dry-v2"}
    back = rd.from_snapshot(snap, list(reversed(lines)))            # order of rows must not matter
    assert (back.opening, back.closing, back.money_in, back.money_out, back.rate, back.rate_date) == (r.opening, r.closing, r.money_in, r.money_out, r.rate, r.rate_date)
    assert back.categories == r.categories and back.movements == r.movements and back.upcoming == r.upcoming
    assert back.generated_at == datetime(2026, 10, 18, 20, 0) and back.late_statement == r.late_statement   # 2026-10-19 00:00 UTC printed as Eastern (EDT)


def test_fetch_rate_returns_rate_and_its_date_for_a_weekend():
    def handler(req):
        assert req.url.path.endswith("/2026-10-18") and req.url.params["base"] == "USD"
        return httpx.Response(200, json={"base": "USD", "date": "2026-10-16", "rates": {"INR": 94.96}})

    assert rd.fetch_rate(date(2026, 10, 18), httpx.Client(transport=httpx.MockTransport(handler))) == (94.96, date(2026, 10, 16))
