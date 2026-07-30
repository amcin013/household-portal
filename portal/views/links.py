"""Quick links - Jellyfin, the router, whatever gets opened often."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db
from ..models import Link

bp = Blueprint("links", __name__, url_prefix="/links")


@bp.route("/")
@login_required
def index():
    links = Link.query.order_by(Link.sort_order, Link.title).all()

    grouped = {}
    for link in links:
        grouped.setdefault(link.category or "General", []).append(link)

    return render_template(
        "links/index.html",
        grouped=sorted(grouped.items()),
        pinned=[l for l in links if l.pinned],
        total=len(links),
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        link = Link()
        db.session.add(link)
        _apply(link, request.form)
        db.session.commit()
        flash(f"Added “{link.title}”.", "success")
        return redirect(url_for("links.index"))
    return render_template("links/edit.html", link=None, categories=_categories())


@bp.route("/<int:link_id>/edit", methods=["GET", "POST"])
@login_required
def edit(link_id):
    link = db.get_or_404(Link, link_id)
    if request.method == "POST":
        _apply(link, request.form)
        db.session.commit()
        flash("Saved.", "success")
        return redirect(url_for("links.index"))
    return render_template("links/edit.html", link=link, categories=_categories())


@bp.route("/<int:link_id>/delete", methods=["POST"])
@login_required
def delete(link_id):
    link = db.get_or_404(Link, link_id)
    db.session.delete(link)
    db.session.commit()
    flash(f"Removed “{link.title}”.", "info")
    return redirect(url_for("links.index"))


@bp.route("/<int:link_id>/pin", methods=["POST"])
@login_required
def toggle_pin(link_id):
    link = db.get_or_404(Link, link_id)
    link.pinned = not link.pinned
    db.session.commit()
    return redirect(request.referrer or url_for("links.index"))


def _categories():
    return sorted({l.category for l in Link.query.all() if l.category})


def _apply(link, form):
    link.title = (form.get("title") or "Untitled").strip()
    url = (form.get("url") or "").strip()
    # People paste "192.168.1.50:8096" - make it a real URL.
    if url and not url.startswith(("http://", "https://", "/")):
        url = "http://" + url
    link.url = url
    link.description = (form.get("description") or "").strip() or None
    link.category = (form.get("category") or "General").strip() or "General"
    link.icon = (form.get("icon") or "").strip()[:16] or None
    link.pinned = form.get("pinned") == "on"
    link.open_new_tab = form.get("open_new_tab") == "on"
    try:
        link.sort_order = int(form.get("sort_order") or 0)
    except ValueError:
        link.sort_order = 0
