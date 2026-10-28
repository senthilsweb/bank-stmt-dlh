"""Deterministic recurring-payment detection. No AI."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config"

CADENCES = {"weekly": 7, "monthly": 30, "quarterly": 91, "yearly": 365}
TOLERANCE_DAYS = 4
AMOUNT_BAND = 0.15  # an amount is "typical" if within 15% of the median
MIN_TYPICAL_SHARE = 0.7  # at least 70% of occurrences must be typical


def detect(txns: pd.DataFrame, min_occurrences: int = 3) -> pd.DataFrame:
    rows = []
    for (cp, direction), g in txns.groupby(["counterparty_clean", "direction"]):
        g = g.sort_values("txn_date")
        if len(g) < min_occurrences:
            continue
        gaps = g["txn_date"].diff().dt.days.dropna()
        med_gap = gaps.median()
        cadence = next((n for n, d in CADENCES.items() if abs(med_gap - d) <= TOLERANCE_DAYS), None)
        if not cadence:
            continue
        med_amt = g["amount"].median()
        typical = ((g["amount"] - med_amt).abs() <= AMOUNT_BAND * med_amt).mean() if med_amt else 0
        if typical < MIN_TYPICAL_SHARE:
            continue
        last = g["txn_date"].max()
        rows.append(
            {
                "counterparty_clean": cp,
                "direction": direction,
                "cadence": cadence,
                "occurrences": len(g),
                "typical_amount": round(float(med_amt), 2),
                "first_seen": g["txn_date"].min(),
                "last_seen": last,
                "next_expected": last + pd.Timedelta(days=CADENCES[cadence]),
                "category": g["category"].mode().iat[0] if "category" in g else None,
            }
        )
    cols = ["counterparty_clean", "direction", "cadence", "occurrences", "typical_amount",
            "first_seen", "last_seen", "next_expected", "category"]
    return pd.DataFrame(rows, columns=cols).sort_values("typical_amount", ascending=False)


def declared(txns: pd.DataFrame) -> pd.DataFrame:
    """Known repeating payments from config/recurring_declared.yaml (e.g. yearly rent)."""
    f = CONFIG / "recurring_declared.yaml"
    if not f.exists():
        return pd.DataFrame()
    rows = []
    text = txns["counterparty_clean"] + " | " + txns["narration"]
    for d in yaml.safe_load(f.read_text())["declared"]:
        g = txns[(txns["direction"] == "debit") & text.str.contains(d["match"], flags=re.I, regex=True)]
        if g.empty:
            continue
        g = g.sort_values("txn_date")
        last = g["txn_date"].max()
        rows.append(
            {
                "counterparty_clean": d["name"],
                "direction": "debit",
                "cadence": d["cadence"],
                "occurrences": len(g),
                "typical_amount": round(float(g["amount"].iloc[-1]), 2),
                "first_seen": g["txn_date"].min(),
                "last_seen": last,
                "next_expected": last + pd.Timedelta(days=CADENCES[d["cadence"]]),
                "category": g["category"].mode().iat[0] if "category" in g else None,
            }
        )
    return pd.DataFrame(rows)


def ended_patterns() -> list[str]:
    f = CONFIG / "recurring_declared.yaml"
    if not f.exists():
        return []
    return [e["match"] for e in (yaml.safe_load(f.read_text()).get("ended") or [])]
