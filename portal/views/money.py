"""Bills, accounts, and the forecast."""
from datetime import date, datetime

from flask import (
    Blueprint, flash, redirect, render_template, request, send_file, session,
    url_for,
)
from flask_login import login_required

from ..extensions import db
from ..models import Account, AccountSnapshot, BillPayment, LedgerItem, Payee, Place
from ..services import importers, money as money_service
from ..util import current_period, month_label, shift_period

bp = Blueprint("money", __name__, url_prefix="/money")

CATEGORIES = [
    "Housing", "Utilities", "Insurance", "Vehicle", "Phone & Internet",
    "Subscriptions", "Medical", "Credit", "Family", "Other",
]
ACCOUNT_KINDS = {
    "checking": "Checking",
    "savings": "Savings",
    "retirement": "Retirement / TSP",
    "investment": "Investment",
    "debt": "Debt / loan",
}


@bp.route("/")
@login_required
def index():
    period = request.args.get("period") or current_period()
    if not _valid_period(period):
        period = current_period()

    view = money_service.month_view(period)
    accounts = Account.query.filter_by(active=True).order_by(
        Account.sort_order, Account.name
    ).all()

    return render_template(
        "money/index.html",
        view=view,
        label=month_label(period),
        accounts=accounts,
        net_worth=money_service.net_worth(),
        history=money_service.history(6),
        today=date.today(),
    )


@bp.route("/bills/<int:bill_id>/pay", methods=["POST"])
@login_required
def mark_paid(bill_id):
    bill = db.get_or_404(BillPayment, bill_id)
    if bill.status == "paid":
        bill.status = "due"
        bill.paid_on = None
    else:
        bill.status = "paid"
        bill.paid_on = date.today()
    db.session.commit()
    return redirect(request.referrer or url_for("money.index", period=bill.period))


@bp.route("/bills/<int:bill_id>", methods=["POST"])
@login_required
def update_bill(bill_id):
    bill = db.get_or_404(BillPayment, bill_id)
    amount = _float(request.form.get("amount"))
    if amount is not None:
        bill.amount = amount
    bill.note = (request.form.get("note") or "").strip() or None
    status = request.form.get("status")
    if status in ("due", "paid", "skipped"):
        bill.status = status
        if status == "paid" and not bill.paid_on:
            bill.paid_on = date.today()
        if status != "paid":
            bill.paid_on = None
    due = _date(request.form.get("due_date"))
    if due:
        bill.due_date = due
    db.session.commit()
    flash(f"Updated {bill.payee.name}.", "success")
    return redirect(url_for("money.index", period=bill.period))


# --- payees ---------------------------------------------------------------
@bp.route("/payees")
@login_required
def payees():
    rows = Payee.query.order_by(Payee.category, Payee.sort_order, Payee.name).all()
    grouped = {}
    for payee in rows:
        grouped.setdefault(payee.category or "Other", []).append(payee)
    return render_template(
        "money/payees.html",
        grouped=sorted(grouped.items()),
        total=sum(p.typical_amount or 0 for p in rows if p.active),
        count=len(rows),
    )


@bp.route("/payees/new", methods=["GET", "POST"])
@login_required
def new_payee():
    if request.method == "POST":
        payee = Payee()
        db.session.add(payee)
        _apply_payee(payee, request.form)
        db.session.commit()
        flash(f"Added {payee.name}.", "success")
        return redirect(url_for("money.payees"))
    return render_template(
        "money/payee_edit.html", payee=None, categories=CATEGORIES,
        places=Place.query.order_by(Place.name).all(),
    )


@bp.route("/payees/<int:payee_id>", methods=["GET", "POST"])
@login_required
def edit_payee(payee_id):
    payee = db.get_or_404(Payee, payee_id)
    if request.method == "POST":
        _apply_payee(payee, request.form)
        db.session.commit()
        flash("Saved.", "success")
        return redirect(url_for("money.payees"))
    return render_template(
        "money/payee_edit.html",
        payee=payee,
        categories=CATEGORIES,
        places=Place.query.order_by(Place.name).all(),
        history=money_service.payee_history(payee, 12),
    )


@bp.route("/payees/<int:payee_id>/delete", methods=["POST"])
@login_required
def delete_payee(payee_id):
    payee = db.get_or_404(Payee, payee_id)
    name = payee.name
    db.session.delete(payee)
    db.session.commit()
    flash(f"Removed {name}.", "info")
    return redirect(url_for("money.payees"))


# --- accounts -------------------------------------------------------------
@bp.route("/accounts")
@login_required
def accounts():
    rows = Account.query.order_by(Account.kind, Account.sort_order, Account.name).all()
    grouped = {}
    for acct in rows:
        grouped.setdefault(acct.kind, []).append(acct)
    return render_template(
        "money/accounts.html",
        grouped=sorted(grouped.items()),
        kinds=ACCOUNT_KINDS,
        net_worth=money_service.net_worth(),
    )


