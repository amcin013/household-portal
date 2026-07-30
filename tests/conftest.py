import re

import pytest

from portal import create_app
from portal.config import TestConfig
from portal.extensions import db as _db
from portal.models import User


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        yield app


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(app, client):
    """A signed-in admin."""
    user = User(email="test@example.com", name="Test Person", role="admin")
    _db.session.add(user)
    _db.session.commit()

    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    return client


def csrf(client, path):
    body = client.get(path).get_data(as_text=True)
    match = re.search(r'name="_csrf_token" value="([^"]+)"', body)
    return match.group(1) if match else ""
