"""The bills table: sorting, filtering, grouping and inline edits.

Sorting and filtering are done on the server off query parameters, so the page
is fully usable with no JavaScript. These tests exercise that path - the script
layer only makes the same actions instant.
"""
from datetime import date, timedelta

import pytest

from portal.extensions import db
from portal.models import BillPayment, Payee
from portal.services.money import month_view, spending_over_time
from portal.util import current_period, shift_period

from .conftest import csrf


@pytest.fixture
def bills(app):
    db.session.add_all([
        Payee(name="TXU", category="Utilities", typical_amount=270, due_day=12),
        Payee(name="Mortgage", category="Housing", typical_amount=1842, due_day=1),
        Payee(name="Netflix", category="Subscriptions", typical_amount=23, due_day=14,
              autopay=True),
    ])
    db.session.commit()
    month_view(current_period())  # materialises this month's rows
    return current_period()


def rows_in(body):
    """Company names in table order."""
    import re
    return re.findall(r'class="bill-name">\s*<a[^>]*>([^<]+)</a>', body)


def test_default_sort_is_by_due_date(auth_client, bills):
    names = rows_in(auth_client.get("/money/").get_data(as_text=True))
    assert names[0] == "Mortgage"  # due the 1st


def test_sorting_by_name(auth_client, bills):
    names = rows_in(auth_client.get("/money/?sort=name").get_data(as_text=True))
    assert names == sorted(names)


def test_sorting_reverses(auth_client, bills):
    names = rows_in(auth_client.get("/money/?sort=name&dir=desc").get_data(as_text=True))
    assert names == sorted(names, reverse=True)


def test_sorting_by_amount(auth_client, bills):
    names = rows_in(auth_client.get("/money/?sort=amount&dir=desc").get_data(as_text=True))
    assert names[0] == "Mortgage"


def test_search_filters_rows(auth_client, bills):
    names = rows_in(auth_client.get("/money/?q=txu").get_data(as_text=True))
    assert names == ["TXU"]


def test_search_matches_category(auth_client, bills):
    names = rows_in(auth_client.get("/money/?q=housing").get_data(as_text=True))
    assert names == ["Mortgage"]


def test_status_filter_shows_only_unpaid(auth_client, bills):
    """Netflix is on autopay, so it starts paid and drops out of Unpaid."""
    names = rows_in(auth_client.get("/money/?status=due").get_data(as_text=True))
    assert "Netflix" not in names
    assert "TXU" in names


def test_paid_filter(auth_client, bills):
    names = rows_in(auth_client.get("/money/?status=paid").get_data(as_text=True))
    assert names == ["Netflix"]


def test_grouping_by_category(auth_client, bills):
    body = auth_client.get("/money/?group=category").get_data(as_text=True)
    for category in ("Utilities", "Housing", "Subscriptions"):
        assert category in body


def test_filters_survive_in_sort_links(auth_client, bills):
    """A sort link must not throw away the filter you already applied."""
    body = auth_client.get("/money/?q=txu&status=due").get_data(as_text=True)
    assert "q=txu" in body and "status=due" in body


# --- inline edits ---------------------------------------------------------
def one_bill():
    return BillPayment.query.join(Payee).filter(Payee.name == "TXU").one()


def test_toggling_paid_inline(auth_client, bills):
    bill = one_bill()
    token = csrf(auth_client, "/money/")
    response = auth_client.post(f"/money/bills/{bill.id}/quick",
                                data={"_csrf_token": token, "action": "toggle"},
                                headers={"X-Requested-With": "fetch"})
    assert response.status_code == 200
    assert response.get_json()["status"] == "paid"
    assert one_bill().paid_on == date.today()


def test_toggling_back_clears_the_paid_date(auth_client, bills):
    bill = one_bill()
    token = csrf(auth_client, "/money/")
    for _ in range(2):
        auth_client.post(f"/money/bills/{bill.id}/quick",
                         data={"_csrf_token": token, "action": "toggle"},
                         headers={"X-Requested-With": "fetch"})
    refreshed = one_bill()
    assert refreshed.status == "due"
    assert refreshed.paid_on is None


