"""Bills, the month view, and the forecast."""
from datetime import date

import pytest

from portal.extensions import db
from portal.models import Account, AccountSnapshot, BillPayment, LedgerItem, Payee
from portal.services.money import (
    due_date_for, ensure_month, forecast, month_view, net_worth,
)
from portal.util import shift_period


@pytest.fixture
def bills(app):
    db.session.add_all([
        Payee(name="TXU", category="Utilities", typical_amount=145.50, due_day=1),
        Payee(name="Water", category="Utilities", typical_amount=68.20, due_day=5),
        Payee(name="Mortgage", category="Housing", typical_amount=1842, due_day=1,
              autopay=True),
        Payee(name="Old cable", typical_amount=90, due_day=1, active=False),
    ])
    db.session.commit()


def test_due_date_clamps_to_short_months():
    """A bill due on the 31st is due the 28th in February, not an invalid date."""
    assert due_date_for("2026-02", 31) == date(2026, 2, 28)
    assert due_date_for("2026-01", 31) == date(2026, 1, 31)
    assert due_date_for("2026-04", 31) == date(2026, 4, 30)


def test_due_date_handles_nonsense_days():
    assert due_date_for("2026-03", 0) == date(2026, 3, 1)
    assert due_date_for("2026-03", None) == date(2026, 3, 1)


def test_ensure_month_creates_one_row_per_active_payee(bills):
    created = ensure_month("2026-08")
    assert len(created) == 3  # the inactive payee is skipped
    assert BillPayment.query.filter_by(period="2026-08").count() == 3


def test_ensure_month_is_idempotent(bills):
    ensure_month("2026-08")
    ensure_month("2026-08")
    ensure_month("2026-08")
    assert BillPayment.query.filter_by(period="2026-08").count() == 3


def test_autopay_bills_start_paid(bills):
    ensure_month("2026-08")
    mortgage = (
        BillPayment.query.join(Payee).filter(Payee.name == "Mortgage").first()
    )
    assert mortgage.status == "paid"
    assert mortgage.paid_on is not None


def test_month_totals(bills):
    view = month_view("2026-08")
    assert view["total"] == pytest.approx(2055.70)
    assert view["paid"] == pytest.approx(1842)
    assert view["remaining"] == pytest.approx(213.70)
    assert view["count_due"] == 2


def test_month_groups_by_category(bills):
    view = month_view("2026-08")
    categories = dict(view["by_category"])
    assert categories["Housing"] == pytest.approx(1842)
    assert categories["Utilities"] == pytest.approx(213.70)


def test_editing_one_month_does_not_change_another(bills):
    month_view("2026-08")
    month_view("2026-09")
    august = BillPayment.query.filter_by(period="2026-08").join(Payee).filter(
        Payee.name == "TXU"
    ).first()
    august.amount = 400
    db.session.commit()

    september = BillPayment.query.filter_by(period="2026-09").join(Payee).filter(
        Payee.name == "TXU"
    ).first()
    assert september.amount == pytest.approx(145.50)


def test_net_worth_subtracts_debts(app):
    savings = Account(name="Savings", kind="savings")
    card = Account(name="Card", kind="debt")
    db.session.add_all([savings, card])
    db.session.flush()
    db.session.add_all([
        AccountSnapshot(account_id=savings.id, as_of=date(2026, 7, 1), balance=10000),
        AccountSnapshot(account_id=card.id, as_of=date(2026, 7, 1), balance=2500),
    ])
    db.session.commit()

    assert net_worth() == pytest.approx(7500)


def test_account_uses_most_recent_snapshot(app):
    acct = Account(name="Savings", kind="savings")
    db.session.add(acct)
    db.session.flush()
    db.session.add_all([
        AccountSnapshot(account_id=acct.id, as_of=date(2026, 5, 1), balance=1000),
        AccountSnapshot(account_id=acct.id, as_of=date(2026, 7, 1), balance=1500),
        AccountSnapshot(account_id=acct.id, as_of=date(2026, 6, 1), balance=1200),
    ])
    db.session.commit()

    assert acct.balance == 1500
    assert acct.change_over(1) == 300


def test_biweekly_income_normalises_to_monthly(app):
    item = LedgerItem(name="Pay", kind="income", amount=3200, frequency="biweekly")
    assert item.monthly_amount == pytest.approx(3200 * 26 / 12)


def test_annual_expense_normalises_to_monthly(app):
    item = LedgerItem(name="Insurance", kind="expense", amount=1200, frequency="annual")
    assert item.monthly_amount == pytest.approx(100)


def test_forecast_projects_cash_forward(app, bills):
    checking = Account(name="Checking", kind="checking")
    db.session.add(checking)
    db.session.flush()
    db.session.add(AccountSnapshot(account_id=checking.id, as_of=date.today(),
                                   balance=5000))
    db.session.add(LedgerItem(name="Pay", kind="income", amount=4000,
                              frequency="monthly"))
    db.session.commit()

    data = forecast(6)
    assert len(data["rows"]) == 6
    # 4000 income - 2055.70 bills = 1944.30 a month
    assert data["monthly_net"] == pytest.approx(1944.30)
    assert data["rows"][0]["cash"] == pytest.approx(5000 + 1944.30)
    assert data["rows"][5]["cash"] == pytest.approx(5000 + 1944.30 * 6)


def test_forecast_flags_runway_when_spending_exceeds_income(app, bills):
    checking = Account(name="Checking", kind="checking")
    db.session.add(checking)
    db.session.flush()
    db.session.add(AccountSnapshot(account_id=checking.id, as_of=date.today(),
                                   balance=6000))
    db.session.commit()

    data = forecast(12)
    assert data["monthly_net"] < 0
    assert data["runway_months"] == 2  # 6000 / 2055.70


def test_forecast_grows_accounts_and_adds_contributions(app):
    tsp = Account(name="TSP", kind="retirement", monthly_contribution=1000,
                  annual_growth_pct=12)
    db.session.add(tsp)
    db.session.flush()
    db.session.add(AccountSnapshot(account_id=tsp.id, as_of=date.today(),
                                   balance=10000))
    db.session.commit()

    data = forecast(1)
    # 10000 * (1 + 0.12/12) + 1000
    assert data["rows"][0]["balances"][tsp.id] == pytest.approx(11100)


def test_shift_period_crosses_years():
    assert shift_period("2026-12", 1) == "2027-01"
    assert shift_period("2026-01", -1) == "2025-12"
    assert shift_period("2026-06", 12) == "2027-06"
