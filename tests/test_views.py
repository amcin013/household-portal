"""Every page loads, and the things that must stay private stay private."""
import pytest

from portal.extensions import db
from portal.models import Link, Page, Payee, Place, Recipe, User

from .conftest import csrf

PAGES = [
    "/", "/places/", "/places/new", "/docs/", "/docs/essentials", "/docs/new",
    "/links/", "/links/new", "/money/", "/money/payees", "/money/payees/new",
    "/money/accounts", "/money/accounts/new", "/money/recurring",
    "/money/forecast", "/money/import", "/recipes/", "/recipes/new",
    "/recipes/shopping-list", "/search/?q=test", "/settings/",
    "/settings/appearance", "/settings/people", "/settings/foods",
]


@pytest.mark.parametrize("path", PAGES)
def test_page_loads_when_signed_in(auth_client, path):
    assert auth_client.get(path).status_code == 200


@pytest.mark.parametrize("path", PAGES)
def test_page_redirects_to_login_when_signed_out(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_login_page_is_public(client):
    assert client.get("/auth/login").status_code == 200


def test_unknown_page_gives_a_friendly_404(auth_client):
    response = auth_client.get("/docs/does-not-exist")
    assert response.status_code == 404
    assert "Nothing here" in response.get_data(as_text=True)


def test_members_cannot_reach_the_people_page(app, client):
    member = User(email="member@example.com", role="member")
    db.session.add(member)
    db.session.commit()
    with client.session_transaction() as session:
        session["_user_id"] = str(member.id)

    assert client.get("/settings/people").status_code == 403


def test_members_can_still_edit_content(app, client):
    member = User(email="member@example.com", role="member")
    db.session.add(member)
    db.session.commit()
    with client.session_transaction() as session:
        session["_user_id"] = str(member.id)

    assert client.get("/recipes/new").status_code == 200
    assert client.get("/docs/new").status_code == 200


def test_disabled_account_cannot_load_pages(app, client):
    user = User(email="gone@example.com", role="member")
    user.is_active_flag = False
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)

    assert client.get("/").status_code == 302


def test_creating_a_recipe(auth_client):
    token = csrf(auth_client, "/recipes/new")
    response = auth_client.post(
        "/recipes/new",
        data={"_csrf_token": token, "title": "Cornbread", "servings": "8",
              "ing_item": "Cornmeal", "ing_quantity": "1", "ing_unit": "cup",
              "ing_heading": "0", "ing_note": "", "ing_food": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert Recipe.query.filter_by(title="Cornbread").count() == 1


def test_creating_a_page_keeps_a_revision_on_edit(auth_client):
    token = csrf(auth_client, "/docs/new")
    auth_client.post("/docs/new", data={"_csrf_token": token, "title": "Alarm",
                                        "body": "first"}, follow_redirects=True)
    page = Page.query.filter_by(title="Alarm").one()
    assert len(page.revisions) == 0

    token = csrf(auth_client, f"/docs/{page.slug}/edit")
    auth_client.post(f"/docs/{page.slug}/edit",
                     data={"_csrf_token": token, "title": "Alarm", "body": "second"},
                     follow_redirects=True)

    page = Page.query.filter_by(title="Alarm").one()
    assert page.body == "second"
    assert [r.body for r in page.revisions] == ["first"]


def test_bare_host_and_port_becomes_a_usable_url(auth_client):
    token = csrf(auth_client, "/links/new")
    auth_client.post("/links/new",
                     data={"_csrf_token": token, "title": "Jellyfin",
                           "url": "192.168.1.50:8096"},
                     follow_redirects=True)
    assert Link.query.filter_by(title="Jellyfin").one().url == "http://192.168.1.50:8096"


def test_slugs_do_not_collide(auth_client):
    for _ in range(3):
        token = csrf(auth_client, "/docs/new")
        auth_client.post("/docs/new",
                         data={"_csrf_token": token, "title": "Water heater",
                               "body": "x"},
                         follow_redirects=True)

    slugs = sorted(p.slug for p in Page.query.all())
    assert slugs == ["water-heater", "water-heater-2", "water-heater-3"]


def test_deleting_a_place_removes_its_notes(auth_client):
    token = csrf(auth_client, "/places/new")
    auth_client.post("/places/new",
                     data={"_csrf_token": token, "name": "Test House",
                           "city": "Austin"},
                     follow_redirects=True)
    place = Place.query.filter_by(name="Test House").one()

    token = csrf(auth_client, f"/places/{place.slug}")
    auth_client.post(f"/places/{place.slug}/facts",
                     data={"_csrf_token": token, "label": "Wifi", "value": "abc"},
                     follow_redirects=True)

    token = csrf(auth_client, f"/places/{place.slug}/edit")
    auth_client.post(f"/places/{place.slug}/delete", data={"_csrf_token": token},
                     follow_redirects=True)

    assert Place.query.filter_by(name="Test House").count() == 0


def test_search_covers_several_kinds_of_thing(auth_client):
    db.session.add_all([
        Recipe(title="Jellyfish salad", slug="jellyfish-salad", servings=2),
        Page(title="Jellyfin setup", slug="jellyfin-setup", body="how to"),
        Link(title="Jellyfin", url="http://x", category="Media"),
        Payee(name="Jellyfin Premium", category="Subscriptions"),
    ])
    db.session.commit()

    body = auth_client.get("/search/?q=jelly").get_data(as_text=True)
    assert "Jellyfish salad" in body
    assert "Jellyfin setup" in body
    assert "Jellyfin Premium" in body


def test_sensitive_facts_are_not_in_the_page_source_as_plain_text(auth_client):
    """A hidden fact is still in the HTML - make sure it is at least masked,
    so a shoulder-surfer does not read it off a wall tablet."""
    token = csrf(auth_client, "/places/new")
    auth_client.post("/places/new",
                     data={"_csrf_token": token, "name": "Test House"},
                     follow_redirects=True)
    place = Place.query.filter_by(name="Test House").one()

    token = csrf(auth_client, f"/places/{place.slug}")
    auth_client.post(f"/places/{place.slug}/facts",
                     data={"_csrf_token": token, "label": "Alarm code",
                           "value": "1234", "sensitive": "on"},
                     follow_redirects=True)

    body = auth_client.get(f"/places/{place.slug}").get_data(as_text=True)
    assert "••••••••" in body
    assert 'class="revealed" style="display:none"' in body


def test_csrf_is_enforced_when_switched_on(app, client):
    app.config["CSRF_IN_TESTS"] = True
    user = User(email="x@example.com", role="admin")
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)

    response = client.post("/docs/new", data={"title": "No token", "body": "x"})
    assert response.status_code == 400
    assert Page.query.count() == 0


def test_markdown_is_sanitised(auth_client):
    token = csrf(auth_client, "/docs/new")
    auth_client.post(
        "/docs/new",
        data={"_csrf_token": token, "title": "Scripty",
              "body": "Hello <script>alert(1)</script> there"},
        follow_redirects=True,
    )
    body = auth_client.get("/docs/scripty").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body
    assert "Hello" in body
