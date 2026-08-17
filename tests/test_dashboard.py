"""The customisable home page, and the schema sync that keeps upgrades safe."""
import pytest

from portal.extensions import db
from portal.migrations import sync_columns
from portal.models import DashboardWidget, Payee, User
from portal.modules import (
    MODULES, choices_for, default_layout, layout_for, save_layout,
)

from .conftest import csrf


def test_a_new_person_gets_the_default_layout(app):
    user = User(email="new@example.com")
    db.session.add(user)
    db.session.commit()
    assert layout_for(user) == default_layout()
    assert "bills" in layout_for(user)


def test_saving_a_layout_stores_every_widget(app):
    """Off widgets keep a row so their position survives being switched on."""
    user = User(email="a@example.com")
    db.session.add(user)
    db.session.commit()

    save_layout(user, ["bills", "links"], ["links", "bills"])
    assert DashboardWidget.query.count() == len(MODULES)
    assert layout_for(user) == ["links", "bills"]


def test_order_is_respected(app):
    user = User(email="a@example.com")
    db.session.add(user)
    db.session.commit()

    save_layout(user, ["bills", "links", "recipes"], ["recipes", "bills", "links"])
    assert layout_for(user) == ["recipes", "bills", "links"]


def test_switching_a_widget_off_removes_it_from_the_page(app):
    user = User(email="a@example.com")
    db.session.add(user)
    db.session.commit()

    save_layout(user, ["bills"], ["bills", "links"])
    assert "links" not in layout_for(user)

    # Back on, and it returns to where it was rather than the end.
    save_layout(user, ["bills", "links"], ["bills", "links"])
    assert layout_for(user) == ["bills", "links"]


def test_layouts_are_separate_per_person(app):
    one = User(email="one@example.com")
    two = User(email="two@example.com")
    db.session.add_all([one, two])
    db.session.commit()

    save_layout(one, ["bills"], ["bills"])
    assert layout_for(one) == ["bills"]
    assert layout_for(two) == default_layout()


def test_unknown_widget_keys_are_ignored(app):
    """A stored layout keeps working after a widget is renamed or dropped."""
    user = User(email="a@example.com")
    db.session.add(user)
    db.session.flush()
    db.session.add(DashboardWidget(user_id=user.id, widget_key="gone",
                                   position=0, enabled=True))
    db.session.add(DashboardWidget(user_id=user.id, widget_key="bills",
                                   position=1, enabled=True))
    db.session.commit()
    assert layout_for(user) == ["bills"]


def test_choices_lists_every_widget_once(app):
    user = User(email="a@example.com")
    db.session.add(user)
    db.session.commit()
    rows = choices_for(user)
    assert len(rows) == len(MODULES)
    assert len({r["key"] for r in rows}) == len(MODULES)


def test_home_renders_the_chosen_widgets(auth_client, app):
    from flask_login import current_user
    user = User.query.first()
    save_layout(user, ["links"], ["links"])

    body = auth_client.get("/").get_data(as_text=True)
    assert "Quick links" in body
    assert "Recently updated" not in body


def test_layout_page_saves(auth_client, app):
    token = csrf(auth_client, "/settings/home")
    auth_client.post("/settings/home",
                     data={"_csrf_token": token, "enabled": ["bills", "links"],
                           "order": "links,bills"},
                     follow_redirects=True)
    user = User.query.first()
    assert layout_for(user) == ["links", "bills"]


def test_a_widget_with_nothing_to_show_hides_itself(auth_client, app):
    """An empty panel is worse than no panel - obligations with no balances
    should not leave a hole on the page."""
    user = User.query.first()
    save_layout(user, ["obligations"], ["obligations"])
    body = auth_client.get("/").get_data(as_text=True)
    assert "Every panel is switched off" in body or "Obligations" not in body


# --- schema sync ----------------------------------------------------------
def test_sync_columns_adds_a_missing_column(app):
    """create_all makes tables but never columns; a live upgrade depends on
    this filling the gap."""
    from sqlalchemy import inspect, text

    db.session.execute(text("ALTER TABLE payees DROP COLUMN usage_unit"))
    db.session.commit()
    assert "usage_unit" not in {
        c["name"] for c in inspect(db.engine).get_columns("payees")
    }

    added = sync_columns()

    assert "payees.usage_unit" in added
    assert "usage_unit" in {
        c["name"] for c in inspect(db.engine).get_columns("payees")
    }
    # And the model works again.
    db.session.add(Payee(name="TXU", usage_unit="kWh"))
    db.session.commit()
    assert Payee.query.one().usage_unit == "kWh"


def test_sync_columns_is_a_no_op_when_up_to_date(app):
    assert sync_columns() == []
