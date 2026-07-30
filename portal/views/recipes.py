"""Recipes: browse, cook, edit. Scaling and nutrition live in services/nutrition."""
from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from ..extensions import db
from ..models import Food, Recipe, RecipeIngredient, unique_slug
from ..services.nutrition import nutrition_for, scale_ingredients, shopping_list

bp = Blueprint("recipes", __name__, url_prefix="/recipes")


@bp.route("/")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    course = (request.args.get("course") or "").strip()
    tag = (request.args.get("tag") or "").strip()

    query = Recipe.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Recipe.title.ilike(like),
                Recipe.description.ilike(like),
                Recipe.tags.ilike(like),
                Recipe.instructions.ilike(like),
            )
        )
    if course:
        query = query.filter_by(course=course)
    if tag:
        query = query.filter(Recipe.tags.ilike(f"%{tag}%"))

    recipes = query.order_by(Recipe.favorite.desc(), Recipe.title).all()

    courses = sorted(
        {r.course for r in Recipe.query.all() if r.course}
    )
    tags = sorted({t for r in Recipe.query.all() for t in r.tag_list})

    return render_template(
        "recipes/index.html",
        recipes=recipes,
        courses=courses,
        tags=tags,
        q=q,
        course=course,
        tag=tag,
    )


@bp.route("/<slug>")
@login_required
def detail(slug):
    recipe = Recipe.query.filter_by(slug=slug).first_or_404()

    try:
        servings = int(request.args.get("servings") or recipe.servings or 1)
    except ValueError:
        servings = recipe.servings or 1
    servings = max(1, min(servings, 200))

    rows, factor = scale_ingredients(recipe, servings)
    nutrition = nutrition_for(recipe, servings)

    return render_template(
        "recipes/detail.html",
        recipe=recipe,
        rows=rows,
        factor=factor,
        servings=servings,
        nutrition=nutrition,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        recipe = Recipe(created_by_id=current_user.id)
        db.session.add(recipe)
        _apply_form(recipe, request.form)
        db.session.commit()
        flash(f"Added “{recipe.title}”.", "success")
        return redirect(url_for("recipes.detail", slug=recipe.slug))

    return render_template(
        "recipes/edit.html", recipe=None, foods=Food.query.order_by(Food.name).all()
    )


@bp.route("/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit(slug):
    recipe = Recipe.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        _apply_form(recipe, request.form)
        db.session.commit()
        flash("Saved.", "success")
        return redirect(url_for("recipes.detail", slug=recipe.slug))

    return render_template(
        "recipes/edit.html", recipe=recipe, foods=Food.query.order_by(Food.name).all()
    )


@bp.route("/<slug>/delete", methods=["POST"])
@login_required
def delete(slug):
    recipe = Recipe.query.filter_by(slug=slug).first_or_404()
    title = recipe.title
    db.session.delete(recipe)
    db.session.commit()
    flash(f"Deleted “{title}”.", "info")
    return redirect(url_for("recipes.index"))


@bp.route("/<slug>/favorite", methods=["POST"])
@login_required
def toggle_favorite(slug):
    recipe = Recipe.query.filter_by(slug=slug).first_or_404()
    recipe.favorite = not recipe.favorite
    db.session.commit()
    return redirect(request.referrer or url_for("recipes.detail", slug=recipe.slug))


@bp.route("/shopping-list", methods=["GET", "POST"])
@login_required
def shopping():
    """Pick a few recipes and servings, get one combined list."""
    selections = []
    if request.method == "POST":
        for rid in request.form.getlist("recipe_id"):
            recipe = db.session.get(Recipe, int(rid))
            if recipe is None:
                continue
            raw = request.form.get(f"servings_{rid}") or recipe.servings
            try:
                servings = max(1, min(int(raw), 200))
            except ValueError:
                servings = recipe.servings or 1
            selections.append((recipe, servings))

    items, loose = shopping_list(selections) if selections else ([], [])
    return render_template(
        "recipes/shopping.html",
        all_recipes=Recipe.query.order_by(Recipe.title).all(),
        selections=selections,
        items=items,
        loose=loose,
    )


def _apply_form(recipe, form):
    recipe.title = (form.get("title") or "Untitled").strip()
    recipe.slug = unique_slug(
        Recipe, form.get("slug") or recipe.title, "recipe", ignore_id=recipe.id
    )
    recipe.description = form.get("description")
    recipe.instructions = form.get("instructions")
    recipe.notes = form.get("notes")
    recipe.source = form.get("source")
    recipe.source_url = form.get("source_url")
    recipe.image_url = form.get("image_url")
    recipe.course = (form.get("course") or "").strip() or None
    recipe.serving_noun = (form.get("serving_noun") or "servings").strip()
    recipe.tag_list = (form.get("tags") or "").split(",")
    recipe.favorite = form.get("favorite") == "on"
    recipe.servings = _int(form.get("servings"), 4) or 4
    recipe.prep_minutes = _int(form.get("prep_minutes"))
    recipe.cook_minutes = _int(form.get("cook_minutes"))

    _apply_ingredients(recipe, form)


def _apply_ingredients(recipe, form):
    """Ingredient rows arrive as parallel lists from the repeating form fields."""
    quantities = form.getlist("ing_quantity")
    units = form.getlist("ing_unit")
    items = form.getlist("ing_item")
    notes = form.getlist("ing_note")
    headings = form.getlist("ing_heading")  # "1"/"0" per row
    food_ids = form.getlist("ing_food")

    recipe.ingredients.clear()
    db.session.flush()

    position = 0
    for idx, name in enumerate(items):
        name = (name or "").strip()
        if not name:
            continue
        is_heading = idx < len(headings) and headings[idx] == "1"
        food_id = _int(food_ids[idx]) if idx < len(food_ids) else None
        recipe.ingredients.append(
            RecipeIngredient(
                position=position,
                quantity=None if is_heading else _float(_at(quantities, idx)),
                unit=None if is_heading else (_at(units, idx) or "").strip() or None,
                item=name,
                note=(_at(notes, idx) or "").strip() or None,
                heading=is_heading,
                food_id=None if is_heading else (food_id or None),
            )
        )
        position += 1


def _at(seq, idx, default=""):
    return seq[idx] if idx < len(seq) else default


def _int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _float(value, default=None):
    """Accepts '1 1/2', '1/2' and '1.5' - people type fractions."""
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        if " " in text and "/" in text:
            whole, frac = text.split(" ", 1)
            num, den = frac.split("/")
            return float(whole) + float(num) / float(den)
        if "/" in text:
            num, den = text.split("/")
            return float(num) / float(den)
        return float(text)
    except (TypeError, ValueError, ZeroDivisionError):
        return default
