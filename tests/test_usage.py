"""Meter readings, and the rate-versus-volume question they exist to answer."""
from datetime import datetime, timedelta, timezone

import pytest

from portal.extensions import db
from portal.models import BillPayment, Payee
from portal.services.usage import (
    UsageError, apply_usage, compare_periods, parse_generic_csv,
    parse_green_button, parse_smt_csv,
)


def green_button(days=90, wh_per_day=30000, multiplier=0, uom=72,
                 start=datetime(2025, 6, 1, tzinfo=timezone.utc)):
    readings = "".join(
        f"<IntervalReading><timePeriod><duration>86400</duration>"
        f"<start>{int((start + timedelta(days=d)).timestamp())}</start></timePeriod>"
        f"<value>{wh_per_day}</value></IntervalReading>"
        for d in range(days)
    )
    return (
        '<?xml version="1.0"?><feed xmlns="http://naesb.org/espi">'
        f"<ReadingType><powerOfTenMultiplier>{multiplier}</powerOfTenMultiplier>"
        f"<uom>{uom}</uom></ReadingType>"
        f"<IntervalBlock>{readings}</IntervalBlock></feed>"
    ).encode()


def smt_csv(days=31, month=7, year=2025, kwh=0.25, intervals=96):
    lines = ["ESIID,USAGE_DATE,USAGE_START_TIME,USAGE_END_TIME,USAGE_KWH,"
             "CONSUMPTION_SURPLUSGENERATION"]
    for day in range(1, days + 1):
        for _ in range(intervals):
            lines.append(f"1044372,{month}/{day}/{year},00:15,00:30,{kwh},")
    return "\n".join(lines)


# --- Green Button ---------------------------------------------------------
def test_green_button_totals_by_month():
    unit, totals = parse_green_button(green_button())
    assert unit == "kWh"
    assert totals["2025-06"] == pytest.approx(900)   # 30 days x 30 kWh
    assert totals["2025-07"] == pytest.approx(930)   # 31 days


def test_green_button_converts_watt_hours_to_kilowatt_hours():
    """Meters report Wh; bills are written in kWh."""
    _, totals = parse_green_button(green_button(days=1, wh_per_day=1000))
    assert totals["2025-06"] == pytest.approx(1.0)


def test_green_button_applies_the_scale_factor():
    """powerOfTenMultiplier is how ESPI avoids decimals."""
    _, totals = parse_green_button(green_button(days=1, wh_per_day=30, multiplier=3))
    assert totals["2025-06"] == pytest.approx(30)  # 30 x 10^3 Wh = 30 kWh


def test_green_button_keeps_non_electric_units():
    unit, _ = parse_green_button(green_button(days=1, uom=169))
    assert unit == "gal"


def test_rubbish_xml_is_rejected_clearly():
    with pytest.raises(UsageError, match="Green Button"):
        parse_green_button(b"not xml at all")


def test_xml_with_no_readings_is_rejected():
    with pytest.raises(UsageError, match="No interval readings"):
        parse_green_button(
            b'<?xml version="1.0"?><feed xmlns="http://naesb.org/espi"></feed>'
        )


# --- Smart Meter Texas ----------------------------------------------------
def test_smt_csv_totals_15_minute_intervals():
    unit, totals = parse_smt_csv(smt_csv())
    assert unit == "kWh"
    assert totals["2025-07"] == pytest.approx(744)  # 96 x 0.25 x 31


def test_smt_reads_the_kwh_column_not_the_start_time():
    """USAGE_START_TIME also contains 'usage', so the unit has to win."""
    _, totals = parse_smt_csv(smt_csv(days=1, intervals=4, kwh=2.5))
    assert totals["2025-07"] == pytest.approx(10)


def test_csv_without_a_usage_column_is_rejected():
    with pytest.raises(UsageError):
        parse_smt_csv("colour,size\nred,large\n")


