"""Sign-in.

Two modes:
  * Google OAuth (normal). Only emails on the allowlist get in. The allowlist is
    ALLOWED_EMAILS from .env plus anyone an admin has added under Settings.
  * Local password (AUTH_MODE=local). One shared password, useful on a LAN box
    before OAuth is set up. Everyone shares a single "household" account.

The first person to sign in becomes an admin.
"""
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    session, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db, login_manager
from .models import User, utcnow

bp = Blueprint("auth", __name__, url_prefix="/auth")
oauth = OAuth()

GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"


def init_oauth(app):
    oauth.init_app(app)
    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url=GOOGLE_METADATA,
            client_kwargs={"scope": "openid email profile"},
        )


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def google_enabled():
    return bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
    )


def email_allowed(email):
    """Allowed if listed in .env, or already invited as a user."""
    email = (email or "").strip().lower()
    if not email:
        return False
    if email in current_app.config.get("ALLOWED_EMAILS", []):
        return True
    return User.query.filter_by(email=email).first() is not None


def no_users_yet():
    return db.session.query(User.id).first() is None


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@bp.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    next_url = request.args.get("next") or url_for("dashboard.index")
    session["next_url"] = next_url
    return render_template(
        "auth/login.html",
        google_enabled=google_enabled(),
        local_enabled=current_app.config.get("AUTH_MODE") == "local",
    )


@bp.route("/google")
def google_start():
    if not google_enabled():
        flash("Google sign-in is not configured yet.", "error")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route("/callback")
def callback():
    if not google_enabled():
        return redirect(url_for("auth.login"))
    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        current_app.logger.exception("Google sign-in failed")
        flash("Google sign-in did not complete. Please try again.", "error")
        return redirect(url_for("auth.login"))

    info = token.get("userinfo") or {}
    email = (info.get("email") or "").strip().lower()
    if not email or not info.get("email_verified", True):
        flash("Google did not return a verified email address.", "error")
        return redirect(url_for("auth.login"))

    first = no_users_yet()
    if not first and not email_allowed(email):
        current_app.logger.warning("Blocked sign-in attempt from %s", email)
        return render_template("auth/denied.html", email=email), 403

    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(email=email, role="admin" if first else "member")
        db.session.add(user)
    if not user.is_active:
        return render_template("auth/denied.html", email=email, disabled=True), 403

    user.name = info.get("name") or user.name
    user.avatar_url = info.get("picture") or user.avatar_url
    user.last_seen_at = utcnow()
    db.session.commit()

    login_user(user, remember=True)
    if first:
        flash(f"Welcome, {user.display_name}. You are the portal admin.", "success")
    return redirect(session.pop("next_url", None) or url_for("dashboard.index"))


@bp.route("/local", methods=["POST"])
def local_login():
    """Shared-password fallback for AUTH_MODE=local."""
    if current_app.config.get("AUTH_MODE") != "local":
        abort(404)
    expected = current_app.config.get("LOCAL_PASSWORD") or ""
    if not expected:
        flash("Set LOCAL_PASSWORD in .env before using local sign-in.", "error")
        return redirect(url_for("auth.login"))
    if request.form.get("password") != expected:
        flash("That password did not match.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email="household@local").first()
    if user is None:
        user = User(
            email="household@local",
            name="Household",
            role="admin",
        )
        db.session.add(user)
    user.last_seen_at = utcnow()
    db.session.commit()
    login_user(user, remember=True)
    return redirect(session.pop("next_url", None) or url_for("dashboard.index"))


@bp.route("/logout", methods=["POST", "GET"])
@login_required
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("auth.login"))
