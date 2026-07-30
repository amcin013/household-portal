"""Wiki-style pages: how-tos, instructions, the essentials.

Every save keeps a revision, so nothing typed here is ever lost.
"""
from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from ..extensions import db
from ..models import Page, PageRevision, unique_slug
from ..util import strip_markdown

bp = Blueprint("docs", __name__, url_prefix="/docs")

CATEGORIES = [
    "How-to", "Emergency", "Appliances", "Home systems", "Vehicles",
    "Accounts & bills", "Medical", "Pets", "Travel", "Reference",
]


@bp.route("/")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()

    query = Page.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Page.title.ilike(like), Page.body.ilike(like),
                Page.summary.ilike(like), Page.tags.ilike(like))
        )
    if category:
        query = query.filter_by(category=category)

    pages = query.order_by(
        Page.pinned.desc(), Page.sort_order, Page.title
    ).all()

    grouped = {}
    for page in pages:
        grouped.setdefault(page.category or "Other", []).append(page)

    return render_template(
        "docs/index.html",
        grouped=sorted(grouped.items()),
        pages=pages,
        essentials=[p for p in pages if p.is_essential],
        categories=sorted({p.category for p in Page.query.all() if p.category}),
        q=q,
        category=category,
    )


@bp.route("/essentials")
@login_required
def essentials():
    """The 'somebody else needs to run the house' view. Prints cleanly."""
    pages = (
        Page.query.filter_by(is_essential=True)
        .order_by(Page.sort_order, Page.title)
        .all()
    )
    return render_template("docs/essentials.html", pages=pages)


@bp.route("/<slug>")
@login_required
def detail(slug):
    page = Page.query.filter_by(slug=slug).first_or_404()
    related = (
        Page.query.filter(Page.category == page.category, Page.id != page.id)
        .order_by(Page.title)
        .limit(6)
        .all()
    )
    return render_template("docs/detail.html", page=page, related=related)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        page = Page()
        db.session.add(page)
        _apply(page, request.form)
        db.session.commit()
        flash(f"Created “{page.title}”.", "success")
        return redirect(url_for("docs.detail", slug=page.slug))

    return render_template(
        "docs/edit.html", page=None, categories=CATEGORIES,
        prefill_title=request.args.get("title", ""),
    )


@bp.route("/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit(slug):
    page = Page.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        # Snapshot the old text before overwriting it.
        db.session.add(
            PageRevision(
                page_id=page.id,
                title=page.title,
                body=page.body,
                author_id=page.updated_by_id,
            )
        )
        _apply(page, request.form)
        db.session.commit()
        flash("Saved.", "success")
        return redirect(url_for("docs.detail", slug=page.slug))

    return render_template("docs/edit.html", page=page, categories=CATEGORIES)


@bp.route("/<slug>/history")
@login_required
def history(slug):
    page = Page.query.filter_by(slug=slug).first_or_404()
    return render_template("docs/history.html", page=page)


@bp.route("/<slug>/restore/<int:revision_id>", methods=["POST"])
@login_required
def restore(slug, revision_id):
    page = Page.query.filter_by(slug=slug).first_or_404()
    revision = db.get_or_404(PageRevision, revision_id)
    if revision.page_id != page.id:
        abort(404)

    db.session.add(
        PageRevision(page_id=page.id, title=page.title, body=page.body,
                     author_id=page.updated_by_id)
    )
    page.title = revision.title
    page.body = revision.body
    page.updated_by_id = current_user.id
    db.session.commit()
    flash("Restored that version.", "success")
    return redirect(url_for("docs.detail", slug=page.slug))


@bp.route("/<slug>/delete", methods=["POST"])
@login_required
def delete(slug):
    page = Page.query.filter_by(slug=slug).first_or_404()
    title = page.title
    db.session.delete(page)
    db.session.commit()
    flash(f"Deleted “{title}”.", "info")
    return redirect(url_for("docs.index"))


@bp.route("/<slug>/pin", methods=["POST"])
@login_required
def toggle_pin(slug):
    page = Page.query.filter_by(slug=slug).first_or_404()
    page.pinned = not page.pinned
    db.session.commit()
    return redirect(request.referrer or url_for("docs.detail", slug=slug))


def _apply(page, form):
    page.title = (form.get("title") or "Untitled").strip()
    page.slug = unique_slug(
        Page, form.get("slug") or page.title, "page", ignore_id=page.id
    )
    page.body = form.get("body")
    page.summary = (form.get("summary") or "").strip() or strip_markdown(page.body, 160)
    page.category = (form.get("category") or "How-to").strip()
    page.icon = (form.get("icon") or "").strip()[:16] or None
    page.tag_list = (form.get("tags") or "").split(",")
    page.pinned = form.get("pinned") == "on"
    page.is_essential = form.get("is_essential") == "on"
    page.updated_by_id = current_user.id
    try:
        page.sort_order = int(form.get("sort_order") or 0)
    except ValueError:
        page.sort_order = 0
