"""Getting the existing spreadsheet in, and getting data back out.

The import is deliberately two-step: read the file and guess what the columns
mean, show the guess, then commit once a human has confirmed the mapping. A
household spreadsheet is never shaped the way an importer expects, so guessing
silently would be worse than useless.
"""
import csv
import io
import re
from datetime import date

from openpyxl import Workbook, load_workbook

from ..extensions import db
from ..models import Account, AccountSnapshot, LedgerItem, Payee

# Column-name guesses. First match wins.
FIELD_HINTS = {
    "name": ["name", "company", "payee", "bill", "vendor", "account", "description",
             "item", "who"],
    "amount": ["amount", "payment", "cost", "monthly", "due", "$", "total", "price",
               "balance"],
    "due_day": ["day", "due day", "due date", "date due", "when"],
    "category": ["category", "type", "kind", "group"],
    "url": ["url", "link", "website", "site", "pay"],
    "notes": ["note", "notes", "comment", "memo", "detail"],
    "account_hint": ["account #", "acct", "account number", "last 4", "ends"],
}

MONEY_RE = re.compile(r"-?[\d,]+\.?\d*")


def parse_money(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    match = MONEY_RE.search(text.replace("$", "").replace(",", ""))
    if not match:
        return None
    amount = float(match.group().replace(",", ""))
    return -amount if negative else amount


def parse_day(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        day = int(value)
        return day if 1 <= day <= 31 else None
    if isinstance(value, date):
        return value.day
    match = re.search(r"\d{1,2}", str(value))
    if not match:
        return None
    day = int(match.group())
    return day if 1 <= day <= 31 else None


def read_table(file_storage):
    """Read an uploaded csv/xlsx into (headers, rows). Rows are lists of strings."""
    filename = (file_storage.filename or "").lower()
    raw = file_storage.read()

    if filename.endswith((".xlsx", ".xlsm")):
        wb = load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        ws = wb.active
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
    else:
        text = raw.decode("utf-8-sig", errors="replace")
        dialect = csv.Sniffer().sniff(text[:4096]) if text.strip() else csv.excel
        grid = list(csv.reader(io.StringIO(text), dialect))

    grid = [row for row in grid if any(c not in (None, "") for c in row)]
    if not grid:
        return [], []

    header_idx = _find_header_row(grid)
    headers = [str(c).strip() if c is not None else "" for c in grid[header_idx]]
    rows = []
    for row in grid[header_idx + 1:]:
        padded = list(row) + [None] * (len(headers) - len(row))
        rows.append(["" if c is None else str(c).strip() for c in padded[:len(headers)]])
    return headers, rows


def _find_header_row(grid):
    """Spreadsheets often start with a title row. The header is the first row
    where most cells are short non-numeric labels."""
    best_idx, best_score = 0, -1
    for idx, row in enumerate(grid[:10]):
        cells = [c for c in row if c not in (None, "")]
        if len(cells) < 2:
            continue
        labels = sum(
            1 for c in cells
            if isinstance(c, str) and len(str(c)) < 40 and parse_money(c) is None
        )
        score = labels - (len(cells) - labels)
        if score > best_score:
            best_idx, best_score = idx, score
    return best_idx


def guess_mapping(headers):
    """{field: column index} for whatever we can recognise."""
    mapping = {}
    used = set()
    lowered = [h.lower().strip() for h in headers]

    for field, hints in FIELD_HINTS.items():
        for hint in hints:
            for idx, head in enumerate(lowered):
                if idx in used or not head:
                    continue
                if head == hint or hint in head:
                    mapping[field] = idx
                    used.add(idx)
                    break
            if field in mapping:
                break
    return mapping


def preview_rows(headers, rows, mapping, limit=200):
    """Apply a mapping without saving anything."""
    out = []
    for row in rows[:limit]:
        def cell(field):
            idx = mapping.get(field)
            if idx is None or idx >= len(row):
                return ""
            return row[idx]

        name = cell("name").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "amount": parse_money(cell("amount")),
                "due_day": parse_day(cell("due_day")),
                "category": cell("category") or "Utilities",
                "url": cell("url"),
                "notes": cell("notes"),
                "account_hint": cell("account_hint"),
            }
        )
    return out


