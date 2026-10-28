import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import dedupe  # noqa: E402

NOW = datetime(2026, 10, 24)


def lines(*rows):
    return pd.DataFrame(rows, columns=["seq", "txn_date", "narration", "ref_no", "value_date", "amount", "balance", "direction"])


A = (1, "05/10/26", "UPI-ACME LTD-X@Y", "0000611201168153", "05/10/26", 1999.00, 65888.75, "debit")
A_WEEKLY_TEXT = (1, "05/10/26", "UPI-ACME LTD", "0000611201168153", "05/10/26", 1999.00, 65888.75, "debit")
B = (2, "05/10/26", "UPI-ACME LTD-X@Y", "0000611201168153", "05/10/26", 1999.00, 63889.75, "debit")  # same look, lower balance


def prep(rows, name, kind):
    return dedupe.prepare(lines(*rows), name, name, kind)


def test_identity_ignores_narration_but_not_balance():
    m, w = prep([A], "m.pdf", "monthly"), prep([A_WEEKLY_TEXT], "w.pdf", "weekly")
    assert m.txn_id[0] == w.txn_id[0]
    assert prep([A, B], "m.pdf", "monthly").txn_id.nunique() == 2


def test_weekly_after_monthly_is_all_duplicate():
    m, w = prep([A, B], "m.pdf", "monthly"), prep([A_WEEKLY_TEXT], "w.pdf", "weekly")
    app, rows = dedupe.resolve([m, w], {}, {}, NOW)
    assert list(app.is_duplicate) == [False, False, True] and app.duplicate_of_file.iloc[2] == "m.pdf"
    assert len(rows) == 2 and set(rows.statement_kind) == {"monthly"}


def test_order_does_not_change_silver():
    m, w = prep([A, B], "m.pdf", "monthly"), prep([A_WEEKLY_TEXT], "w.pdf", "weekly")
    _, r1 = dedupe.resolve([m, w], {}, {}, NOW)
    _, r2 = dedupe.resolve([w, m], {}, {}, NOW)
    key = lambda d: d.sort_values("txn_id")[["txn_id", "narration", "source_file", "statement_kind"]].values.tolist()
    assert key(r1) == key(r2)


def test_monthly_text_replaces_weekly_text_but_not_the_reverse():
    m, w = prep([A], "m.pdf", "monthly"), prep([A_WEEKLY_TEXT], "w.pdf", "weekly")
    _, rows = dedupe.resolve([m], {w.txn_id[0]: "w.pdf"}, {w.txn_id[0]: "weekly"}, NOW)  # weekly already stored
    assert rows.narration.iloc[0] == A[2]
    _, rows = dedupe.resolve([w], {m.txn_id[0]: "m.pdf"}, {m.txn_id[0]: "monthly"}, NOW)  # monthly already stored
    assert rows.empty


def test_collision_inside_one_file():
    assert dedupe.collisions(prep([A, A], "m.pdf", "monthly")) == 1
    assert dedupe.collisions(prep([A, B], "m.pdf", "monthly")) == 0
