"""The landing page, assembled from whichever modules are switched on."""
from datetime import date, timedelta

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from ..models import (
    Account, Link, Obligation, Page, Place, Recipe, latest_updates,
)
from ..modules import layout_for
from ..services import money as money_service

bp = Blueprint("dashboard", __name__)


def greeting_for(hour):
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


# Each builder returns the context for one module, or None to skip it entirely.
# Skipping matters for things like alerts, which should take up no room at all
# when there is nothing to say.
def _weather(ctx):
    places = ctx["places"]
    return {"places": places} if places else None


def _radar(ctx):
    places = [p for p in ctx["places"] if p.show_radar and p.has_coords]
    return {"places": places} if places else None


def _alerts(ctx):
    # Filled in on the client from the same fetch the weather cards use, so
    # this only reserves the space.
    return {"places": ctx["places"]} if ctx["places"] else None


def _bills(ctx):
    month = ctx["month"]
    horizon = date.today() + timedelta(days=10)
    due_soon = [
        b for b in month["bills"]
        if b.status == "due" and b.due_date and b.due_date <= horizon
    ][:5]
    return {
        "month": month,
        "due_soon": due_soon,
        "overdue": month["overdue"],
        "has_any": bool(month["bills"]),
    }


def _obligations(ctx):
    rows = (
        Obligation.query.filter_by(active=True)
        .order_by(Obligation.sort_order, Obligation.name)
        .all()
    )
    if not rows:
        return None
    return {
        "obligations": rows,
        "total": sum(o.balance for o in rows),
        "uncleared": sum(len(o.uncleared) for o in rows),
    }


def _accounts(ctx):
    rows = (
        Account.query.filter_by(active=True)
        .order_by(Account.kind, Account.sort_order, Account.name)
        .all()
    )
    if not rows:
        return None
    return {"accounts": rows, "net_worth": money_service.net_worth()}


def _links(ctx):
    return {
        "links": Link.query.filter_by(pinned=True)
        .order_by(Link.sort_order, Link.title).all()
    }


def _essentials(ctx):
    rows = (
        Page.query.filter_by(is_essential=True)
        .order_by(Page.sort_order, Page.title).limit(6).all()
    )
    return {"pages": rows} if rows else None


def _recipes(ctx):
    favorites = (
        Recipe.query.filter_by(favorite=True)
        .order_by(Recipe.updated_at.desc()).limit(4).all()
    )
    recent = Recipe.query.order_by(Recipe.updated_at.desc()).limit(4).all()
    return {"recipes": favorites or recent, "any": bool(recent)}


def _pages(ctx):
    rows = (
        Page.query.filter_by(pinned=True)
        .order_by(Page.sort_order, Page.title).limit(6).all()
    )
    return {"pages": rows} if rows else None


def _storage(ctx):
    from ..services import disks as disk_service
    try:
        report = disk_service.summary()
    except Exception:
        return None
    if not report.get("filesystems"):
        return None
    return {"report": report}


def _activity(ctx):
    rows = latest_updates(6)
    return {"updates": rows} if rows else None


BUILDERS = {
    "weather": _weather,
    "radar": _radar,
    "alerts": _alerts,
    "bills": _bills,
    "obligations": _obligations,
    "accounts": _accounts,
    "links": _links,
    "essentials": _essentials,
    "recipes": _recipes,
    "pages": _pages,
    "storage": _storage,
    "activity": _activity,
}


@bp.route("/")
@login_required
def index():
    import datetime as dt

    places = (
        Place.query.filter_by(show_on_dashboard=True)
        .order_by(Place.sort_order, Place.name)
        .all()
    )

    shared = {"places": places, "month": money_service.month_view()}

    panels = []
    for key in layout_for(current_user):
        builder = BUILDERS.get(key)
        if builder is None:
            continue
        data = builder(shared)
        if data is not None:
            panels.append({"key": key, "data": data})

    return render_template(
        "dashboard.html",
        greeting=greeting_for(dt.datetime.now().hour),
        who=current_user.display_name.split()[0],
        panels=panels,
        needs_weather_fetch=any(
            p["key"] in ("weather", "alerts") for p in panels
        ),
        today=date.today(),
    )
