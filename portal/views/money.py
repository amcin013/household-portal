"""Bills, accounts, and the forecast."""
from datetime import date, datetime

from flask import (
    Blueprint, flash, jsonify, redirect, render_template, request, send_file,
    session, url_for,
)
from flask_login import login_required

from ..extensions import db
from ..models import Account, AccountSnapshot, BillPayment, LedgerItem, Payee, Place
from ..services import (
    importers, money as money_service, staging, usage as usage_service,
)
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


SORTS = {
    "name": lambda b: (b.payee.name or "").lower(),
    "category": lambda b: ((b.payee.category or "").lower(), (b.payee.name or "").lower()),
    "due": lambda b: (b.due_date or date.max, (b.payee.name or "").lower()),
    "amount": lambda b: (b.amount or 0),
    "status": lambda b: (b.status or "", (b.payee.name or "").lower()),
}


@bp.route("/")
@login_required
def index():
    """This month's bills as a table you can sort, filter and group.

    All three are done on the server off query parameters, so the page works
    with JavaScript switched off; the script layer only makes the same actions
    instant.
    """
    period = request.args.get("period") or current_period()
    if not _valid_period(period):
        period = current_period()

    view = money_service.month_view(period)
    bills = list(view["bills"])

    query = (request.args.get("q") or "").strip()
    if query:
        needle = query.lower()
        bills = [
            b for b in bills
            if needle in (b.payee.name or "").lower()
            or needle in (b.payee.category or "").lower()
            or needle in (b.payee.account_hint or "").lower()
        ]

    status = request.args.get("status") or "all"
    if status == "due":
        bills = [b for b in bills if b.status == "due"]
    elif status == "paid":
        bills = [b for b in bills if b.status == "paid"]
    elif status == "overdue":
        bills = [b for b in bills
                 if b.status == "due" and b.due_date and b.due_date < date.today()]

    sort = request.args.get("sort") or "due"
    direction = request.args.get("dir") or "asc"
    bills.sort(key=SORTS.get(sort, SORTS["due"]), reverse=(direction == "desc"))

    group_by = request.args.get("group") or "none"
    groups = []
    if group_by == "category":
        buckets = {}
        for bill in bills:
            buckets.setdefault(bill.payee.category or "Other", []).append(bill)
        groups = [
            {"label": name, "bills": rows,
             "total": sum(b.amount or 0 for b in rows),
             "unpaid": sum(1 for b in rows if b.status == "due")}
            for name, rows in sorted(buckets.items())
        ]
    else:
        groups = [{"label": None, "bills": bills,
                   "total": sum(b.amount or 0 for b in bills),
                   "unpaid": sum(1 for b in bills if b.status == "due")}]

    return render_template(
        "money/index.html",
        view=view,
        bills=bills,
        groups=groups,
        label=month_label(period),
        accounts=Account.query.filter_by(active=True).order_by(
            Account.sort_order, Account.name).all(),
        net_worth=money_service.net_worth(),
        history=money_service.history(12),
        today=date.today(),
        q=query, status=status, sort=sort, dir=direction, group_by=group_by,
        shown_total=sum(b.amount or 0 for b in bills),
    )


@bp.route("/bills/<int:bill_id>/quick", methods=["POST"])
@login_required
def quick_update(bill_id):
    """Inline edits from the table. Answers JSON to a fetch, and redirects back
    for a plain form post so the same route serves both."""
    bill = db.get_or_404(BillPayment, bill_id)

    if "amount" in request.form:
        amount = _float(request.form.get("amount"))
        if amount is not None:
            bill.amount = amount
    if "due_date" in request.form:
        due = _date(request.form.get("due_date"))
        if due:
            bill.due_date = due
    action = request.form.get("action")
    if action == "toggle":
        if bill.status == "paid":
            bill.status, bill.paid_on = "due", None
        else:
            bill.status, bill.paid_on = "paid", date.today()
    db.session.commit()

    if request.headers.get("X-Requested-With") == "fetch":
        view = money_service.month_view(bill.period)
        return jsonify({
            "ok": True,
            "amount": bill.amount,
            "status": bill.status,
            "overdue": bool(bill.status == "due" and bill.due_date
                            and bill.due_date < date.today()),
            "month_total": view["total"],
            "month_remaining": view["remaining"],
            "count_due": view["count_due"],
        })
    return redirect(request.referrer or url_for("money.index", period=bill.period))


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
    readings = usage_service.usage_history(payee, 24)
    latest = [r for r in readings if r["usage"]]
    comparison = None
    if len(latest) >= 1:
        # Against the same month last year, which is the only fair comparison
        # for anything weather-driven.
        newest = latest[-1]["period"]
        comparison = usage_service.compare_periods(
            payee, newest, shift_period(newest, -12)
        ) or usage_service.compare_periods(payee, newest, shift_period(newest, -1))

    return render_template(
        "money/payee_edit.html",
        payee=payee,
        categories=CATEGORIES,
        places=Place.query.order_by(Place.name).all(),
        history=money_service.payee_history(payee, 12),
        readings=readings,
        has_usage=bool(latest),
        comparison=comparison,
        units=usage_service.UNIT_LABELS,
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
    try:
        back = max(6, min(int(request.args.get("back", 24)), 72))
    except ValueError:
        back = 24

    return render_template(
        "money/forecast.html",
        data=money_service.forecast(months),
        months=months,
        back=back,
        spend=money_service.spending_over_time(back),
    )


# --- import / export ------------------------------------------------------
@bp.route("/import", methods=["GET", "POST"])
@login_required
def import_sheet():
    """Step one: read the file, work out its shape, show what we found."""
    if request.method == "POST":
        upload = request.files.get("file")
        if not upload or not upload.filename:
            flash("Choose a .xlsx or .csv file first.", "error")
            return redirect(url_for("money.import_sheet"))

        sheet = (request.form.get("sheet") or "").strip() or None
        try:
            grid = importers.read_grid(upload, sheet)
        except Exception as exc:
            flash(f"Could not read that file: {exc}", "error")
            return redirect(url_for("money.import_sheet"))

        if not grid:
            flash("That file looked empty.", "error")
            return redirect(url_for("money.import_sheet"))

        # A sheet with months across the top is a different animal from a
        # simple list, and importing it as a list would throw away the history.
        periods, items = importers.read_matrix(grid)
        if periods and items:
            staging.save({
                "kind": "matrix",
                "items": [{"name": i["name"], "values": i["values"]} for i in items],
            })
            return render_template(
                "money/import_matrix.html",
                periods=periods,
                items=items,
                sheets=importers.sheet_names(upload),
                current_sheet=sheet,
                total_records=sum(i["months"] for i in items),
                grand_total=sum(i["total"] for i in items),
                places=Place.query.order_by(Place.name).all(),
                categories=CATEGORIES,
            )

        headers, rows = importers.grid_to_table(grid)
        staging.save({"kind": "table", "headers": headers, "rows": rows[:500]})
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


@bp.route("/import/matrix", methods=["POST"])
@login_required
def import_matrix_confirm():
    """Commit a wide sheet: one payee per row, one bill per month."""
    staged = staging.load() or {}
    items = staged.get("items") if staged.get("kind") == "matrix" else None
    if not items:
        flash("That upload expired. Please pick the file again.", "error")
        return redirect(url_for("money.import_sheet"))

    keep = set(request.form.getlist("include"))
    chosen = [i for i in items if i["name"] in keep] if keep else items
    if not chosen:
        flash("Nothing was selected.", "error")
        return redirect(url_for("money.import_sheet"))

    result = importers.import_matrix(
        chosen,
        place_id=_int(request.form.get("place_id")) or None,
        category=(request.form.get("category") or "Utilities").strip(),
        replace=request.form.get("replace") == "on",
    )
    staging.discard()
    flash(
        f"Imported {result['bills_added']:,} months across "
        f"{result['payees_added']} new companies "
        f"({result['payees_updated']} already existed).",
        "success",
    )
    return redirect(url_for("money.payees"))


# --- meter readings -------------------------------------------------------
@bp.route("/usage", methods=["GET", "POST"])
@login_required
def usage_import():
    """Green Button, Smart Meter Texas, or any CSV with dates and numbers."""
    if request.method == "POST":
        payee = db.session.get(Payee, _int(request.form.get("payee_id")) or 0)
        upload = request.files.get("file")
        if payee is None:
            flash("Choose which company the readings belong to.", "error")
            return redirect(url_for("money.usage_import"))
        if not upload or not upload.filename:
            flash("Choose a file first.", "error")
            return redirect(url_for("money.usage_import"))

        try:
            unit, totals = usage_service.read_usage_file(
                upload, request.form.get("unit") or None
            )
        except Exception as exc:
            flash(f"Could not read that file: {exc}", "error")
            return redirect(url_for("money.usage_import"))

        result = usage_service.apply_usage(
            payee, unit, totals,
            source="import",
            overwrite=request.form.get("overwrite") == "on",
            only_complete=request.form.get("keep_partial") != "on",
        )
        parts = [f"{result['written']} months of usage written to {payee.name}"]
        if result["skipped_no_bill"]:
            parts.append(f"{result['skipped_no_bill']} had no bill to attach to")
        if result["skipped_partial"]:
            parts.append(f"{result['skipped_partial']} part-months skipped")
        flash(". ".join(parts) + ".", "success" if result["written"] else "warning")
        return redirect(url_for("money.edit_payee", payee_id=payee.id))

    return render_template(
        "money/usage_import.html",
        payees=Payee.query.order_by(Payee.name).all(),
        units=usage_service.UNIT_LABELS,
    )


@bp.route("/bills/<int:bill_id>/usage", methods=["POST"])
@login_required
def set_usage(bill_id):
    """Type a reading straight off a paper bill."""
    bill = db.get_or_404(BillPayment, bill_id)
    bill.usage = _float(request.form.get("usage"))
    bill.service_days = _int(request.form.get("service_days"))
    bill.usage_unit = (
        (request.form.get("usage_unit") or "").strip() or bill.payee.usage_unit
    )
    if bill.usage is not None:
        bill.usage_source = "manual"
    db.session.commit()
    flash(f"Usage recorded for {bill.payee.name}.", "success")
    return redirect(request.referrer or url_for("money.edit_payee",
                                                payee_id=bill.payee_id))


@bp.route("/import/confirm", methods=["POST"])
@login_required
def import_confirm():
    """Step two: apply the confirmed mapping."""
    staged = staging.load() or {}
    headers = staged.get("headers")
    rows = staged.get("rows")
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

    staging.discard()
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
    payee.usage_unit = (form.get("usage_unit") or "").strip() or None
    payee.meter_number = (form.get("meter_number") or "").strip() or None
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
