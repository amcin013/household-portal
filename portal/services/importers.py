"""Getting the existing spreadsheet in, and getting data back out.

The import is deliberately two-step: read the file and guess what the columns
mean, show the guess, then commit once a human has confirmed the mapping. A
household spreadsheet is never shaped the way an importer expects, so guessing
silently would be worse than useless.
"""
import csv
import io
import re
from datetime import date, datetime

from openpyxl import Workbook, load_workbook

from ..extensions import db
from ..models import (
    Account, AccountSnapshot, BillPayment, LedgerItem, Payee,
)

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


def _bytes(file_storage):
    """Read the upload once and keep it, so a second look does not get nothing."""
    if getattr(file_storage, "_cached", None) is None:
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass
        file_storage._cached = file_storage.read()
    return file_storage._cached


def sheet_names(file_storage):
    """Every tab in the workbook, so the right one can be picked."""
    name = (file_storage.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        return []
    try:
        return load_workbook(io.BytesIO(_bytes(file_storage)), read_only=True).sheetnames
    except Exception:
        return []


def read_grid(file_storage, sheet=None):
    """The raw cells of an upload, values untouched.

    Kept as native types - a date stays a date and a number stays a number -
    because working out whether a column header is a month depends on that.
    """
    name = (file_storage.filename or "").lower()
    raw = _bytes(file_storage)

    if name.endswith((".xlsx", ".xlsm")):
        wb = load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb.active
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
    else:
        text = raw.decode("utf-8-sig", errors="replace")
        dialect = csv.Sniffer().sniff(text[:4096]) if text.strip() else csv.excel
        grid = list(csv.reader(io.StringIO(text), dialect))

    return [row for row in grid if any(c not in (None, "") for c in row)]


def grid_to_table(grid):
    """Flatten a grid to (headers, string rows) for the column-mapping path."""
    if not grid:
        return [], []
    header_idx = _find_header_row(grid)
    headers = [str(c).strip() if c is not None else "" for c in grid[header_idx]]
    rows = []
    for row in grid[header_idx + 1:]:
        padded = list(row) + [None] * (len(headers) - len(row))
        rows.append(["" if c is None else str(c).strip() for c in padded[:len(headers)]])
    return headers, rows


def read_table(file_storage):
    """Read an uploaded csv/xlsx into (headers, rows). Rows are lists of strings."""
    filename = (file_storage.filename or "").lower()
    raw = _bytes(file_storage)

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


# --------------------------------------------------------------------------
# Wide sheets: one row per bill, one column per month
# --------------------------------------------------------------------------
# The layout a household budget actually ends up in after a few years - the
# companies down the side, the months marching off to the right, and a few
# summary columns (Total, Estimated, Average) wedged in before the data starts.
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# Columns that hold a rollup rather than a month, and must never be imported.
SUMMARY_WORDS = {
    "total", "estimated", "estimate", "budget", "avg", "average", "mean",
    "% of total", "percent", "pct", "ytd", "sum", "max", "min", "count",
}


def _month_number(value):
    """Read a month out of a header cell, whether it is text or a real date."""
    if isinstance(value, (datetime, date)):
        return value.month, value.year
    if value is None:
        return None, None
    text = str(value).strip().lower().rstrip(".")
    if not text:
        return None, None
    if text in SUMMARY_WORDS or any(w in text for w in SUMMARY_WORDS):
        return None, None
    month = MONTHS.get(text) or MONTHS.get(text[:3])
    return (month, None) if month else (None, None)


def _year_of(value):
    if isinstance(value, (datetime, date)):
        return value.year
    try:
        year = int(str(value).strip()[:4])
    except (TypeError, ValueError):
        return None
    return year if 1990 <= year <= 2100 else None


def find_month_columns(grid):
    """Locate the header row and work out which column is which month.

    Returns (header_row_index, {column_index: 'YYYY-MM'}).

    Years are usually on their own row above the months, filled in only where
    they change, so they get carried across. Where the year runs out entirely -
    a sheet extended into next year without relabelling - it rolls over at
    each January.
    """
    best_row, best_cols = None, {}

    for idx, row in enumerate(grid[:25]):
        months = {}
        for col, cell in enumerate(row):
            month, year = _month_number(cell)
            if month:
                months[col] = (month, year)
        if len(months) > len(best_cols):
            best_row, best_cols = idx, months

    if best_row is None or len(best_cols) < 3:
        return None, {}

    # A row of years directly above the months, carried forward.
    years = {}
    if best_row > 0:
        for col, cell in enumerate(grid[best_row - 1]):
            year = _year_of(cell)
            if year:
                years[col] = year

    periods = {}
    current_year = None
    previous_month = None
    for col in sorted(best_cols):
        month, inline_year = best_cols[col]
        year = years.get(col) or inline_year
        if year:
            current_year = year
        elif current_year is not None and previous_month is not None and month < previous_month:
            current_year += 1  # rolled past December
        if current_year is None:
            continue
        periods[col] = f"{current_year:04d}-{month:02d}"
        previous_month = month

    return best_row, periods


def read_matrix(grid):
    """Pull a wide sheet apart into rows of {period: amount}.

    Returns (periods_in_order, [{name, values, total, months}]).
    """
    header_row, periods = find_month_columns(grid)
    if not periods:
        return [], []

    label_col = _find_label_column(grid, header_row)
    ordered = [periods[c] for c in sorted(periods)]

    items = []
    for row in grid[header_row + 1:]:
        if label_col >= len(row):
            continue
        name = row[label_col]
        name = "" if name is None else str(name).strip()
        # No label means a totals row or a spacer - never a bill.
        if not name or _month_number(name)[0]:
            continue

        values = {}
        for col in sorted(periods):
            if col >= len(row):
                continue
            amount = parse_money(row[col])
            if amount is not None:
                values[periods[col]] = amount
        if not values:
            continue

        recent = [values[p] for p in sorted(values)[-12:]]
        items.append({
            "name": name,
            "values": values,
            "total": sum(values.values()),
            "months": len(values),
            "first": min(values),
            "last": max(values),
            "average": sum(values.values()) / len(values),
            "recent_average": sum(recent) / len(recent),
        })

    return ordered, items


def _find_label_column(grid, header_row):
    """The column holding the row names - the leftmost mostly-text column."""
    best_col, best_score = 0, -1
    for col in range(min(4, max((len(r) for r in grid), default=1))):
        score = 0
        for row in grid[header_row + 1: header_row + 40]:
            if col >= len(row):
                continue
            cell = row[col]
            if cell is None or str(cell).strip() == "":
                continue
            score += 1 if parse_money(cell) is None else -1
        if score > best_score:
            best_col, best_score = col, score
    return best_col


def import_matrix(items, place_id=None, category="Utilities", replace=False):
    """Create payees and one bill per month from a wide sheet."""
    if replace:
        BillPayment.query.delete()
        Payee.query.delete()
        db.session.flush()

    payees_added = payees_updated = bills_added = bills_updated = 0

    for item in items:
        payee = Payee.query.filter(
            db.func.lower(Payee.name) == item["name"].lower()
        ).first()
        if payee is None:
            payee = Payee(name=item["name"], category=category, place_id=place_id)
            db.session.add(payee)
            db.session.flush()
            payees_added += 1
        else:
            payees_updated += 1

        # Seed the typical amount from the last twelve months, which reflects
        # what it costs now rather than what it cost in 2021.
        recent = [item["values"][p] for p in sorted(item["values"])[-12:]]
        if recent:
            payee.typical_amount = round(sum(recent) / len(recent), 2)
        if item.get("usage_unit"):
            payee.usage_unit = item["usage_unit"]

        existing = {b.period: b for b in payee.payments}
        for period, amount in item["values"].items():
            bill = existing.get(period)
            if bill is None:
                bill = BillPayment(
                    payee_id=payee.id,
                    period=period,
                    amount=amount,
                    due_date=_period_due_date(period, payee.due_day),
                    status="paid",
                    paid_on=_period_due_date(period, payee.due_day),
                )
                db.session.add(bill)
                bills_added += 1
            else:
                bill.amount = amount
                bills_updated += 1

    db.session.commit()
    return {
        "payees_added": payees_added,
        "payees_updated": payees_updated,
        "bills_added": bills_added,
        "bills_updated": bills_updated,
    }


def _period_due_date(period, day):
    import calendar
    year, month = (int(p) for p in period.split("-"))
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(day or 1, 1), last))


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
