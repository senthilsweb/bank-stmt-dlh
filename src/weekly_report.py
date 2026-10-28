"""Weekly cash report: the HTML email body (USD) and the two PDFs (USD, INR). No AI, no Spark, no network.

Every figure is passed in as INR (the book of record) together with one USD/INR rate for the whole report. USD amounts
are INR / rate, rounded to cents line by line; totals are converted from the INR total, so they can differ from the sum of
the lines by a cent (the footnote says so). Everything here is a pure function of the `Report`, so it is unit tested.
"""
from __future__ import annotations

import html as _html
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import settings

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# emerald palette (RefCard set): primary, tint, secondary, hair; semantic colours stay in the same family
EMERALD = {"primary": "#0B4F3F", "tint": "#F0F5F2", "secondary": "#1B7F5C", "hair": "#D3DED9", "pos": "#17795E", "neg": "#B3402F", "muted": "#66737F", "ink": "#1B2733"}


@dataclass
class Report:
    week_start: date
    week_end: date
    opening: float
    closing: float
    money_in: float
    money_out: float
    payments: int
    rate: float                                   # INR per 1 USD
    rate_date: date
    categories: list[dict] = field(default_factory=list)   # {label, payments, amount}  money out by category, INR
    movements: list[dict] = field(default_factory=list)    # {date, payee, category, amount}  every payment, signed INR
    upcoming: list[dict] = field(default_factory=list)     # {payee, expected, amount}  next 14 days, INR
    review_count: int = 0
    review_amount: float = 0.0
    late_statement: bool = False
    generated_at: datetime | None = None


# ---------- formatting ----------