def import_payees(items, replace=False):
    """Create or update payees from previewed rows."""
    if replace:
        Payee.query.delete()
        db.session.flush()

    created = updated = 0
    for item in items:
        payee = Payee.query.filter(
            db.func.lower(Payee.name) == item["name"].lower()
        ).first()
        if payee is None:
            payee = Payee(name=item["name"])
            db.session.add(payee)
            created += 1
        else:
            updated += 1

        payee.typical_amount = item["amount"] or 0
        payee.due_day = item["due_day"] or 1
        payee.category = item["category"] or "Utilities"
        if item["url"]:
            payee.pay_url = item["url"]
        if item["notes"]:
            payee.notes = item["notes"]
        if item["account_hint"]:
            payee.account_hint = item["account_hint"]

    db.session.commit()
    return created, updated


def import_accounts(items, kind="savings", replace=False):
    """Same rows, read as balances instead of bills."""
    if replace:
        AccountSnapshot.query.delete()
        Account.query.delete()
        db.session.flush()

    created = updated = 0
    today = date.today()
    for item in items:
        acct = Account.query.filter(
            db.func.lower(Account.name) == item["name"].lower()
        ).first()
        if acct is None:
            acct = Account(name=item["name"], kind=kind)
            db.session.add(acct)
            db.session.flush()
            created += 1
        else:
            updated += 1
        if item["notes"]:
            acct.notes = item["notes"]

        if item["amount"] is not None:
            existing = AccountSnapshot.query.filter_by(
                account_id=acct.id, as_of=today
            ).first()
            if existing:
                existing.balance = item["amount"]
            else:
                db.session.add(
                    AccountSnapshot(
                        account_id=acct.id, as_of=today, balance=item["amount"]
                    )
                )
    db.session.commit()
    return created, updated


def import_ledger(items, kind="expense", replace=False):
    if replace:
        LedgerItem.query.filter_by(kind=kind).delete()
        db.session.flush()

    created = updated = 0
    for item in items:
        row = LedgerItem.query.filter(
            db.func.lower(LedgerItem.name) == item["name"].lower()
        ).first()
        if row is None:
            row = LedgerItem(name=item["name"], kind=kind)
            db.session.add(row)
            created += 1
        else:
            updated += 1
        row.amount = item["amount"] or 0
        row.day_of_month = item["due_day"] or 1
        row.category = item["category"] or "Other"
        if item["notes"]:
            row.notes = item["notes"]
    db.session.commit()
    return created, updated


# --- export ---------------------------------------------------------------
def export_workbook():
    """Everything money-related as a real .xlsx, so the data is never trapped here."""
    wb = Workbook()

    ws = wb.active
    ws.title = "Bills"
    ws.append(["Company", "Category", "Typical amount", "Due day", "Autopay",
               "Account", "Pay URL", "Phone", "Notes"])
    for p in Payee.query.order_by(Payee.category, Payee.name):
        ws.append([p.name, p.category, p.typical_amount, p.due_day,
                   "yes" if p.autopay else "no", p.account_hint or "",
                   p.pay_url or "", p.phone or "", p.notes or ""])

    ws = wb.create_sheet("Accounts")
    ws.append(["Account", "Kind", "Institution", "Balance", "As of",
               "Monthly contribution", "Growth %/yr", "Notes"])
    for a in Account.query.order_by(Account.kind, Account.name):
        ws.append([a.name, a.kind, a.institution or "", a.balance,
                   a.as_of, a.monthly_contribution, a.annual_growth_pct,
                   a.notes or ""])

    ws = wb.create_sheet("Recurring")
    ws.append(["Name", "Kind", "Amount", "Frequency", "Day", "Category", "Notes"])
    for i in LedgerItem.query.order_by(LedgerItem.kind, LedgerItem.name):
        ws.append([i.name, i.kind, i.amount, i.frequency, i.day_of_month,
                   i.category, i.notes or ""])

    ws = wb.create_sheet("History")
    ws.append(["Company", "Month", "Amount", "Due", "Paid on", "Status", "Note"])
    for p in Payee.query.order_by(Payee.name):
        for b in sorted(p.payments, key=lambda x: x.period):
            ws.append([p.name, b.period, b.amount, b.due_date, b.paid_on,
                       b.status, b.note or ""])

    for sheet in wb.worksheets:
        for column in sheet.columns:
            width = max((len(str(c.value)) for c in column if c.value), default=8)
            sheet.column_dimensions[column[0].column_letter].width = min(width + 3, 48)
        sheet.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