@bp.route("/accounts/new", methods=["GET", "POST"])
@login_required
def new_account():
    if request.method == "POST":
        acct = Account()
        db.session.add(acct)
        _apply_account(acct, request.form)
        db.session.flush()
        balance = _float(request.form.get("balance"))
        if balance is not None:
            db.session.add(
                AccountSnapshot(account_id=acct.id, as_of=date.today(), balance=balance)
            )
        db.session.commit()
        flash(f"Added {acct.name}.", "success")
        return redirect(url_for("money.accounts"))
    return render_template("money/account_edit.html", account=None, kinds=ACCOUNT_KINDS)


@bp.route("/accounts/<int:account_id>", methods=["GET", "POST"])
@login_required
def edit_account(account_id):
    acct = db.get_or_404(Account, account_id)
    if request.method == "POST":
        _apply_account(acct, request.form)
        db.session.commit()
        flash("Saved.", "success")
        return redirect(url_for("money.accounts"))
    return render_template(
        "money/account_edit.html", account=acct, kinds=ACCOUNT_KINDS
    )


@bp.route("/accounts/<int:account_id>/balance", methods=["POST"])
@login_required
def add_balance(account_id):
    acct = db.get_or_404(Account, account_id)
    balance = _float(request.form.get("balance"))
    if balance is None:
        flash("That balance was not a number.", "error")
        return redirect(url_for("money.accounts"))

    as_of = _date(request.form.get("as_of")) or date.today()
    existing = AccountSnapshot.query.filter_by(
        account_id=acct.id, as_of=as_of
    ).first()
    if existing:
        existing.balance = balance
    else:
        db.session.add(
            AccountSnapshot(
                account_id=acct.id, as_of=as_of, balance=balance,
                note=(request.form.get("note") or "").strip() or None,
            )
        )
    db.session.commit()
    flash(f"{acct.name} updated.", "success")
    return redirect(request.referrer or url_for("money.accounts"))


@bp.route("/accounts/<int:account_id>/delete", methods=["POST"])
@login_required
def delete_account(account_id):
    acct = db.get_or_404(Account, account_id)
    name = acct.name
    db.session.delete(acct)
    db.session.commit()
    flash(f"Removed {name}.", "info")
    return redirect(url_for("money.accounts"))


# --- recurring items ------------------------------------------------------
@bp.route("/recurring", methods=["GET", "POST"])
@login_required
def recurring():
    if request.method == "POST":
        item = LedgerItem()
        db.session.add(item)
        _apply_ledger(item, request.form)
        db.session.commit()
        flash(f"Added {item.name}.", "success")
        return redirect(url_for("money.recurring"))

    rows = LedgerItem.query.order_by(LedgerItem.kind, LedgerItem.name).all()
    return render_template(
        "money/recurring.html",
        income=[r for r in rows if r.kind == "income"],
        expenses=[r for r in rows if r.kind == "expense"],
        transfers=[r for r in rows if r.kind == "transfer"],
        accounts=Account.query.filter_by(active=True).order_by(Account.name).all(),
    )


@bp.route("/recurring/<int:item_id>", methods=["POST"])
@login_required
def edit_recurring(item_id):
    item = db.get_or_404(LedgerItem, item_id)
    _apply_ledger(item, request.form)
    db.session.commit()
    flash("Saved.", "success")
    return redirect(url_for("money.recurring"))


