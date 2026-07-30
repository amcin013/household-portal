"""Meter readings: Green Button, Smart Meter Texas, or a plain CSV.

Recording what a utility cost tells you half the story. Recording what you
actually used tells you the other half - whether a bill went up because the
rate rose or because the house drew more.

Three ways in:

  Green Button XML   the national standard (ESPI). Any utility with a
                     "Download My Data" button produces it.
  Smart Meter Texas  CSV of 15-minute interval data from the smart meter
                     itself. In deregulated Texas this comes from the wires
                     company (Oncor and the like), not the retailer, so it is
                     available whoever you buy electricity from - and it holds
                     13 months of history.
  Plain CSV          a date column and a usage column. Covers the water and
                     gas portals that export something simpler.

All three are reduced to a monthly total, because that is the grain the bills
are at. Interval detail is deliberately not stored: it is a lot of rows to
answer questions this portal does not ask.
"""
import csv
import io
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone

from ..extensions import db
from ..models import BillPayment, Payee

ESPI_NS = {"espi": "http://naesb.org/espi", "atom": "http://www.w3.org/2005/Atom"}

# Unit of measure codes used by ESPI. 72 is Wh, 119 is cubic feet, 169 gallons.
UOM = {5: "A", 29: "V", 31: "J", 33: "Hz", 38: "W", 42: "m3", 61: "VA",
       72: "Wh", 119: "ft3", 125: "ft3", 128: "gal", 169: "gal"}

UNIT_LABELS = {
    "kWh": "kWh (electricity)",
    "ccf": "ccf (gas, hundred cubic feet)",
    "therm": "therms (gas)",
    "gal": "gallons (water)",
    "kgal": "thousand gallons (water)",
}


class UsageError(Exception):
    pass


def _period(dt):
    return f"{dt.year:04d}-{dt.month:02d}"


# --------------------------------------------------------------------------
# Green Button / ESPI XML
# --------------------------------------------------------------------------
def parse_green_button(raw):
    """Monthly totals out of a Green Button export.

    Returns (unit, {period: total}).
    """
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise UsageError(f"That does not look like Green Button XML: {exc}")

    # ReadingType carries the units and the scale the values are written at.
    multiplier, unit = 0, "Wh"
    for rt in root.iter():
        if not rt.tag.endswith("ReadingType"):
            continue
        for child in rt:
            if child.tag.endswith("powerOfTenMultiplier"):
                multiplier = int((child.text or "0").strip())
            elif child.tag.endswith("uom"):
                unit = UOM.get(int((child.text or "72").strip()), "Wh")
        break

    totals = defaultdict(float)
    readings = 0
    for reading in root.iter():
        if not reading.tag.endswith("IntervalReading"):
            continue
        start = value = None
        for child in reading.iter():
            if child.tag.endswith("start") and start is None:
                start = int((child.text or "0").strip())
            elif child.tag.endswith("value") and value is None:
                value = float((child.text or "0").strip())
        if start is None or value is None:
            continue
        when = datetime.fromtimestamp(start, tz=timezone.utc)
        totals[_period(when)] += value * (10 ** multiplier)
        readings += 1

    if not readings:
        raise UsageError("No interval readings found in that file.")

    # Wh is what meters report; kWh is what bills are written in.
    if unit == "Wh":
        totals = {p: v / 1000 for p, v in totals.items()}
        unit = "kWh"

    return unit, dict(totals)


# --------------------------------------------------------------------------
# Smart Meter Texas CSV
# --------------------------------------------------------------------------
SMT_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def parse_smt_csv(text):
    """Smart Meter Texas 15-minute interval export.

    Columns are ESIID, USAGE_DATE (or DATE), USAGE_START_TIME, USAGE_KWH and
    friends. Only the date and the kWh matter here.
    """
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise UsageError("That CSV was empty.")

    header_idx, header = None, None
    for idx, row in enumerate(rows[:20]):
        lowered = [str(c).strip().lower() for c in row]
        if any("usage" in c for c in lowered) and any(
            "date" in c or "time" in c for c in lowered
        ):
            header_idx, header = idx, lowered
            break
    if header is None:
        raise UsageError(
            "Could not find a header row with a date and a usage column."
        )

    def column(*names):
        for want in names:
            for i, name in enumerate(header):
                if want in name:
                    return i
        return None

    date_col = column("usage_date", "date")
    # Careful: USAGE_START_TIME also contains "usage", so ask for the kWh
    # column by its unit first.
    usage_col = column("kwh", "usage_kwh", "consumption", "usage")
    if date_col is None or usage_col is None:
        raise UsageError("That CSV needs a date column and a usage column.")

    totals = defaultdict(float)
    counted = skipped = 0
    for row in rows[header_idx + 1:]:
        if len(row) <= max(date_col, usage_col):
            continue
        when = _parse_date(row[date_col])
        if when is None:
            skipped += 1
            continue
        try:
            totals[_period(when)] += float(str(row[usage_col]).replace(",", "").strip())
            counted += 1
        except ValueError:
            skipped += 1

    if not counted:
        raise UsageError("No readable rows in that CSV.")
    return "kWh", dict(totals)


def _parse_date(text):
    text = str(text).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%d/%m/%Y",
                "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %H:%M", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:len(fmt) + 8].strip(), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Anything else with a date and a number
# --------------------------------------------------------------------------
def parse_generic_csv(text, unit="kWh"):
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        raise UsageError("That CSV was empty.")

    totals = defaultdict(float)
    counted = 0
    for row in rows:
        when = usage = None
        for cell in row:
            if when is None:
                when = _parse_date(cell)
                if when is not None:
                    continue
            if usage is None:
                try:
                    usage = float(str(cell).replace(",", "").replace("$", "").strip())
                except (TypeError, ValueError):
                    pass
        if when is not None and usage is not None:
            totals[_period(when)] += usage
            counted += 1

    if not counted:
        raise UsageError("Found no rows with both a date and a number.")
    return unit, dict(totals)


def read_usage_file(file_storage, unit_hint=None):
    """Work out what kind of export this is and reduce it to monthly totals."""
    name = (file_storage.filename or "").lower()
    raw = file_storage.read()

    if name.endswith(".xml") or raw.lstrip()[:200].find(b"<?xml") == 0:
        return parse_green_button(raw)

    text = raw.decode("utf-8-sig", errors="replace")
    if "usage_kwh" in text[:4000].lower() or "esiid" in text[:4000].lower():
        return parse_smt_csv(text)
    try:
        return parse_smt_csv(text)
    except UsageError:
        return parse_generic_csv(text, unit_hint or "kWh")


# --------------------------------------------------------------------------
# Attaching it to bills
# --------------------------------------------------------------------------
def apply_usage(payee, unit, totals, source="import", overwrite=True,
                only_complete=True):
    """Write monthly usage onto that payee's bills.

    A month is only written when there is a bill to attach it to - usage
    without a cost cannot say anything about a rate. Partial months at either
    end of an export are dropped by default, because half a month of readings
    against a whole month's bill would give a badly wrong unit cost.
    """
    payee.usage_unit = unit
    existing = {b.period: b for b in payee.payments}

    written = skipped_no_bill = skipped_partial = 0
    periods = sorted(totals)
    edges = {periods[0], periods[-1]} if only_complete and len(periods) > 1 else set()

    for period in periods:
        if period in edges:
            skipped_partial += 1
            continue
        bill = existing.get(period)
        if bill is None:
            skipped_no_bill += 1
            continue
        if bill.usage is not None and not overwrite:
            continue
        bill.usage = round(totals[period], 3)
        bill.usage_unit = unit
        bill.usage_source = source
        written += 1

    db.session.commit()
    return {
        "written": written,
        "unit": unit,
        "months": len(totals),
        "skipped_no_bill": skipped_no_bill,
        "skipped_partial": skipped_partial,
        "first": periods[0] if periods else None,
        "last": periods[-1] if periods else None,
    }


# --------------------------------------------------------------------------
# Reading it back out
# --------------------------------------------------------------------------
def usage_history(payee, months=24):
    """Cost, usage and unit cost per month, newest last."""
    bills = sorted(payee.payments, key=lambda b: b.period)[-months:]
    return [
        {
            "period": b.period,
            "amount": b.amount,
            "usage": b.usage,
            "unit": b.usage_unit or payee.usage_unit,
            "unit_cost": b.unit_cost,
            "per_day": b.usage_per_day,
        }
        for b in bills
    ]


def compare_periods(payee, period, other):
    """Split the change between two months into rate and volume.

    A bill going up $50 means something different depending on which of the two
    moved, so saying which is the whole point.
    """
    by_period = {b.period: b for b in payee.payments}
    now, before = by_period.get(period), by_period.get(other)
    if not now or not before:
        return None
    if not (now.usage and before.usage and now.amount and before.amount):
        return None

    rate_now, rate_before = now.unit_cost, before.unit_cost
    # Volume effect priced at the old rate; rate effect on the new volume.
    volume_effect = (now.usage - before.usage) * rate_before
    rate_effect = (rate_now - rate_before) * now.usage

    return {
        "period": period,
        "other": other,
        "amount_change": now.amount - before.amount,
        "usage_change": now.usage - before.usage,
        "rate_change": rate_now - rate_before,
        "rate_effect": rate_effect,
        "volume_effect": volume_effect,
        "unit": now.usage_unit or payee.usage_unit,
    }


def payees_with_usage():
    return (
        Payee.query.filter(Payee.usage_unit.isnot(None))
        .order_by(Payee.name)
        .all()
    )
