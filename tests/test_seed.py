"""Seeding, and specifically that it stays safe to run more than once.

Seeding is not a one-time install step: it runs again whenever new starter
content is added, against databases that are already in use. So the rule it
has to obey is that it may fill a gap but must never undo somebody's edit.
"""
from portal.models import Link
from portal.seed import run_seed


def test_backfills_a_blank_link_url(app, db):
    """Seeded links shipped with blank URLs. Re-seeding fills them in."""
    with app.app_context():
        db.session.add(Link(title="Jellyfin", url="", category="Media"))
        db.session.commit()

        run_seed()

        assert Link.query.filter_by(title="Jellyfin").first().url == (
            "http://192.168.50.178:8096"
        )


def test_never_overwrites_a_url_set_by_hand(app, db):
    """The rule that makes re-seeding safe: an edited URL survives."""
    with app.app_context():
        db.session.add(
            Link(title="Jellyfin", url="http://my-own-host:9999", category="Media")
        )
        db.session.commit()

        run_seed()

        assert Link.query.filter_by(title="Jellyfin").first().url == (
            "http://my-own-host:9999"
        )


def test_whitespace_only_url_counts_as_blank(app, db):
    with app.app_context():
        db.session.add(Link(title="Jellyfin", url="   ", category="Media"))
        db.session.commit()

        run_seed()

        assert Link.query.filter_by(title="Jellyfin").first().url == (
            "http://192.168.50.178:8096"
        )


def test_seeding_twice_changes_nothing_the_second_time(app, db):
    with app.app_context():
        run_seed()
        before = {l.title: l.url for l in Link.query.all()}

        run_seed()

        assert {l.title: l.url for l in Link.query.all()} == before
