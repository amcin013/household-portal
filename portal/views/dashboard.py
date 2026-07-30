"""The landing page."""
from datetime import date, timedelta

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from ..models import Link, Page, Place, Recipe, latest_updates
from ..services import money as money_service

bp = Blueprint("dashboard", __name__)


def greeting_for(hour):
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


@bp.route("/")
@login_required
def index():
    import datetime as dt

    places = (
        Place.query.filter_by(show_on_dashboard=True)
        .order_by(Place.sort_order, Place.name)
        .all()
    )

    month = money_service.month_view()
    horizon = date.today() + timedelta(days=10)
    due_soon = [
        b for b in month["bills"]
        if b.status == "due" and b.due_date and b.due_date <= horizon
    ][:8]

    pinned_links = (
        Link.query.filter_by(pinned=True)
        .order_by(Link.sort_order, Link.title)
        .all()
    )
    essentials = (
        Page.query.filter_by(is_essential=True)
        .order_by(Page.sort_order, Page.title)
        .limit(6)
        .all()
    )
    pinned_pages = (
        Page.query.filter_by(pinned=True)
        .order_by(Page.sort_order, Page.title)
        .limit(6)
        .all()
    )
    recent_recipes = (
        Recipe.query.order_by(Recipe.updated_at.desc()).limit(4).all()
    )
    favorites = (
        Recipe.query.filter_by(favorite=True)
        .order_by(Recipe.updated_at.desc())
        .limit(4)
        .all()
    )

    return render_template(
        "dashboard.html",
        greeting=greeting_for(dt.datetime.now().hour),
        who=current_user.display_name.split()[0],
        places=places,
        month=month,
        due_soon=due_soon,
        overdue=month["overdue"],
        pinned_links=pinned_links,
        essentials=essentials,
        pinned_pages=pinned_pages,
        recent_recipes=recent_recipes,
        favorites=favorites,
        updates=latest_updates(6),
        today=date.today(),
    )