# --- generic --------------------------------------------------------------
def test_generic_csv_pairs_a_date_with_a_number():
    unit, totals = parse_generic_csv("2025-08-01,1200\n2025-08-15,800\n", "gal")
    assert unit == "gal"
    assert totals["2025-08"] == pytest.approx(2000)


# --- attaching to bills ---------------------------------------------------
@pytest.fixture
def txu(app):
    payee = Payee(name="TXU", usage_unit="kWh")
    db.session.add(payee)
    db.session.flush()
    for period, amount in [("2025-05", 200), ("2025-06", 250), ("2025-07", 300),
                           ("2025-08", 280)]:
        db.session.add(BillPayment(payee_id=payee.id, period=period, amount=amount))
    db.session.commit()
    return payee


def test_usage_lands_on_the_matching_bills(txu):
    result = apply_usage(txu, "kWh",
                         {"2025-05": 900, "2025-06": 1100, "2025-07": 1400,
                          "2025-08": 1300},
                         only_complete=False)
    assert result["written"] == 4
    bill = BillPayment.query.filter_by(period="2025-07").one()
    assert bill.usage == pytest.approx(1400)
    assert bill.usage_unit == "kWh"


def test_months_with_no_bill_are_reported_not_invented(txu):
    result = apply_usage(txu, "kWh", {"2024-01": 500, "2025-06": 1100},
                         only_complete=False)
    assert result["written"] == 1
    assert result["skipped_no_bill"] == 1


def test_part_months_at_the_edges_are_dropped_by_default(txu):
    """A half month of readings against a whole month's bill would give a
    badly wrong rate."""
    result = apply_usage(txu, "kWh",
                         {"2025-05": 400, "2025-06": 1100, "2025-07": 1400,
                          "2025-08": 200})
    assert result["skipped_partial"] == 2
    assert BillPayment.query.filter_by(period="2025-05").one().usage is None
    assert BillPayment.query.filter_by(period="2025-06").one().usage is not None


def test_existing_readings_are_kept_when_overwrite_is_off(txu):
    apply_usage(txu, "kWh", {"2025-06": 1100, "2025-07": 1400}, only_complete=False)
    apply_usage(txu, "kWh", {"2025-06": 9999, "2025-07": 9999},
                overwrite=False, only_complete=False)
    assert BillPayment.query.filter_by(period="2025-06").one().usage == 1100


# --- what it is all for ---------------------------------------------------
def test_unit_cost_is_the_real_rate(txu):
    apply_usage(txu, "kWh", {"2025-07": 1500}, only_complete=False)
    bill = BillPayment.query.filter_by(period="2025-07").one()
    assert bill.unit_cost == pytest.approx(300 / 1500)


def test_usage_per_day_normalises_billing_periods(txu):
    bill = BillPayment.query.filter_by(period="2025-07").one()
    bill.usage, bill.service_days = 930, 31
    db.session.commit()
    assert bill.usage_per_day == pytest.approx(30)


def test_rate_and_volume_effects_add_up_to_the_change(txu):
    """The whole point: a bill went up, and this says which half did it."""
    apply_usage(txu, "kWh", {"2025-06": 1000, "2025-07": 1200}, only_complete=False)
    result = compare_periods(txu, "2025-07", "2025-06")

    assert result["amount_change"] == pytest.approx(50)  # 250 -> 300
    assert result["usage_change"] == pytest.approx(200)
    assert result["rate_effect"] + result["volume_effect"] == pytest.approx(
        result["amount_change"]
    )


def test_a_pure_rate_rise_is_attributed_to_rate(txu):
    """Same consumption, bigger bill - none of it is volume."""
    apply_usage(txu, "kWh", {"2025-06": 1000, "2025-07": 1000}, only_complete=False)
    result = compare_periods(txu, "2025-07", "2025-06")
    assert result["volume_effect"] == pytest.approx(0)
    assert result["rate_effect"] == pytest.approx(50)


def test_comparison_needs_usage_on_both_months(txu):
    apply_usage(txu, "kWh", {"2025-07": 1200}, only_complete=False)
    assert compare_periods(txu, "2025-07", "2025-06") is None