def usd(inr: float, rate: float) -> Decimal:
    return (Decimal(str(inr)) / Decimal(str(rate))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _group_us(n: Decimal) -> str:
    return f"{n:,.2f}"


def _group_in(n: Decimal) -> str:
    """Indian grouping (lakh, crore): 2,40,000.00"""
    whole, frac = f"{n:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{whole}.{frac}"


def money(inr: float, currency: str, rate: float, *, sign: bool = False, plain: bool = False) -> str:
    """Format an INR amount in the chosen currency. plain=True avoids characters the PDF base fonts lack (rupee sign, minus)."""
    neg = inr < 0
    a = abs(inr)
    if currency == "USD":
        body = "$" + _group_us(usd(a, rate))
    else:
        body = ("INR " if plain else "₹") + _group_in(Decimal(str(a)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if neg:
        return ("-" if plain else "−") + body
    return ("+" + body) if sign and inr > 0 else body


def period_label(start: date, end: date) -> str:
    if start.year == end.year and start.month == end.month:
        return f"{start.day} – {end.day} {end:%b %Y}"
    if start.year == end.year:
        return f"{start.day} {start:%b} – {end.day} {end:%b %Y}"
    return f"{start.day} {start:%b %Y} – {end.day} {end:%b %Y}"


def company_name() -> str:
    return settings.load()["company_name"]


def subject(r: Report, company: str | None = None) -> str:
    return f"{company or company_name()} weekly cash report · {period_label(r.week_start, r.week_end)}"


def pdf_name(r: Report, currency: str, company: str | None = None) -> str:
    return f"{settings.slug(company or company_name())}-weekly-cash-report-{r.week_end.isoformat()}-{currency.lower()}.pdf"


def rate_note(r: Report) -> str:
    return (f"Converted at 1 USD = ₹{r.rate:,.2f} (ECB reference rate for {r.rate_date.day} {r.rate_date:%b %Y}, the latest published before this report). "
            "Indicative only: the books stay in INR. Line items are converted one by one, so totals can differ by a cent.")


def top_movements(r: Report, n: int = 5) -> list[dict]:
    return sorted(r.movements, key=lambda m: abs(m["amount"]), reverse=True)[:n]


# ---------- HTML body (INR by default, USD when asked) ----------

def render_html(r: Report, *, logo_cid: str = "logo-white", currency: str = "INR") -> str:
    p, e = EMERALD, _html.escape
    m = lambda x, **k: money(x, currency, r.rate, **k)
    th = f'style="text-align:left;padding:6px 4px;border-bottom:1px solid {p["hair"]};font-size:11px;color:{p["muted"]};font-weight:600"'
    td = f'style="padding:6px 4px;border-bottom:1px solid {p["hair"]};font-size:12.5px;color:{p["ink"]}"'
    tdr = td[:-1] + ';text-align:right;white-space:nowrap"'
    thr = th[:-1] + ';text-align:right"'
    h4 = f'style="margin:18px 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:{p["muted"]}"'
    tile = lambda label, val, colour=p["ink"]: (
        f'<td width="50%" style="padding:4px"><div style="background:{p["tint"]};border-radius:3px;padding:9px 11px">'
        f'<div style="font-size:11px;color:{p["muted"]};text-transform:uppercase;letter-spacing:.05em">{label}</div>'
        f'<div style="font-size:16px;font-weight:bold;color:{colour}">{val}</div></div></td>')
    cats = "".join(f'<tr><td {td}>{e(c["label"])}</td><td {tdr}>{c["payments"]}</td><td {tdr}>{m(c["amount"])}</td></tr>' for c in r.categories)
    moves = "".join(
        f'<tr><td {td}>{m_["date"]:%d %b}</td><td {td}>{e(m_["payee"])}</td>'
        f'<td {tdr[:-1]};color:{p["pos"] if m_["amount"] > 0 else p["neg"]}">{m(m_["amount"], sign=True)}</td></tr>' for m_ in top_movements(r))
    ups = "".join(f'<tr><td {td}>{e(u["payee"])}</td><td {tdr}>~ {u["expected"]:%d %b}</td><td {tdr}>{m(u["amount"])}</td></tr>' for u in r.upcoming) \
        or f'<tr><td {td} colspan="3">Nothing expected in the next 14 days.</td></tr>'
    notice = (f'<div style="background:#FFF4DC;color:#6B4A00;border-radius:3px;padding:7px 10px;font-size:12px;margin-bottom:14px">'
              "Bank statement for this week not yet received. Figures are from transactions loaded so far.</div>") if r.late_statement else ""
    review = (f'<tr><td {td}>{r.review_count} payment{"s" if r.review_count != 1 else ""} unlabelled ({m(r.review_amount)})</td><td {tdr}>See the dashboard</td></tr>'
              if r.review_count else f'<tr><td {td} colspan="2">Nothing needs a person this week.</td></tr>')
    note = rate_note(r) if currency == "USD" else (
        f"Amounts in INR, the book of record. The USD PDF uses 1 USD = ₹{r.rate:,.2f} (ECB reference rate for {r.rate_date.day} {r.rate_date:%b %Y}).")
    fx = f'<div style="background:{p["tint"]};color:{p["muted"]};padding:12px 22px;font-size:11px">{e(note)}</div>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{e(subject(r))}</title></head>
<body style="margin:0;background:#E7EBEE;padding:18px 0;font-family:Arial,Helvetica,sans-serif;color:{p["ink"]}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#FFFFFF;border-radius:4px;overflow:hidden">
<tr><td style="background:{p["primary"]};padding:18px 22px;color:#FFFFFF">
  <img src="cid:{logo_cid}" alt="{e(company_name())}" height="26" style="display:block;height:26px;margin-bottom:10px">
  <div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;opacity:.8">Weekly cash report</div>
  <div style="font-size:18px;font-weight:bold;margin-top:2px">Week of {e(period_label(r.week_start, r.week_end))}</div></td></tr>
<tr><td style="padding:18px 22px">{notice}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{tile("Opening balance", m(r.opening))}{tile("Closing balance", m(r.closing))}</tr>
  <tr>{tile("Money in", m(r.money_in), p["pos"])}{tile("Money out", m(r.money_out), p["neg"])}</tr></table>
  <div {h4}>Where the money went</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><th {th}>Category</th><th {thr}>Payments</th><th {thr}>Amount</th></tr>{cats}</table>
  <div {h4}>Largest movements</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><th {th}>Date</th><th {th}>Payee</th><th {thr}>Amount</th></tr>{moves}</table>
  <div {h4}>Coming up (next 14 days)</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{ups}</table>
  <div {h4}>Needs a person</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{review}</table></td></tr>
<tr><td>{fx}<div style="background:{p["tint"]};color:{p["muted"]};padding:12px 22px;font-size:11px">Attached: {e(pdf_name(r, "USD"))} and {e(pdf_name(r, "INR"))} · Sent by the bank-stmt-dlh job · Figures from loaded bank statements</div></td></tr>
</table></td></tr></table></body></html>"""


# ---------- PDF (USD or INR) ----------

def render_pdf(r: Report, currency: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    P = {k: colors.HexColor(v) for k, v in EMERALD.items()}
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica", fontSize=9, textColor=P["ink"], leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, textColor=P["muted"], leading=10)
    h1 = ParagraphStyle("h1", parent=body, fontName="Helvetica-Bold", fontSize=16, textColor=P["primary"], leading=20)
    h2 = ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=9, textColor=P["muted"], spaceBefore=8, spaceAfter=3, leading=11)
    m = lambda x, **k: money(x, currency, r.rate, plain=True, **k)
    cell_r = ParagraphStyle("r", parent=body, alignment=2)

    class Numbered(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            n = len(self._pages)
            for st in self._pages:
                self.__dict__.update(st)
                self.setFont("Helvetica", 7.5)
                self.setFillColor(P["muted"])
                self.drawString(18 * mm, 10 * mm, f"Page {self._pageNumber} of {n}  ·  Account number not shown  ·  Figures from loaded bank statements")
                super().showPage()
            super().save()

    story = [Image(str(ASSETS / "logo.png"), width=34 * mm, height=34 * mm * 155 / 700, hAlign="LEFT"), Spacer(1, 4),
             Paragraph(f"Weekly cash report ({currency})", h1),
             Paragraph(f"{period_label(r.week_start, r.week_end)}" + (f"  ·  generated {r.generated_at:%a %d %b %Y %H:%M} ET" if r.generated_at else ""), body)]
    if r.late_statement:
        story += [Spacer(1, 4), Paragraph("Bank statement for this week not yet received. Figures are from transactions loaded so far.", small)]
    story += [Spacer(1, 6)]
    kpi = Table([["Opening", "Money in", "Money out", "Closing"], [m(r.opening), m(r.money_in), m(r.money_out), m(r.closing)]], colWidths=[43 * mm] * 4)
    kpi.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 7.5), ("TEXTCOLOR", (0, 0), (-1, 0), P["muted"]),
                             ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 10), ("BACKGROUND", (0, 0), (-1, -1), P["tint"]),
                             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [kpi, Paragraph("Where the money went", h2)]
    grid = lambda rows, widths, header=True: _grid(rows, widths, P, header)
    story += [grid([["Category", "Payments", "Amount"]] + [[c["label"], str(c["payments"]), m(c["amount"])] for c in r.categories] or [["-", "", ""]],
                   [100 * mm, 30 * mm, 42 * mm]), Paragraph("Every payment of the week", h2)]
    rows = [["Date", "Payee", "Category", "Amount"]] + [[f'{x["date"]:%d %b}', x["payee"][:34], x["category"][:24], m(x["amount"], sign=True)] for x in sorted(r.movements, key=lambda x: x["date"])]
    story += [grid(rows, [20 * mm, 62 * mm, 48 * mm, 42 * mm])]
    if r.upcoming:
        story += [Paragraph("Coming up (next 14 days)", h2), grid([[u["payee"][:40], f'~ {u["expected"]:%d %b}', m(u["amount"])] for u in r.upcoming], [100 * mm, 30 * mm, 42 * mm], header=False)]
    story += [Spacer(1, 8)]
    if currency == "USD":
        story += [Paragraph(rate_note(r).replace("₹", "INR "), small)]
    else:
        story += [Paragraph(f"Amounts in INR, the book of record. The USD version uses 1 USD = INR {r.rate:,.2f} (ECB reference rate, {r.rate_date.day} {r.rate_date:%b %Y}).", small)]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
                      title=subject(r), author="bank-stmt-dlh").build(story, canvasmaker=Numbered)
    return buf.getvalue()


def _grid(rows, widths, P, header=True):
    from reportlab.platypus import Table, TableStyle
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("TEXTCOLOR", (0, 0), (-1, -1), P["ink"]),
             ("LINEBELOW", (0, 0), (-1, -1), 0.4, P["hair"]), ("ALIGN", (-1, 0), (-1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 7.5), ("TEXTCOLOR", (0, 0), (-1, 0), P["muted"])]
    t.setStyle(TableStyle(style))
    return t
