"""Wide sheets - the shape a household budget really ends up in.

The layout under test: companies down the side, months across the top, and a
few summary columns wedged in before the data starts.
"""
import pytest

from portal.extensions import db
from portal.models import BillPayment, Payee
from portal.services.importers import (
    find_month_columns, import_matrix, read_matrix,
)


def sheet(extra_rows=(), years=None, months=None, summary=True):
    year_row = years or [None, None, None, 2021, None, None, 2022, None, None]
    month_row = months or ["Item", "Total", "Estimated",
                           "Jan", "Feb", "Mar", "Jan", "Feb", "Mar"]
    if not summary:
        year_row = [year_row[0]] + year_row[3:]
        month_row = [month_row[0]] + month_row[3:]
    return [year_row, month_row, *extra_rows]


def test_finds_the_month_row_and_maps_columns():
    header, periods = find_month_columns(sheet())
    assert header == 1
    assert periods == {3: "2021-01", 4: "2021-02", 5: "2021-03",
                       6: "2022-01", 7: "2022-02", 8: "2022-03"}


def test_summary_columns_are_never_treated_as_months():
    _, periods = find_month_columns(sheet())
    assert 1 not in periods and 2 not in periods  # Total, Estimated


@pytest.mark.parametrize("word", ["Total", "AVG(ALL)", "AVG(YTD)", "% of Total",
                                  "Estimated", "Budget"])
def test_common_summary_headings_are_ignored(word):
    grid = sheet(months=["Item", word, "x", "Jan", "Feb", "Mar", "Apr", "May", "Jun"])
    _, periods = find_month_columns(grid)
    assert 1 not in periods


def test_year_is_carried_across_columns():
    """The year is written once, in January, and applies to the rest."""
    _, periods = find_month_columns(sheet())
    assert periods[4] == "2021-02"
    assert periods[5] == "2021-03"


def test_year_rolls_over_when_the_label_runs_out():
    """A sheet extended into next year without relabelling still lands right -
    this is exactly what the real budget does past its last year header."""
    grid = [
        [None, 2025, None, None],
        ["Item", "Nov", "Dec", "Jan"],
        ["Atmos", 10, 20, 30],
    ]
    _, periods = find_month_columns(grid)
    assert periods[1] == "2025-11"
    assert periods[2] == "2025-12"
    assert periods[3] == "2026-01"


def test_reads_rows_into_periods():
    grid = sheet([["Atmos", 500, 55, 73.90, 81.81, 93.76, 65.38, 70.10, 62.00]])
    periods, items = read_matrix(grid)

    assert len(items) == 1
    item = items[0]
    assert item["name"] == "Atmos"
    assert item["months"] == 6
    assert item["values"]["2021-01"] == pytest.approx(73.90)
    assert item["values"]["2022-03"] == pytest.approx(62.00)
    assert item["total"] == pytest.approx(446.95)


def test_summary_columns_are_not_imported_as_money():
    """The Total column must not become a month, or it doubles everything."""
    grid = sheet([["Atmos", 99999, 55, 10, 10, 10, 10, 10, 10]])
    _, items = read_matrix(grid)
    assert items[0]["total"] == pytest.approx(60)


def test_unlabelled_totals_rows_are_skipped():
    """A totals row has numbers but no name in the label column."""
    grid = sheet([
        ["Atmos", 100, 55, 10, 10, 10, 10, 10, 10],
        [None, 200, 60, 20, 20, 20, 20, 20, 20],
    ])
    _, items = read_matrix(grid)
    assert [i["name"] for i in items] == ["Atmos"]


def test_gaps_in_a_row_are_left_as_gaps():
    """A utility that started late has no bill for the months before it."""
    grid = sheet([["Starlink", 0, 0, None, None, 110, 110, 110, 110]])
    _, items = read_matrix(grid)
    assert items[0]["months"] == 4
    assert items[0]["first"] == "2021-03"


def test_import_creates_a_payee_and_one_bill_per_month(app):
    grid = sheet([["Atmos", 0, 0, 73.90, 81.81, 93.76, 65.38, 70.10, 62.00]])
    _, items = read_matrix(grid)
    result = import_matrix(items)

    assert result["payees_added"] == 1
    assert result["bills_added"] == 6

    payee = Payee.query.filter_by(name="Atmos").one()
    assert len(payee.payments) == 6
    assert {b.period for b in payee.payments} == {
        "2021-01", "2021-02", "2021-03", "2022-01", "2022-02", "2022-03"
    }


def test_imported_months_are_marked_paid(app):
    """It is history, not a list of things still to do."""
    grid = sheet([["Atmos", 0, 0, 10, 10, 10, 10, 10, 10]])
    _, items = read_matrix(grid)
    import_matrix(items)
    assert all(b.status == "paid" for b in BillPayment.query.all())


def test_typical_amount_uses_recent_months_not_lifetime(app):
    """What it costs now matters more than what it cost in 2021."""
    values = {f"2024-{m:02d}": 100.0 for m in range(1, 13)}
    values.update({f"2025-{m:02d}": 200.0 for m in range(1, 13)})
    import_matrix([{"name": "TXU", "values": values}])

    payee = Payee.query.filter_by(name="TXU").one()
    assert payee.typical_amount == pytest.approx(200)


def test_reimporting_updates_amounts_without_duplicating(app):
    grid = sheet([["Atmos", 0, 0, 10, 10, 10, 10, 10, 10]])
    _, items = read_matrix(grid)
    import_matrix(items)

    items[0]["values"]["2021-01"] = 99.0
    result = import_matrix(items)

    assert result["payees_added"] == 0
    assert result["bills_added"] == 0
    assert Payee.query.count() == 1
    assert BillPayment.query.count() == 6
    bill = BillPayment.query.filter_by(period="2021-01").one()
    assert bill.amount == pytest.approx(99.0)


def test_import_tags_a_property(app):
    from portal.models import Place
    place = Place(name="Secretariat", slug="secretariat")
    db.session.add(place)
    db.session.commit()

    grid = sheet([["TXU", 0, 0, 10, 10, 10, 10, 10, 10]])
    _, items = read_matrix(grid)
    import_matrix(items, place_id=place.id)

    assert Payee.query.filter_by(name="TXU").one().place_id == place.id


def test_a_plain_list_is_not_mistaken_for_a_matrix():
    """A simple two-column sheet has no month headers and must fall through to
    the column-mapping importer instead."""
    grid = [["Company", "Amount"], ["TXU", 145.50], ["Water", 68.20]]
    periods, items = read_matrix(grid)
    assert periods == [] and items == []
