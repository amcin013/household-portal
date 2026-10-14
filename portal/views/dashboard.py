"""The landing page, assembled from whichever modules are switched on."""
from datetime import date, timedelta

from flask import Blueprint, render_template, url_for
from flask_login import current_user, login_required

from ..models import (
    Account, Link, Obligation, Page, Place, Recipe, latest_updates,
)
from ..modules import MODULES, layout_for
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


def _glance(ctx):
    """The tile row: five numbers that answer "is anything wrong?" from a doorway.

    Every figure here already exists on some other panel. That is the point -
    this is the summary layer, read from across the room, and each tile links
    to the panel that explains it. A tile whose number cannot be worked out is
    dropped rather than shown as a dash, so the row never pads itself out.
    """
    month = ctx["month"]
    tiles = []

    due = month["count_due"] if "count_due" in month else len(
        [b for b in month["bills"] if b.status == "due"])
    tiles.append({
        "tint": "t1", "icon": "💵", "value": due,
        "label": "bill" + ("" if due == 1 else "s") + " left",
        "href": url_for("money.index"),
        "state": "warn" if month.get("overdue") else "",
    })

    obligations = Obligation.query.filter_by(active=True).count()
    if obligations:
        tiles.append({
            "tint": "t4", "icon": "🧾", "value": obligations,
            "label": "obligation" + ("" if obligations == 1 else "s"),
            "href": url_for("obligations.index"), "state": "",
        })

    try:
        from ..services import disks as disk_service
        report = disk_service.summary()
        roots = [f for f in report.get("filesystems", []) if f.get("mount") == "/"]
        if roots:
            tiles.append({
                "tint": "t3", "icon": "▦", "value": roots[0].get("avail_h", "—"),
                "label": "disk free",
                "href": url_for("system.disks"),
                "state": "bad" if (roots[0].get("use_percent") or 0) >= 90
                         else "warn" if (roots[0].get("use_percent") or 0) >= 75
                         else "",
            })
    except Exception:
        pass

    sensors = sum(len(p.sensors) for p in ctx["places"])
    if sensors:
        tiles.append({
            "tint": "t2", "icon": "🌡️", "value": sensors,
            "label": "sensor" + ("" if sensors == 1 else "s"),
            "href": url_for("places.index"), "state": "",
        })

    recipes = Recipe.query.count()
    if recipes:
        tiles.append({
            "tint": "t5", "icon": "🍽️", "value": recipes,
            "label": "recipe" + ("" if recipes == 1 else "s"),
            "href": url_for("recipes.index"), "state": "",
        })

    return {"tiles": tiles} if tiles else None


def _machine(ctx):
    """The box itself: memory, uptime, load, and every filesystem on it.

    Two sources with different privilege: host stats come straight out of /proc
    and are always current; filesystem sizes come from the root collector's
    hourly JSON and can be stale, which the panel says rather than hides.
    """
    from ..services import host as host_service
    from ..services import disks as disk_service

    info = host_service.summary()
    if not info.get("memory") and not info.get("uptime"):
        return None  # not a Linux box, or /proc is not readable

    try:
        report = disk_service.summary()
    except Exception:
        report = {"available": False, "filesystems": [], "generated_at": None,
                  "stale": False}
    return {"host": info, "report": report}


def _machines(ctx):
    """The VMs with power buttons on them, and nothing else.

    Hidden entirely when the feature is switched off, so a household that does
    not run a hypervisor never sees an empty panel asking to be configured.
    """
    from ..services import machines as vm_service

    summary = vm_service.summary()
    if summary is None:
        return None
    # An unreachable hypervisor is worth showing - it is the one state you want
    # to know about without going looking - but only once it has been set up.
    if not summary["domains"] and not summary["configured"]:
        return None
    summary["domains"] = [
        {**d, "actions": vm_service.actions_for(d)} for d in summary["domains"]
    ]
    return summary


BUILDERS = {
    "glance": _glance,
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
    "machine": _machine,
    "machines": _machines,
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
            panels.append({"key": key, "data": data,
                           "wide": MODULES[key].get("wide", False)})

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