def test_editing_the_amount_inline(auth_client, bills):
    bill = one_bill()
    token = csrf(auth_client, "/money/")
    response = auth_client.post(f"/money/bills/{bill.id}/quick",
                                data={"_csrf_token": token, "amount": "$1,234.56"},
                                headers={"X-Requested-With": "fetch"})
    assert response.get_json()["amount"] == pytest.approx(1234.56)
    assert one_bill().amount == pytest.approx(1234.56)


def test_inline_edit_returns_refreshed_month_totals(auth_client, bills):
    """The stat tiles repaint from this rather than reloading the page."""
    bill = one_bill()
    token = csrf(auth_client, "/money/")
    payload = auth_client.post(f"/money/bills/{bill.id}/quick",
                               data={"_csrf_token": token, "amount": "1000"},
                               headers={"X-Requested-With": "fetch"}).get_json()
    assert payload["month_total"] == pytest.approx(1000 + 1842 + 23)


def test_the_same_route_redirects_for_a_plain_form_post(auth_client, bills):
    """No JavaScript: the cell's Save button posts and comes back to the page."""
    bill = one_bill()
    token = csrf(auth_client, "/money/")
    response = auth_client.post(f"/money/bills/{bill.id}/quick",
                                data={"_csrf_token": token, "amount": "99"})
    assert response.status_code == 302
    assert one_bill().amount == pytest.approx(99)


def test_a_bad_amount_leaves_the_old_one_alone(auth_client, bills):
    bill = one_bill()
    before = bill.amount
    token = csrf(auth_client, "/money/")
    auth_client.post(f"/money/bills/{bill.id}/quick",
                     data={"_csrf_token": token, "amount": "not a number"},
                     headers={"X-Requested-With": "fetch"})
    assert one_bill().amount == before


# --- spending over time ---------------------------------------------------
def test_spending_over_time_totals_by_month(app):
    payee = Payee(name="TXU", category="Utilities")
    db.session.add(payee)
    db.session.flush()
    this = current_period()
    for offset, amount in [(0, 100), (-1, 200), (-2, 300)]:
        db.session.add(BillPayment(payee_id=payee.id, period=shift_period(this, offset),
                                   amount=amount, status="paid"))
    db.session.commit()

    spend = spending_over_time(6)
    assert spend["total"] == pytest.approx(600)
    assert spend["months"] == 3
    assert spend["average"] == pytest.approx(200)
    assert spend["highest"]["total"] == pytest.approx(300)


def test_spending_breaks_down_by_category(app):
    power = Payee(name="TXU", category="Utilities")
    house = Payee(name="Mortgage", category="Housing")
    db.session.add_all([power, house])
    db.session.flush()
    this = current_period()
    db.session.add_all([
        BillPayment(payee_id=power.id, period=this, amount=250),
        BillPayment(payee_id=house.id, period=this, amount=1800),
    ])
    db.session.commit()

    categories = dict(spending_over_time(3)["by_category"])
    assert categories["Housing"] == pytest.approx(1800)
    assert categories["Utilities"] == pytest.approx(250)
    # Biggest first, so the chart reads without sorting again.
    assert spending_over_time(3)["by_category"][0][0] == "Housing"


def test_months_with_nothing_recorded_do_not_drag_the_average_down(app):
    payee = Payee(name="TXU", category="Utilities")
    db.session.add(payee)
    db.session.flush()
    db.session.add(BillPayment(payee_id=payee.id, period=current_period(), amount=400))
    db.session.commit()

    spend = spending_over_time(24)
    assert len(spend["series"]) == 24
    assert spend["months"] == 1
    assert spend["average"] == pytest.approx(400)


def test_trends_page_renders(auth_client, bills):
    body = auth_client.get("/money/forecast").get_data(as_text=True)
    assert "Spending over time" in body
    assert "Forecast" in body
