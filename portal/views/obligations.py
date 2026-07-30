"""Obligations - a balance being paid down, and the cheques that do it."""
from datetime import date, datetime

from flask import (
    Blueprint, flash, redirect, render_template, request, url_for,
)
from flask_login import login_required

from ..extensions import db
from ..models import Obligation, ObligationEntry, unique_slug

bp = Blueprint("obligations", __name__, url_prefix="/money/obligations")

KINDS = {
    "support": "Child support",
    "medical": "Medical share",
    "loan": "Loan or judgement",
    "other": "Other",
}


@bp.route("/")
@login_required
def index():
    rows = Obligation.query.order_by(
        Obligation.active.desc(), Obligation.sort_order, Obligation.name
    ).all()
    return render_template(
        "money/obligations.html",
        obligations=rows,
        kinds=KINDS,
        total_owed=sum(o.balance for o in rows if o.active),
        uncleared=sum(len(o.uncleared) for o in rows),
    )


@bp.route("/<slug>")
@login_required
def detail(slug):
    ob = Obligation.query.filter_by(slug=slug).first_or_404()
    entries = sorted(
        ob.entries, key=lambda e: (e.happened_on or date.min, e.id), reverse=True
    )

    # A running balance read the way a chequebook is - oldest first, then
    # flipped, so each row shows what was left after it.
    running, ledger = ob.opening_balance or 0, []
    for entry in sorted(ob.entries, key=lambda e: (e.happened_on or date.min, e.id)):
        if entry.is_charge:
            running += entry.amount or 0
        elif entry.status in ("sent", "cleared"):
            running -= entry.amount or 0
        ledger.append({"entry": entry, "balance": running})
    ledger.reverse()

    return render_template(
        "money/obligation_detail.html",
        ob=ob, entries=entries, ledger=ledger, kinds=KINDS,
        today=date.today(),
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        ob = Obligation()
        db.session.add(ob)
        _apply(ob, request.form)
        db.session.commit()
        flash(f"Added {ob.name}.", "success")
        return redirect(url_for("obligations.detail", slug=ob.slug))
    return render_template("money/obligation_edit.html", ob=None, kinds=KINDS)


@bp.route("/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit(slug):
    ob = Obligation.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        _apply(ob, request.form)
        db.session.commit()
        flash("Saved.", "success")
        return redirect(url_for("obligations.detail", slug=ob.slug))
    return render_template("money/obligation_edit.html", ob=ob, kinds=KINDS)


@bp.route("/<slug>/delete", methods=["POST"])
@login_required
def delete(slug):
    ob = Obligation.query.filter_by(slug=slug).first_or_404()
    name = ob.name
    db.session.delete(ob)
    db.session.commit()
    flash(f"Removed {name}.", "info")
    return redirect(url_for("obligations.index"))


# --- entries --------------------------------------------------------------
@bp.route("/<slug>/entries", methods=["POST"])
@login_required
def add_entry(slug):
    ob = Obligation.query.filter_by(slug=slug).first_or_404()
    amount = _float(request.form.get("amount"))
    if amount is None:
        flash("That amount was not a number.", "error")
        return redirect(url_for("obligations.detail", slug=slug))

    is_charge = request.form.get("kind") == "charge"
    entry = ObligationEntry(
        obligation_id=ob.id,
        happened_on=_date(request.form.get("happened_on")) or date.today(),
        amount=abs(amount),
        is_charge=is_charge,
        status="charge" if is_charge else (request.form.get("status") or "sent"),
        check_number=(request.form.get("check_number") or "").strip() or None,
        note=(request.form.get("note") or "").strip() or None,
    )
    if is_charge:
        entry.status = "sent"  # not meaningful for a charge, keep it valid
    db.session.add(entry)

    # Roll the cheque book forward so the next one is pre-filled.
    if entry.check_number and entry.check_number.isdigit():
        ob.next_check_number = str(int(entry.check_number) + 1)

    db.session.commit()
    flash("Recorded." if not is_charge else "Charge added.", "success")
    return redirect(url_for("obligations.detail", slug=slug))


@bp.route("/entries/<int:entry_id>", methods=["POST"])
@login_required
def update_entry(entry_id):
    entry = db.get_or_404(ObligationEntry, entry_id)
    slug = entry.obligation.slug
    action = request.form.get("action")

    if action == "delete":
        db.session.delete(entry)
        db.session.commit()
        flash("Removed.", "info")
        return redirect(url_for("obligations.detail", slug=slug))

    if action == "clear":
        entry.status = "cleared"
        entry.cleared_on = _date(request.form.get("cleared_on")) or date.today()
    elif action == "send":
        entry.status = "sent"
    elif action == "void":
        entry.status = "void"
    else:
        amount = _float(request.form.get("amount"))
        if amount is not None:
            entry.amount = abs(amount)
        entry.happened_on = _date(request.form.get("happened_on")) or entry.happened_on
        entry.check_number = (request.form.get("check_number") or "").strip() or None
        entry.note = (request.form.get("note") or "").strip() or None
        status = request.form.get("status")
        if status in ("scheduled", "sent", "cleared", "void"):
            entry.status = status

    db.session.commit()
    return redirect(url_for("obligations.detail", slug=slug))


@bp.route("/<slug>/schedule", methods=["POST"])
@login_required
def schedule(slug):
    """Write out the next N cheques in one go, numbered in sequence."""
    ob = Obligation.query.filter_by(slug=slug).first_or_404()
    count = _int(request.form.get("count"), 0) or 0
    amount = _float(request.form.get("amount")) or ob.payment_amount or 0
    start = _date(request.form.get("start_on")) or date.today()
    number = (request.form.get("check_number") or ob.next_check_number or "").strip()

    if count < 1 or amount <= 0:
        flash("Need a number of payments and an amount.", "error")
        return redirect(url_for("obligations.detail", slug=slug))
    count = min(count, 60)

    step = 14 if ob.frequency == "biweekly" else 30
    from datetime import timedelta

    for i in range(count):
        db.session.add(
            ObligationEntry(
                obligation_id=ob.id,
                happened_on=start + timedelta(days=step * i),
                amount=amount,
                status="scheduled",
                check_number=(str(int(number) + i) if number.isdigit() else None),
            )
        )
    if number.isdigit():
        ob.next_check_number = str(int(number) + count)

    db.session.commit()
    flash(f"Scheduled {count} payments.", "success")
    return redirect(url_for("obligations.detail", slug=slug))


# --- helpers --------------------------------------------------------------
def _apply(ob, form):
    ob.name = (form.get("name") or "Untitled").strip()
    ob.slug = unique_slug(Obligation, form.get("slug") or ob.name, "obligation",
                          ignore_id=ob.id)
    ob.owed_to = (form.get("owed_to") or "").strip() or None
    ob.kind = form.get("kind") or "other"
    ob.opening_balance = _float(form.get("opening_balance"), 0) or 0
    ob.payment_amount = _float(form.get("payment_amount"), 0) or 0
    ob.frequency = form.get("frequency") or "monthly"
    ob.pays_by = form.get("pays_by") or "check"
    ob.next_check_number = (form.get("next_check_number") or "").strip() or None
    ob.account_hint = (form.get("account_hint") or "").strip() or None
    ob.active = form.get("active") == "on"
    ob.notes = form.get("notes")
    ob.sort_order = _int(form.get("sort_order"), 0) or 0


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
