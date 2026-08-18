"""Settings: appearance, people, nutrition reference data."""
from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from ..auth import admin_required
from ..extensions import db
from ..models import Food, Setting, User
from ..modules import choices_for, save_layout
from ..themes import DENSITIES, FONTS, THEMES, themes_by_family

bp = Blueprint("admin", __name__, url_prefix="/settings")


@bp.route("/")
@login_required
def index():
    return render_template(
        "admin/index.html",
        settings=Setting.all_as_dict(),
        user_count=User.query.count(),
        food_count=Food.query.count(),
        google_configured=bool(current_app.config.get("GOOGLE_CLIENT_ID")),
        auth_mode=current_app.config.get("AUTH_MODE"),
    )


@bp.route("/appearance", methods=["GET", "POST"])
@login_required
def appearance():
    if request.method == "POST":
        scope = request.form.get("scope", "household")

        if scope == "personal":
            current_user.theme = request.form.get("theme") or None
            current_user.font = request.form.get("font") or None
            db.session.commit()
            flash("Your personal look is saved.", "success")
            return redirect(url_for("admin.appearance"))

        if not current_user.is_admin:
            flash("Only an admin can change the household look.", "error")
            return redirect(url_for("admin.appearance"))

        for key in ("theme", "font", "density", "site_name", "site_tagline",
                    "emergency_note"):
            if key in request.form:
                Setting.set(key, request.form.get(key))
        Setting.set(
            "allow_personal_theme",
            "1" if request.form.get("allow_personal_theme") == "on" else "0",
        )
        Setting.set(
            "dashboard_greeting",
            "1" if request.form.get("dashboard_greeting") == "on" else "0",
        )
        db.session.commit()
        flash("Appearance updated.", "success")
        return redirect(url_for("admin.appearance"))

    return render_template(
        "admin/appearance.html",
        settings=Setting.all_as_dict(),
        themes=THEMES,
        theme_families=themes_by_family(),
        # Everything the live preview needs, flattened once rather than being
        # dug back out of the nested dicts in JavaScript.
        look_data={
            "themes": {
                key: {"mode": t["mode"], "vars": t["vars"]}
                for key, t in THEMES.items()
            },
            "fonts": {key: f["stack"] for key, f in FONTS.items()},
            "densities": {key: d["scale"] for key, d in DENSITIES.items()},
        },
        fonts=FONTS,
        densities=DENSITIES,
    )


@bp.route("/appearance/reset-personal", methods=["POST"])
@login_required
def reset_personal_theme():
    current_user.theme = None
    current_user.font = None
    db.session.commit()
    flash("Back to the household look.", "info")
    return redirect(url_for("admin.appearance"))


@bp.route("/home", methods=["GET", "POST"])
@login_required
def home_layout():
    """Which panels appear on this person's home page, and in what order."""
    if request.method == "POST":
        order = [k.strip() for k in (request.form.get("order") or "").split(",")
                 if k.strip()]
        save_layout(current_user, request.form.getlist("enabled"), order)
        flash("Home page updated.", "success")
        return redirect(url_for("admin.home_layout"))

    return render_template("admin/home_layout.html", widgets=choices_for(current_user))


@bp.route("/people")
@admin_required
def people():
    return render_template(
        "admin/people.html",
        users=User.query.order_by(User.role, User.email).all(),
        allowed=current_app.config.get("ALLOWED_EMAILS", []),
        google_configured=bool(current_app.config.get("GOOGLE_CLIENT_ID")),
    )


@bp.route("/people/invite", methods=["POST"])
@admin_required
def invite():
    """Pre-creating the account is the invite - the email can then sign in."""
    email = (request.form.get("email") or "").strip().lower()
    if "@" not in email:
        flash("That does not look like an email address.", "error")
        return redirect(url_for("admin.people"))
    if User.query.filter_by(email=email).first():
        flash(f"{email} is already on the list.", "info")
        return redirect(url_for("admin.people"))

    db.session.add(
        User(
            email=email,
            name=(request.form.get("name") or "").strip() or None,
            role="admin" if request.form.get("role") == "admin" else "member",
        )
    )
    db.session.commit()
    flash(f"{email} can now sign in with Google.", "success")
    return redirect(url_for("admin.people"))


@bp.route("/people/<int:user_id>", methods=["POST"])
@admin_required
def update_person(user_id):
    user = db.get_or_404(User, user_id)
    action = request.form.get("action")

    if action == "toggle_active":
        if user.id == current_user.id:
            flash("You cannot switch off your own account.", "error")
        else:
            user.is_active_flag = not user.is_active_flag
            db.session.commit()
    elif action == "toggle_role":
        admins = User.query.filter_by(role="admin").count()
        if user.is_admin and admins <= 1:
            flash("The portal needs at least one admin.", "error")
        else:
            user.role = "member" if user.is_admin else "admin"
            db.session.commit()
    elif action == "delete":
        if user.id == current_user.id:
            flash("You cannot remove yourself.", "error")
        else:
            db.session.delete(user)
            db.session.commit()
            flash(f"Removed {user.email}.", "info")

    return redirect(url_for("admin.people"))


# --- nutrition reference --------------------------------------------------
@bp.route("/foods", methods=["GET", "POST"])
@login_required
def foods():
    if request.method == "POST":
        food = Food(name=(request.form.get("name") or "").strip())
        if not food.name:
            flash("A food needs a name.", "error")
            return redirect(url_for("admin.foods"))
        if Food.query.filter(db.func.lower(Food.name) == food.name.lower()).first():
            flash(f"“{food.name}” is already in the list.", "info")
            return redirect(url_for("admin.foods"))
        _apply_food(food, request.form)
        db.session.add(food)
        db.session.commit()
        flash(f"Added {food.name}.", "success")
        return redirect(url_for("admin.foods"))

    return render_template(
        "admin/foods.html", foods=Food.query.order_by(Food.name).all()
    )


@bp.route("/foods/<int:food_id>", methods=["POST"])
@login_required
def edit_food(food_id):
    food = db.get_or_404(Food, food_id)
    if request.form.get("action") == "delete":
        db.session.delete(food)
        db.session.commit()
        flash(f"Removed {food.name}.", "info")
        return redirect(url_for("admin.foods"))

    food.name = (request.form.get("name") or food.name).strip()
    _apply_food(food, request.form)
    db.session.commit()
    flash("Saved.", "success")
    return redirect(url_for("admin.foods"))


def _apply_food(food, form):
    for field in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg"):
        try:
            setattr(food, field, float(form.get(field) or 0))
        except ValueError:
            setattr(food, field, 0)

    units = {}
    for unit, grams in zip(form.getlist("unit_name"), form.getlist("unit_grams")):
        unit = (unit or "").strip().lower()
        if not unit:
            continue
        try:
            units[unit] = float(grams)
        except (TypeError, ValueError):
            continue
    food.unit_grams = units
