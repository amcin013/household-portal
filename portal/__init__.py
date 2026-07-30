"""Household portal - application factory."""
import logging
import os

from flask import Flask, request
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db, login_manager
from .themes import (
    DEFAULT_DENSITY, DEFAULT_FONT, DEFAULT_THEME, DENSITIES, FONTS, THEMES,
    theme_css, theme_mode,
)
from .util import register_filters

__version__ = "1.0.0"


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)

    os.makedirs(app.config["INSTANCE_DIR"], exist_ok=True)

    if app.config.get("BEHIND_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db.init_app(app)
    login_manager.init_app(app)
    register_filters(app)

    from .security import init_csrf
    init_csrf(app)

    from . import auth
    auth.init_oauth(app)

    from .views import (
        admin, dashboard, docs, links, money, obligations, places, recipes,
        search,
    )

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(recipes.bp)
    app.register_blueprint(links.bp)
    app.register_blueprint(places.bp)
    app.register_blueprint(money.bp)
    app.register_blueprint(obligations.bp)
    app.register_blueprint(docs.bp)
    app.register_blueprint(search.bp)
    app.register_blueprint(admin.bp)

    register_context(app)
    register_errors(app)

    with app.app_context():
        db.create_all()
        _seed_defaults()

    @app.cli.command("seed")
    def seed_command():
        """Load starter content: the two properties, some links and pages."""
        from .seed import run_seed
        run_seed()

    @app.cli.command("refresh-sensors")
    def refresh_sensors_command():
        """Pull every non-manual sensor. Point cron at this."""
        from .services.sensors import refresh_all
        result = refresh_all()
        print(f"sensors updated: {result['ok']} ok, {result['failed']} failed")

    @app.cli.command("refresh-weather")
    def refresh_weather_command():
        """Warm the weather cache so the dashboard is instant."""
        from .models import Place
        from .services.weather import get_weather
        for place in Place.query.all():
            data = get_weather(place, force=True)
            state = data.get("error") or "ok"
            print(f"{place.name}: {state}")

    return app


DEFAULT_SETTINGS = {
    "site_name": "Household Portal",
    "site_tagline": "Everything for the house, in one place",
    "theme": DEFAULT_THEME,
    "font": DEFAULT_FONT,
    "density": DEFAULT_DENSITY,
    "allow_personal_theme": "1",
    "dashboard_greeting": "1",
    "emergency_note": (
        "If you are covering for someone, start with the Essentials section. "
        "It has the accounts, contacts, and steps that keep the house running."
    ),
}


def _seed_defaults():
    from .models import Setting
    changed = False
    for key, value in DEFAULT_SETTINGS.items():
        if Setting.query.filter_by(key=key).first() is None:
            db.session.add(Setting(key=key, value=value))
            changed = True
    if changed:
        db.session.commit()


def register_context(app):
    """Make settings and the active theme available to every template."""

    @app.context_processor
    def inject_globals():
        from .models import Setting
        from .services.nutrition import NUTRIENT_LABELS

        settings = Setting.all_as_dict()

        theme = settings.get("theme", DEFAULT_THEME)
        font = settings.get("font", DEFAULT_FONT)
        density = settings.get("density", DEFAULT_DENSITY)

        # A signed-in person can override the household look for themselves.
        if (
            settings.get("allow_personal_theme") == "1"
            and current_user.is_authenticated
        ):
            theme = current_user.theme or theme
            font = current_user.font or font

        return {
            "settings": settings,
            "site_name": settings.get("site_name", "Household Portal"),
            "site_tagline": settings.get("site_tagline", ""),
            "theme_key": theme,
            "theme_mode": theme_mode(theme),
            "theme_style": theme_css(theme, font, density),
            "all_themes": THEMES,
            "all_fonts": FONTS,
            "all_densities": DENSITIES,
            "nutrition_labels": NUTRIENT_LABELS,
            "version": __version__,
            "nav_active": request.endpoint or "",
        }


def register_errors(app):
    from flask import render_template

    @app.errorhandler(403)
    def forbidden(error):
        return render_template(
            "error.html",
            code=403,
            title="Not your page",
            message="That area is admin-only. Ask Allen if you need access.",
        ), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            "error.html",
            code=404,
            title="Nothing here",
            message="That page does not exist, or it was renamed.",
        ), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        app.logger.exception("Unhandled error")
        return render_template(
            "error.html",
            code=500,
            title="Something broke",
            message="The portal hit an error. The details are in the server log.",
        ), 500