@bp.route("/recurring/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_recurring(item_id):
    item = db.get_or_404(LedgerItem, item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("money.recurring"))


# --- forecast -------------------------------------------------------------
@bp.route("/forecast")
@login_required
def forecast():
    try:
        months = max(1, min(int(request.args.get("months", 12)), 60))
    except ValueError:
        months = 12
    data = money_service.forecast(months)
    return render_template(
        "money/forecast.html",
        data=data,
        months=months,
        history=money_service.history(12),
    )


# --- import / export ------------------------------------------------------
@bp.route("/import", methods=["GET", "POST"])
@login_required
def import_sheet():
    """Step one: read the file, guess the columns, show what we found."""
    if request.method == "POST":
        upload = request.files.get("file")
        if not upload or not upload.filename:
            flash("Choose a .xlsx or .csv file first.", "error")
            return redirect(url_for("money.import_sheet"))
        try:
            headers, rows = importers.read_table(upload)
        except Exception as exc:
            flash(f"Could not read that file: {exc}", "error")
            return redirect(url_for("money.import_sheet"))

        if not headers:
            flash("That file looked empty.", "error")
            return redirect(url_for("money.import_sheet"))

        session["import_headers"] = headers
        session["import_rows"] = rows[:500]
        mapping = importers.guess_mapping(headers)
        return render_template(
            "money/import_map.html",
            headers=headers,
            rows=rows[:12],
            mapping=mapping,
            row_count=len(rows),
            preview=importers.preview_rows(headers, rows, mapping, 12),
        )

    return render_template("money/import.html")


@bp.route("/import/confirm", methods=["POST"])
@login_required
def import_confirm():
    """Step two: apply the confirmed mapping."""
    headers = session.get("import_headers")
    rows = session.get("import_rows")
    if not headers or not rows:
        flash("That upload expired. Please pick the file again.", "error")
        return redirect(url_for("money.import_sheet"))

    mapping = {}
    for field in importers.FIELD_HINTS:
        raw = request.form.get(f"map_{field}")
        if raw not in (None, "", "-1"):
            try:
                mapping[field] = int(raw)
            except ValueError:
                pass

    if "name" not in mapping:
        flash("Tell me which column holds the name before importing.", "error")
        return redirect(url_for("money.import_sheet"))

    items = importers.preview_rows(headers, rows, mapping, limit=500)
    if not items:
        flash("No rows had a name in that column.", "error")
        return redirect(url_for("money.import_sheet"))

    target = request.form.get("target", "payees")
    replace = request.form.get("replace") == "on"

    if target == "payees":
        created, updated = importers.import_payees(items, replace)
        noun = "bills"
    elif target == "accounts":
        created, updated = importers.import_accounts(
            items, request.form.get("account_kind", "savings"), replace
        )
        noun = "accounts"
    else:
        created, updated = importers.import_ledger(
            items, request.form.get("ledger_kind", "expense"), replace
        )
        noun = "recurring items"

    session.pop("import_headers", None)
    session.pop("import_rows", None)
    flash(f"Imported {noun}: {created} added, {updated} updated.", "success")
    return redirect(url_for("money.payees" if target == "payees" else "money.accounts"))


@bp.route("/export")
@login_required
def export():
    buf = importers.export_workbook()
    stamp = datetime.now().strftime("%Y-%m-%d")
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"household-money-{stamp}.xlsx",
    )


# --- helpers --------------------------------------------------------------
def _valid_period(period):
    try:
        datetime.strptime(period, "%Y-%m")
        return True
    except (ValueError, TypeError):
        return False


def _float(value, default=None):
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except ValueError:
        return default


def _int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _apply_payee(payee, form):
    payee.name = (form.get("name") or "Untitled").strip()
    payee.category = (form.get("category") or "Other").strip()
    payee.typical_amount = _float(form.get("typical_amount"), 0) or 0
    payee.due_day = min(max(_int(form.get("due_day"), 1) or 1, 1), 31)
    payee.pay_url = (form.get("pay_url") or "").strip() or None
    payee.login_url = (form.get("login_url") or "").strip() or None
    payee.phone = (form.get("phone") or "").strip() or None
    payee.account_hint = (form.get("account_hint") or "").strip() or None
    payee.notes = form.get("notes")
    payee.autopay = form.get("autopay") == "on"
    payee.variable_amount = form.get("variable_amount") == "on"
    payee.active = form.get("active") == "on"
    payee.place_id = _int(form.get("place_id")) or None
    payee.sort_order = _int(form.get("sort_order"), 0) or 0


def _apply_account(acct, form):
    acct.name = (form.get("name") or "Untitled").strip()
    acct.kind = form.get("kind") or "savings"
    acct.institution = (form.get("institution") or "").strip() or None
    acct.url = (form.get("url") or "").strip() or None
    acct.account_hint = (form.get("account_hint") or "").strip() or None
    acct.monthly_contribution = _float(form.get("monthly_contribution"), 0) or 0
    acct.annual_growth_pct = _float(form.get("annual_growth_pct"), 0) or 0
    acct.include_in_net_worth = form.get("include_in_net_worth") == "on"
    acct.active = form.get("active") == "on"
    acct.notes = form.get("notes")
    acct.sort_order = _int(form.get("sort_order"), 0) or 0


def _apply_ledger(item, form):
    item.name = (form.get("name") or "Untitled").strip()
    item.kind = form.get("kind") or "expense"
    item.amount = _float(form.get("amount"), 0) or 0
    item.frequency = form.get("frequency") or "monthly"
    item.day_of_month = min(max(_int(form.get("day_of_month"), 1) or 1, 1), 31)
    item.category = (form.get("category") or "Other").strip()
    item.to_account_id = _int(form.get("to_account_id")) or None
    item.active = form.get("active") == "on"
    item.notes = form.get("notes")
