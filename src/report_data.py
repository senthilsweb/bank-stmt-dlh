"""Weekly cash report data: week window, figures from the gold tables, and the append-only snapshot.

`query` is any function that takes SQL and returns a list of dicts (Spark in the Databricks job, the SQL-warehouse client
on a laptop), so this module has no Spark or network import and is unit tested with a fake. All amounts stay INR.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Callable

import httpx

import settings
import weekly_report as wr

CAT = settings.load()["catalog"]
Query = Callable[[str], list[dict]]

SNAPSHOT_SCHEMA = ("report_id STRING, week_start DATE, week_end DATE, version INT, mode STRING, opening DOUBLE, closing DOUBLE, money_in_inr DOUBLE, "
                   "money_out_inr DOUBLE, payments INT, rate DOUBLE, rate_date DATE, review_count INT, review_amount_inr DOUBLE, late_statement BOOLEAN, created_at TIMESTAMP")
LINES_SCHEMA = "report_id STRING, kind STRING, rank INT, label STRING, category STRING, line_date DATE, payments INT, amount_inr DOUBLE"
FX_SCHEMA = "rate_date DATE, base STRING, quote STRING, rate DOUBLE, source STRING, fetched_at TIMESTAMP"
LOG_SCHEMA = "report_id STRING, week_end DATE, mode STRING, version INT, sent_at TIMESTAMP, recipient_count INT, rate DOUBLE, rate_date DATE, status STRING, error STRING"

DDL = [f"CREATE TABLE IF NOT EXISTS {CAT}.gold.weekly_cash_snapshot ({SNAPSHOT_SCHEMA})",
       f"CREATE TABLE IF NOT EXISTS {CAT}.gold.weekly_cash_snapshot_lines ({LINES_SCHEMA})",
       f"CREATE TABLE IF NOT EXISTS {CAT}.gold.fx_rates ({FX_SCHEMA})",
       f"CREATE TABLE IF NOT EXISTS {CAT}.gold.report_log ({LOG_SCHEMA})"]


def _f(x) -> float:
    return float(x) if x is not None else 0.0


def _d(x) -> date:
    return x if isinstance(x, date) and not isinstance(x, datetime) else (x.date() if isinstance(x, datetime) else date.fromisoformat(str(x)[:10]))


def _to_et(dt: datetime) -> datetime:
    """Stored timestamps are UTC (naive values from Spark are taken as UTC); the report prints Eastern time."""
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)


def default_week_end(today: date) -> date:
    """The Sunday that ended the week most recently (today, if today is a Sunday). Monday 00:00 ET reports the Sunday just ended."""
    return today - timedelta(days=(today.weekday() + 1) % 7)


def fetch_rate(week_end: date, http: httpx.Client | None = None) -> tuple[float, date]:
    """USD/INR (INR per USD) from the ECB reference rates: the latest published on or before week_end."""
    r = (http or httpx).get(f"https://api.frankfurter.dev/v1/{week_end.isoformat()}", params={"base": "USD", "symbols": "INR"}, timeout=20)
    r.raise_for_status()
    j = r.json()
    return float(j["rates"]["INR"]), date.fromisoformat(j["date"])


def build(query: Query, week_end: date, rate: float, rate_date: date, cat: str = CAT) -> wr.Report:
    start = week_end - timedelta(days=6)
    last_bal = lambda cond: (query(f"select balance from {cat}.gold.fact_transactions where {cond} order by txn_date desc, seq desc limit 1") or [{"balance": 0}])[0]["balance"]
    tot = query(f"select coalesce(sum(case when direction='credit' then amount end),0) i, coalesce(sum(case when direction='debit' then amount end),0) o, count(*) n "
                f"from {cat}.gold.fact_transactions where txn_date between '{start}' and '{week_end}'")[0]
    cats = query(f"select category, count(*) n, sum(amount) a from {cat}.gold.fact_transactions where direction='debit' and txn_date between '{start}' and '{week_end}' group by 1 order by 3 desc")
    tx = query(f"select txn_date, counterparty_clean, category, direction, amount from {cat}.gold.fact_transactions where txn_date between '{start}' and '{week_end}' order by txn_date, seq")
    up = query(f"select payee, next_expected, typical_amount from {cat}.gold.upcoming_payments where status='upcoming' and next_expected between "
               f"'{week_end + timedelta(days=1)}' and '{week_end + timedelta(days=14)}' order by next_expected")
    rv = query(f"select coalesce(sum(txns),0) n, coalesce(sum(amount),0) a from {cat}.gold.review_summary")[0]
    seen = (query(f"select max(period_to) m from {cat}.silver.statements") or [{"m": None}])[0]["m"]
    nice = lambda slug: (slug or "unclassified").replace("-", " ").capitalize()
    return wr.Report(
        week_start=start, week_end=week_end, opening=_f(last_bal(f"txn_date < '{start}'")), closing=_f(last_bal(f"txn_date <= '{week_end}'")),
        money_in=_f(tot["i"]), money_out=_f(tot["o"]), payments=int(_f(tot["n"])), rate=rate, rate_date=rate_date,
        categories=[{"label": nice(c["category"]), "payments": int(_f(c["n"])), "amount": _f(c["a"])} for c in cats],
        movements=[{"date": _d(t["txn_date"]), "payee": t["counterparty_clean"] or "", "category": t["category"] or "",
                    "amount": _f(t["amount"]) * (1 if t["direction"] == "credit" else -1)} for t in tx],
        upcoming=[{"payee": u["payee"], "expected": _d(u["next_expected"]), "amount": _f(u["typical_amount"])} for u in up],
        review_count=int(_f(rv["n"])), review_amount=_f(rv["a"]), late_statement=(seen is None or _d(seen) < week_end))


def report_id(week_end: date, mode: str, version: int) -> str:
    return f"{week_end:%Y%m%d}-{mode}-v{version}"


def to_snapshot(r: wr.Report, version: int, mode: str, now: datetime) -> tuple[dict, list[dict]]:
    rid = report_id(r.week_end, mode, version)
    snap = {"report_id": rid, "week_start": r.week_start, "week_end": r.week_end, "version": version, "mode": mode, "opening": r.opening, "closing": r.closing,
            "money_in_inr": r.money_in, "money_out_inr": r.money_out, "payments": r.payments, "rate": r.rate, "rate_date": r.rate_date,
            "review_count": r.review_count, "review_amount_inr": r.review_amount, "late_statement": r.late_statement, "created_at": now}
    line = lambda kind, rank, label, amount, category=None, day=None, payments=None: {
        "report_id": rid, "kind": kind, "rank": rank, "label": label, "category": category, "line_date": day, "payments": payments, "amount_inr": amount}
    lines = ([line("category", i, c["label"], c["amount"], payments=c["payments"]) for i, c in enumerate(r.categories)]
             + [line("movement", i, m["payee"], m["amount"], category=m["category"], day=m["date"]) for i, m in enumerate(r.movements)]
             + [line("upcoming", i, u["payee"], u["amount"], day=u["expected"]) for i, u in enumerate(r.upcoming)])
    return snap, lines


def from_snapshot(snap: dict, lines: list[dict]) -> wr.Report:
    by = lambda kind: sorted((l for l in lines if l["kind"] == kind), key=lambda l: int(l["rank"]))
    return wr.Report(
        week_start=_d(snap["week_start"]), week_end=_d(snap["week_end"]), opening=_f(snap["opening"]), closing=_f(snap["closing"]),
        money_in=_f(snap["money_in_inr"]), money_out=_f(snap["money_out_inr"]), payments=int(_f(snap["payments"])), rate=_f(snap["rate"]), rate_date=_d(snap["rate_date"]),
        categories=[{"label": l["label"], "payments": int(_f(l["payments"])), "amount": _f(l["amount_inr"])} for l in by("category")],
        movements=[{"date": _d(l["line_date"]), "payee": l["label"], "category": l["category"] or "", "amount": _f(l["amount_inr"])} for l in by("movement")],
        upcoming=[{"payee": l["label"], "expected": _d(l["line_date"]), "amount": _f(l["amount_inr"])} for l in by("upcoming")],
        review_count=int(_f(snap["review_count"])), review_amount=_f(snap["review_amount_inr"]), late_statement=bool(snap["late_statement"]),
        generated_at=_to_et(snap["created_at"]))


def json_safe(x):
    return json.loads(json.dumps(x, default=str))
