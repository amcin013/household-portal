"""Obligations: a balance paid down, and the cheques that do it.

The behaviour that matters is that a cheque written but not sent has not paid
anything yet, and that a new charge puts the balance back up.
"""
from datetime import date, timedelta

import pytest

from portal.extensions import db
from portal.models import Obligation, ObligationEntry


@pytest.fixture
def nancy(app):
    """Half the kids' medical bills - the real shape of it."""
    ob = Obligation(
        slug="kids-medical-nancy", name="Kids medical — Nancy",
        owed_to="Nancy", kind="medical",
        opening_balance=1220.25, payment_amount=67.79,
        frequency="monthly", next_check_number="995094",
    )
    db.session.add(ob)
    db.session.commit()
    return ob


def pay(ob, amount, status="sent", when=None, number=None):
    entry = ObligationEntry(
        obligation_id=ob.id, amount=amount, status=status,
        happened_on=when or date.today(), check_number=number,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def charge(ob, amount, when=None):
    entry = ObligationEntry(
        obligation_id=ob.id, amount=amount, is_charge=True,
        happened_on=when or date.today(),
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def test_a_new_obligation_owes_its_opening_balance(nancy):
    assert nancy.balance == pytest.approx(1220.25)
    assert nancy.total_paid == 0


def test_a_sent_payment_reduces_the_balance(nancy):
    pay(nancy, 67.79)
    assert nancy.balance == pytest.approx(1152.46)


def test_a_cleared_payment_also_counts(nancy):
    pay(nancy, 67.79, status="cleared")
    assert nancy.balance == pytest.approx(1152.46)


def test_a_written_but_unsent_cheque_has_not_paid_anything(nancy):
    """It is on the desk, not at the bank. The balance must not move."""
    pay(nancy, 67.79, status="scheduled")
    assert nancy.balance == pytest.approx(1220.25)
    assert nancy.total_scheduled == pytest.approx(67.79)


def test_projected_balance_looks_past_the_cheques_already_written(nancy):
    pay(nancy, 67.79, status="scheduled")
    pay(nancy, 67.79, status="scheduled")
    assert nancy.balance == pytest.approx(1220.25)
    assert nancy.projected_balance == pytest.approx(1084.67)


def test_a_void_cheque_counts_for_nothing(nancy):
    pay(nancy, 67.79, status="void")
    assert nancy.balance == pytest.approx(1220.25)
    assert nancy.total_scheduled == 0


def test_a_new_charge_puts_the_balance_back_up(nancy):
    """A fresh medical bill arrives after the old one was paid off."""
    for _ in range(18):
        pay(nancy, 67.79)
    assert nancy.balance == pytest.approx(0.03, abs=0.05)

    charge(nancy, 2387.89)
    assert nancy.balance == pytest.approx(2387.92, abs=0.05)
    assert nancy.is_settled is False


def test_payments_remaining_rounds_up(nancy):
    """A part payment still needs a whole cheque."""
    assert nancy.payments_remaining == 19  # 1220.25 / 67.79 = 18.0
    charge(nancy, 10)
    assert nancy.payments_remaining == 19


def test_settled_when_the_balance_reaches_zero(nancy):
    pay(nancy, 1220.25)
    assert nancy.is_settled is True
    assert nancy.payments_remaining == 0


def test_progress_measures_against_everything_ever_owed(nancy):
    pay(nancy, 610.125)
    assert nancy.progress == pytest.approx(0.5)
    charge(nancy, 1220.25)
    assert nancy.progress == pytest.approx(0.25)


def test_uncleared_lists_only_what_is_waiting_on_the_bank(nancy):
    pay(nancy, 67.79, status="sent", number="995094")
    pay(nancy, 67.79, status="cleared", number="995095")
    pay(nancy, 67.79, status="scheduled", number="995096")

    assert [e.check_number for e in nancy.uncleared] == ["995094"]


def test_payoff_date_runs_from_the_last_payment(nancy):
    when = date(2026, 1, 15)
    pay(nancy, 1084.67, when=when)  # two payments left
    payoff = nancy.payoff_date()
    assert payoff == when + timedelta(days=60)


def test_payoff_date_is_unknown_without_a_payment_amount(app):
    ob = Obligation(slug="x", name="X", opening_balance=500, payment_amount=0)
    db.session.add(ob)
    db.session.commit()
    assert ob.payments_remaining is None
    assert ob.payoff_date() is None


def test_entry_labels_read_like_a_chequebook(nancy):
    assert pay(nancy, 10, number="995094").label == "Check 995094"
    assert pay(nancy, 10).label == "Payment"
    assert charge(nancy, 10).label == "Charge"


def test_deleting_an_obligation_takes_its_entries(nancy):
    pay(nancy, 67.79)
    db.session.delete(nancy)
    db.session.commit()
    assert ObligationEntry.query.count() == 0


# --- through the views ----------------------------------------------------
def test_recording_a_cheque_rolls_the_number_forward(auth_client, nancy):
    from .conftest import csrf
    token = csrf(auth_client, f"/money/obligations/{nancy.slug}")
    auth_client.post(
        f"/money/obligations/{nancy.slug}/entries",
        data={"_csrf_token": token, "kind": "payment", "amount": "67.79",
              "check_number": "995094", "status": "sent"},
        follow_redirects=True,
    )
    assert Obligation.query.one().next_check_number == "995095"


def test_scheduling_writes_a_numbered_run_of_cheques(auth_client, nancy):
    from .conftest import csrf
    token = csrf(auth_client, f"/money/obligations/{nancy.slug}")
    auth_client.post(
        f"/money/obligations/{nancy.slug}/schedule",
        data={"_csrf_token": token, "count": "4", "amount": "67.79",
              "start_on": "2026-02-01", "check_number": "995100"},
        follow_redirects=True,
    )
    entries = sorted(
        ObligationEntry.query.all(), key=lambda e: e.check_number or ""
    )
    assert [e.check_number for e in entries] == ["995100", "995101", "995102", "995103"]
    assert all(e.status == "scheduled" for e in entries)
    # Written, not sent - so nothing has been paid down yet.
    assert Obligation.query.one().balance == pytest.approx(1220.25)


def test_marking_a_cheque_cleared_records_the_date(auth_client, nancy):
    from .conftest import csrf
    entry = pay(nancy, 67.79, status="sent")
    token = csrf(auth_client, f"/money/obligations/{nancy.slug}")
    auth_client.post(
        f"/money/obligations/entries/{entry.id}",
        data={"_csrf_token": token, "action": "clear"},
        follow_redirects=True,
    )
    updated = db.session.get(ObligationEntry, entry.id)
    assert updated.status == "cleared"
    assert updated.cleared_on == date.today()


def test_obligation_pages_load(auth_client, nancy):
    assert auth_client.get("/money/obligations/").status_code == 200
    assert auth_client.get(f"/money/obligations/{nancy.slug}").status_code == 200
    assert auth_client.get(f"/money/obligations/{nancy.slug}/edit").status_code == 200
    assert auth_client.get("/money/obligations/new").status_code == 200
