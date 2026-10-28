import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import weekly_report as wr  # noqa: E402


def sample(**kw):
    base = dict(
        week_start=date(2026, 10, 12), week_end=date(2026, 10, 18), opening=240000.00, closing=221800.00, money_in=105000.00, money_out=123200.00,
        payments=12, rate=94.96, rate_date=date(2026, 10, 16),
        categories=[{"label": "Payroll and contractors", "payments": 3, "amount": 78000.00}, {"label": "Software and tools", "payments": 6, "amount": 21400.00},
                    {"label": "Operations (founder)", "payments": 1, "amount": 20000.00}, {"label": "Other", "payments": 2, "amount": 3800.00}],
        movements=[{"date": date(2026, 10, 13), "payee": "Client receipt", "category": "client-receipts", "amount": 100000.00},
                   {"date": date(2026, 10, 14), "payee": "Contractor <b>payout</b>", "category": "payroll-contractors", "amount": -45000.00},
                   {"date": date(2026, 10, 16), "payee": "Software", "category": "saas-tools", "amount": -1999.00}],
        upcoming=[{"payee": "Software subscription", "expected": date(2026, 10, 24), "amount": 1999.00}],
        review_count=2, review_amount=6500.00, generated_at=datetime(2026, 10, 19, 0, 0))
    base.update(kw)
    return wr.Report(**base)


def test_inr_uses_lakh_grouping_and_usd_uses_standard():
    assert wr.money(240000, "INR", 94.96) == "₹2,40,000.00"
    assert wr.money(12345678.5, "INR", 94.96) == "₹1,23,45,678.50"
    assert wr.money(999.5, "INR", 94.96) == "₹999.50"
    assert wr.money(240000, "USD", 94.96) == "$2,527.38"


def test_signs_and_plain_mode_for_pdf_fonts():
    assert wr.money(-45000, "USD", 94.96, sign=True) == "−$473.88"
    assert wr.money(100000, "USD", 94.96, sign=True) == "+$1,053.07"
    assert wr.money(-45000, "INR", 94.96, plain=True) == "-INR 45,000.00"


def test_usd_rounds_half_up_to_cents():
    assert str(wr.usd(1, 4)) == "0.25" and str(wr.usd(0.01, 4)) == "0.00" and str(wr.usd(0.02, 4)) == "0.01"


def test_totals_convert_from_inr_not_from_rounded_lines():
    rate = 3.0
    lines = [10.0, 10.0, 10.0]
    assert str(wr.usd(sum(lines), rate)) == "10.00"                      # total converted from the INR total
    assert str(sum(wr.usd(x, rate) for x in lines)) == "9.99"            # three rounded lines are a cent short, as the footnote says


def test_period_subject_and_file_names():
    r = sample()
    assert wr.period_label(date(2026, 10, 12), date(2026, 10, 18)) == "12 – 18 Oct 2026"
    assert wr.period_label(date(2026, 9, 28), date(2026, 10, 4)) == "28 Sep – 4 Oct 2026"
    assert wr.period_label(date(2026, 12, 28), date(2027, 1, 3)) == "28 Dec 2026 – 3 Jan 2027"
    assert wr.subject(r, company="Acme Pvt Ltd") == "Acme Pvt Ltd weekly cash report · 12 – 18 Oct 2026"
    assert wr.pdf_name(r, "USD", company="Acme Pvt Ltd") == "acme-pvt-ltd-weekly-cash-report-2026-10-18-usd.pdf"


def test_html_defaults_to_inr_escapes_payees_and_points_to_the_usd_pdf():
    h = wr.render_html(sample())
    assert "₹2,40,000.00" in h and "₹1,23,200.00" in h and "cid:logo-white" in h
    assert "$" not in h                                       # no USD amounts in an INR body
    assert "&lt;b&gt;payout" in h and "<b>payout" not in h    # payee text is escaped
    assert "The USD PDF uses 1 USD = ₹94.96" in h and "16 Oct 2026" in h
    assert "not yet received" not in h


def test_html_usd_body_states_the_rate_and_has_no_rupee_amounts():
    h = wr.render_html(sample(), currency="USD")
    assert "$2,527.38" in h and "$1,297.39" in h
    assert "₹" not in h.split("Converted at")[0]
    assert "1 USD = ₹94.96" in h and "totals can differ by a cent" in h


def test_html_late_statement_notice_and_empty_sections():
    h = wr.render_html(sample(late_statement=True, upcoming=[], review_count=0))
    assert "not yet received" in h and "Nothing expected in the next 14 days." in h and "Nothing needs a person" in h


def test_largest_movements_are_by_absolute_amount():
    r = sample()
    assert [m["amount"] for m in wr.top_movements(r, 2)] == [100000.00, -45000.00]


def test_pdfs_are_built_in_both_currencies():
    usd_pdf, inr_pdf = wr.render_pdf(sample(), "USD"), wr.render_pdf(sample(), "INR")
    for b in (usd_pdf, inr_pdf):
        assert b.startswith(b"%PDF") and 3_000 < len(b) < 300_000
    assert usd_pdf != inr_pdf


def test_pdf_with_many_payments_runs_to_more_pages():
    many = [{"date": date(2026, 10, 13), "payee": f"Payee {i}", "category": "saas-tools", "amount": -100.0 * i} for i in range(1, 120)]
    b = wr.render_pdf(sample(movements=many), "USD")
    assert b.count(b"/Type /Page\n") + b.count(b"/Type /Page ") >= 2
