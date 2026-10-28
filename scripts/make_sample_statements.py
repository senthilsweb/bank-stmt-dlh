"""Generate synthetic bank statement PDFs in the HDFC current account layout the parser reads.

    python scripts/make_sample_statements.py [out_dir]      # default samples/statements

Four monthly statements (Jul to Oct 2026) and two weekly ones that overlap October, for a fictional company
with fictional payees (they match config/examples/merchant_map.yaml). No password. Every statement reconciles:
counts, totals and closing balance in the STATEMENT SUMMARY are computed from the rows. Deterministic output.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
COMPANY = "CONCEPTLABS PRIVATE LIMITED"
ACCOUNT = "50200098765432"
OPENING = Decimal("1250000.00")
D = Decimal

# (day, narration, amount, direction). Narrations follow the bank's own patterns so channel and counterparty cleaning work.
MONTHLY = [
    (2,  "ME DC SI 512345XXXXXX1234 GOOGLE WORKSPACE",                                      D("4720.00"),  "debit"),
    (3,  "ME DC SI 512345XXXXXX1234 AMAZON WEB SERVICES",                                   D("12450.75"), "debit"),
    (4,  "UPI-AUTOPAY-OPENAI LLC-OPENAILLC.CFP@CAS-HDFC0000001-523412345678-SUBSCRIPTION",  D("1999.00"),  "debit"),
    (5,  "NEFT DR-HDFC0001234-ARJUN MEHTA-NETBANK, MUM-N210261234567",                      D("85000.00"), "debit"),
    (6,  "UPI-AIRTEL PAYMENTS-airtel@okhdfcbank-HDFC0000001-523498765432-BROADBAND",        D("1499.00"),  "debit"),
    (7,  "IMPS-521234567890-RAVI SHANKAR IYER-HDFC-XXXXXX9876-CONSULTANCY FEE",             D("45000.00"), "debit"),
    (8,  "UPI-SWIGGY-swiggy@icici-ICIC0000001-523455667788-TEAM LUNCH",                     D("1840.00"),  "debit"),
    (10, "UPI-PRIYA NAIR-priya.nair@okaxis-UTIB0000123-523411223344-STIPEND",               D("15000.00"), "debit"),
    (12, "UPI-UBER INDIA-uber@axisbank-UTIB0000001-523466778899-TRIP",                       D("420.00"),   "debit"),
    (14, "UPI-CAFE BLUE TOKAI-bluetokai@ybl-YESB0000001-523400112233-COFFEE",               D("560.00"),   "debit"),
    (17, "UPI-RAJ STATIONERS-rajstat@okhdfcbank-HDFC0000001-523499887766-PAPER",            D("1240.00"),  "debit"),
    (18, "UPI-ZOMATO-zomato@ptybl-YESB0000001-523455443322-DINNER",                          D("920.00"),   "debit"),
    (20, "GST PAYMENT CPIN 26072600123456",                                                  D("48000.00"), "debit"),
    (22, "UPI-BMRCL-bmrcl@sbi-SBIN0000001-523411112222-METRO",                               D("150.00"),   "debit"),
    (25, "UPI-SUNRISE ELECTRICALS-sunrise@okicici-ICIC0000001-523433334444-CABLES",          D("2380.00"),  "debit"),
    (28, "NEFT DR-HDFC0001234-VIKRAM RAO-NETBANK, MUM-N210269876543",                        D("100000.00"), "debit"),
    (31, "SMS ALERT CHGS",                                                                   D("17.70"),    "debit"),
]
# extra rows in particular months (yearly payments, receipts, funding, a few surprises)
EXTRA = {
    7:  [(1,  "NEFT DR-HDFC0001234-NORTHSTAR PROPERTIES LLP-OFFICE RENT 2026-27-N210260001111", D("360000.00"), "debit"),
         (9,  "IMPS-523456789012-MEERA KAPOOR-HDFC-XXXXXX5678-INVESTMENT",                     D("500000.00"), "credit"),
         (15, "NEFT CR-UTIB0000123-GLOBEX TECHNOLOGIES PVT LTD-CONCEPTLABS-AXISCN0123456789",   D("450000.00"), "credit")],
    8:  [(11, "RTGS CR-HDFC0000999-ACME VENTURES LLP-CONCEPTLABS PVT LTD-HDFCR52026081112345",  D("2500000.00"), "credit"),
         (13, "NEFT DR-HDFC0001234-SAFEGUARD INSURANCE CO LTD-GROUP HEALTH-N210260002222",      D("38500.00"),  "debit"),
         (15, "NEFT CR-UTIB0000123-GLOBEX TECHNOLOGIES PVT LTD-CONCEPTLABS-AXISCN0123456790",   D("300000.00"), "credit"),
         (19, "NEFT CR-ICIC0000456-VIKRAM RAO-CONCEPTLABS PVT LTD-N210260003333",               D("50000.00"),  "credit")],
    9:  [(15, "NEFT CR-UTIB0000123-GLOBEX TECHNOLOGIES PVT LTD-CONCEPTLABS-AXISCN0123456791",   D("450000.00"), "credit"),
         (16, "NEFT DR-HDFC0001234-AUDIT PARTNERS LLP-AUDIT FEE 2025-26-N210260004444",         D("25000.00"),  "debit"),
         (24, "NEFT CR-ICIC0000456-VIKRAM RAO-CONCEPTLABS PVT LTD-N210260005555",               D("100000.00"), "credit"),
         (30, "CREDIT INTEREST CAPITALISED",                                                     D("3250.00"),   "credit")],
    10: [(9,  "NEFT CR-SBIN0001234-SKYLINE REMITTER LLP-ADVANCE-SBINN52026100912345",            D("75000.00"),  "credit"),
         (15, "NEFT CR-UTIB0000123-GLOBEX TECHNOLOGIES PVT LTD-CONCEPTLABS-AXISCN0123456792",   D("450000.00"), "credit")],
}
SKIP = {(10, "IMPS-521234567890-RAVI SHANKAR IYER-HDFC-XXXXXX9876-CONSULTANCY FEE")}  # engagement ended in September


def month_rows(year: int, month: int) -> list[tuple[date, str, Decimal, str]]:
    last = (date(year, month % 12 + 1, 1) if month < 12 else date(year + 1, 1, 1)) - timedelta(days=1)
    rows = [(min(d, last.day), n, a, k) for d, n, a, k in MONTHLY if (month, n) not in SKIP] + EXTRA.get(month, [])
    rows.sort(key=lambda r: (r[0], r[1]))
    return [(date(year, month, d), n, a, k) for d, n, a, k in rows]


def ledger(months: list[tuple[int, int]]) -> list[dict]:
    """Every row with its reference and running balance, in order."""
    out, bal, ref = [], OPENING, 100000000001
    for y, m in months:
        for d, n, a, k in month_rows(y, m):
            bal = bal + a if k == "credit" else bal - a
            out.append({"date": d, "narr": n, "amount": a, "kind": k, "balance": bal, "ref": f"{ref:016d}"})
            ref += 7
    return out


def money(x: Decimal) -> str:
    return f"{x:,.2f}"


def write_pdf(path: Path, rows: list[dict], opening: Decimal, start: date, end: date, kind: str) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    y = h - 40
    page = 1

    def text(s, size=7, font="Courier", dy=11):
        nonlocal y
        c.setFont(font, size)
        c.drawString(28, y, s)
        y -= dy

    def header(first: bool):
        nonlocal y
        y = h - 40
        if first:
            text("HDFC BANK LIMITED", 9, "Courier-Bold", 13)
            text(f"{COMPANY}", 8, "Courier-Bold", 11)
            text("12 SAMPLE STREET, BENGALURU 560001", 8)
            text(f"Account No : {ACCOUNT}    Currency : INR    Account Branch : SAMPLE BRANCH", 8, dy=12)
            text(f"Statement of account    From : {start:%d/%m/%Y}   To : {end:%d/%m/%Y}    ({kind} statement)", 8, dy=14)
        text(f"Page No .: {page}", 7, dy=10)
        text("Date      Narration                                                        Chq./Ref.No.      Value Dt   Amount          Closing Balance", 7, "Courier-Bold", 12)

    def footer():
        nonlocal y
        y -= 4
        text(f"Generated On: {(end + timedelta(days=1)):%d/%m/%Y}", 7, dy=10)
        text("This is a computer generated statement and does not require signature.", 7, dy=10)
        text("HDFC BANK LIMITED", 7, dy=10)

    header(True)
    for r in rows:
        if y < 90:
            footer()
            c.showPage()
            page += 1
            header(False)
        line = f"{r['date']:%d/%m/%y}  {r['narr']:<70}  {r['ref']}  {r['date']:%d/%m/%y}  {money(r['amount']):>14}  {money(r['balance']):>16}"
        text(line)
    dr = [r for r in rows if r["kind"] == "debit"]
    cr = [r for r in rows if r["kind"] == "credit"]
    closing = rows[-1]["balance"] if rows else opening
    y -= 6
    text("STATEMENT SUMMARY :-", 8, "Courier-Bold", 12)
    text("Opening Balance        Dr Count   Cr Count   Debits            Credits           Closing Bal", 7, "Courier-Bold", 11)
    text(f"{money(opening):<22} {len(dr):<10} {len(cr):<10} {money(sum((r['amount'] for r in dr), D(0))):<17} "
         f"{money(sum((r['amount'] for r in cr), D(0))):<17} {money(closing)}", 7, dy=12)
    footer()
    c.save()


def main(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    months = [(2026, 7), (2026, 8), (2026, 9), (2026, 10)]
    rows = ledger(months)
    files = []
    for y, m in months:
        mrows = [r for r in rows if r["date"].month == m]
        opening = next((rr["balance"] for rr in reversed(rows) if rr["date"] < mrows[0]["date"]), OPENING)
        start, end = date(y, m, 1), (mrows[-1]["date"].replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        p = out_dir / f"{y}-{m:02d}-monthly.pdf"
        write_pdf(p, mrows, opening, start, end, "monthly")
        files.append(p)
    for start in (date(2026, 10, 5), date(2026, 10, 12)):
        end = start + timedelta(days=6)
        wrows = [r for r in rows if start <= r["date"] <= end]
        opening = next(rr["balance"] for rr in reversed(rows) if rr["date"] < start)
        p = out_dir / f"{start:%Y-%m-%d}-weekly.pdf"
        write_pdf(p, wrows, opening, start, end, "weekly")
        files.append(p)
    for p in files:
        print(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples" / "statements"))
