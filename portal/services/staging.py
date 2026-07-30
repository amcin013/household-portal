"""Somewhere to park an upload between reading it and confirming it.

The obvious place is the session, and that is wrong: a session lives in a
cookie, browsers cap those around 4 KB, and five years of a household budget is
far past that. The failure is silent - the browser drops the cookie and the
import simply forgets what it read - so this keeps the payload on disk and puts
only a short token in the session.
"""
import json
import secrets
import time
from pathlib import Path

from flask import current_app, session

TTL_SECONDS = 2 * 60 * 60
KEY = "staged_import"


def _dir():
    path = Path(current_app.config["INSTANCE_DIR"]) / "imports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(payload):
    """Write the payload out and return its token."""
    prune()
    token = secrets.token_urlsafe(16)
    (_dir() / f"{token}.json").write_text(json.dumps(payload))
    session[KEY] = token
    return token


def load(token=None):
    token = token or session.get(KEY)
    if not token:
        return None
    # Tokens are generated here, but never trust one off a request with a path.
    if not token.replace("-", "").replace("_", "").isalnum():
        return None
    path = _dir() / f"{token}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def discard(token=None):
    token = token or session.pop(KEY, None)
    if not token:
        return
    session.pop(KEY, None)
    path = _dir() / f"{token}.json"
    if path.exists():
        path.unlink()


def prune():
    """Drop anything left behind by an import nobody finished."""
    cutoff = time.time() - TTL_SECONDS
    for path in _dir().glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass
