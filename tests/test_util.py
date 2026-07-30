"""Formatting helpers. Quantities matter most - a cook reads these."""
import pytest

from portal.util import (
    money, money_short, month_label, pretty_quantity, shift_period,
    strip_markdown,
)


@pytest.mark.parametrize("value,expected", [
    (None, ""),
    (0, "0"),
    (1, "1"),
    (3, "3"),
    (0.5, "½"),
    (0.25, "¼"),
    (0.75, "¾"),
    (0.125, "⅛"),
    (1 / 3, "⅓"),
    (2 / 3, "⅔"),
    (1 / 6, "⅙"),
    (5 / 6, "⅚"),
    (1 / 5, "⅕"),
    (1.5, "1½"),
    (2.25, "2¼"),
    (1.75, "1¾"),
    (7 / 6, "1⅙"),
    (4 / 3, "1⅓"),
])
def test_pretty_quantity(value, expected):
    assert pretty_quantity(value) == expected


def test_pretty_quantity_falls_back_to_a_decimal():
    """A quantity that is not close to a common fraction stays a number
    rather than being forced into a wrong one."""
    assert pretty_quantity(0.07) == "0.07"


def test_scaling_a_half_batch_reads_as_fractions():
    """The real point: halving 1½ lb should say ¾, not 0.75."""
    assert pretty_quantity(1.5 / 2) == "¾"
    assert pretty_quantity(0.5 / 2) == "¼"
    assert pretty_quantity(2 / 3 / 2) == "⅓"


@pytest.mark.parametrize("value,expected", [
    (0, "$0.00"), (1234.5, "$1,234.50"), (-650, "-$650.00"), (None, ""),
])
def test_money(value, expected):
    assert money(value) == expected


def test_money_short_drops_the_cents():
    assert money_short(1842.75) == "$1,843"
    assert money_short(-420) == "-$420"


def test_month_label():
    assert month_label("2026-07") == "July 2026"
    assert month_label("nonsense") == "nonsense"


def test_shift_period():
    assert shift_period("2026-12", 1) == "2027-01"
    assert shift_period("2026-01", -1) == "2025-12"


def test_strip_markdown_makes_a_summary():
    text = "## Heading\n\nSome **bold** text with a [link](http://x)."
    plain = strip_markdown(text, 200)
    assert "#" not in plain and "**" not in plain
    assert "Some" in plain


def test_strip_markdown_truncates():
    assert strip_markdown("word " * 100, 20).endswith("…")


@pytest.mark.parametrize("value", [0.07, 0.03, 0.7, 1.4, 0.09, 2.9])
def test_small_or_odd_quantities_are_never_forced_into_a_wrong_fraction(value):
    """The nearest eighth of 0.07 is 1/8 - nearly double it. Showing that as
    a pinch-and-a-bit would be a real error in a kitchen."""
    result = pretty_quantity(value)
    if any(g in result for g in "⅛⅙⅕¼⅓⅜⅖½⅗⅝⅔¾⅘⅚⅞"):
        # If it did use a fraction, it has to be an honest one.
        assert abs(float(eval_fraction(result)) - value) <= 0.02 * value


GLYPHS = {"⅛": 0.125, "⅙": 1/6, "⅕": 0.2, "¼": 0.25, "⅓": 1/3, "⅜": 0.375,
          "⅖": 0.4, "½": 0.5, "⅗": 0.6, "⅝": 0.625, "⅔": 2/3, "¾": 0.75,
          "⅘": 0.8, "⅚": 5/6, "⅞": 0.875}


def eval_fraction(text):
    whole = "".join(c for c in text if c.isdigit())
    glyph = next((c for c in text if c in GLYPHS), None)
    return (int(whole) if whole else 0) + (GLYPHS[glyph] if glyph else 0)
