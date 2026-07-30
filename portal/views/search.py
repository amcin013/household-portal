"""One search box across everything in the portal."""
from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import or_

from ..models import Link, Page, Payee, Place, PlaceFact, Recipe
from ..util import strip_markdown

bp = Blueprint("search", __name__, url_prefix="/search")


@bp.route("/")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    if not q:
        return render_template("search.html", q="", groups=[], total=0)

    like = f"%{q}%"
    groups = []

    recipes = Recipe.query.filter(
        or_(Recipe.title.ilike(like), Recipe.description.ilike(like),
            Recipe.tags.ilike(like), Recipe.instructions.ilike(like))
    ).order_by(Recipe.title).limit(20).all()
    if recipes:
        groups.append({
            "label": "Recipes", "icon": "🍳",
            "items": [
                {"title": r.title, "detail": strip_markdown(r.description, 120),
                 "endpoint": "recipes.detail", "params": {"slug": r.slug}}
                for r in recipes
            ],
        })

    pages = Page.query.filter(
        or_(Page.title.ilike(like), Page.body.ilike(like),
            Page.summary.ilike(like), Page.tags.ilike(like))
    ).order_by(Page.title).limit(20).all()
    if pages:
        groups.append({
            "label": "Pages & how-tos", "icon": "📄",
            "items": [
                {"title": p.title, "detail": p.summary or strip_markdown(p.body, 120),
                 "endpoint": "docs.detail", "params": {"slug": p.slug}}
                for p in pages
            ],
        })

    links = Link.query.filter(
        or_(Link.title.ilike(like), Link.description.ilike(like),
            Link.url.ilike(like), Link.category.ilike(like))
    ).order_by(Link.title).limit(20).all()
    if links:
        groups.append({
            "label": "Links", "icon": "🔗",
            "items": [
                {"title": l.title,
                 "detail": l.description or l.url or "No address set yet",
                 "external": l.url,
                 "endpoint": "links.edit", "params": {"link_id": l.id}}
                for l in links
            ],
        })

    payees = Payee.query.filter(
        or_(Payee.name.ilike(like), Payee.notes.ilike(like),
            Payee.category.ilike(like))
    ).order_by(Payee.name).limit(20).all()
    if payees:
        groups.append({
            "label": "Bills", "icon": "💵",
            "items": [
                {"title": p.name,
                 "detail": f"{p.category} · due the {p.due_day}",
                 "endpoint": "money.edit_payee", "params": {"payee_id": p.id}}
                for p in payees
            ],
        })

    places = Place.query.filter(
        or_(Place.name.ilike(like), Place.address.ilike(like),
            Place.city.ilike(like), Place.notes.ilike(like))
    ).all()
    facts = PlaceFact.query.filter(
        or_(PlaceFact.label.ilike(like), PlaceFact.value.ilike(like))
    ).limit(20).all()
    place_items = [
        {"title": p.name, "detail": p.label,
         "endpoint": "places.detail", "params": {"slug": p.slug}}
        for p in places
    ] + [
        {"title": f.label,
         "detail": f"{f.place.name} · {'hidden' if f.sensitive else (f.value or '')[:80]}",
         "endpoint": "places.detail", "params": {"slug": f.place.slug}}
        for f in facts
    ]
    if place_items:
        groups.append({"label": "Places", "icon": "🏠", "items": place_items})

    total = sum(len(g["items"]) for g in groups)
    return render_template("search.html", q=q, groups=groups, total=total)
