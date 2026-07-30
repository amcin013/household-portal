"""CSRF protection for plain HTML forms.

Every state-changing request must carry the session's token. Templates get a
`csrf_token()` global; `{{ csrf_field() }}` renders the hidden input.
"""
import hmac
import secrets

from flask import abort, current_app, request, session
from markupsafe import Markup

FIELD = "_csrf_token"
SESSION_KEY = "_csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def csrf_token():
    if SESSION_KEY not in session:
        session[SESSION_KEY] = secrets.token_urlsafe(32)
    return session[SESSION_KEY]


def csrf_field():
    return Markup(f'<input type="hidden" name="{FIELD}" value="{csrf_token()}">')


def validate():
    sent = request.form.get(FIELD) or request.headers.get("X-CSRF-Token", "")
    expected = session.get(SESSION_KEY, "")
    if not expected or not hmac.compare_digest(str(sent), str(expected)):
        abort(400, description="Your form expired. Go back and try again.")


def init_csrf(app):
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["csrf_field"] = csrf_field

    @app.before_request
    def check_csrf():
        if request.method in SAFE_METHODS:
            return
        if current_app.config.get("TESTING") and not current_app.config.get(
            "CSRF_IN_TESTS"
        ):
            return
        if getattr(current_app.view_functions.get(request.endpoint), "_csrf_exempt", False):
            return
        validate()


def csrf_exempt(view):
    view._csrf_exempt = True
    return view
