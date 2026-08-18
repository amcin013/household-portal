"""Template filters and small shared helpers."""
import re
from datetime import date, datetime, timezone
from fractions import Fraction

import bleach
import markdown as md_lib
from markupsafe import Markup

ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "p", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "img", "hr", "br", "span",
    "div", "table", "thead", "tbody", "tr", "th", "td", "dl", "dt", "dd", "del",
    "input",
}
ALLOWED_ATTRS = {
    "*": ["class", "id", "title"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height", "loading"],
    "input": ["type", "checked", "disabled"],
    "td": ["colspan", "rowspan", "align"],
    "th": ["colspan", "rowspan", "align"],
}


def render_markdown(text):
    """Markdown -> sanitised HTML. Content is household-authored but this keeps a
    pasted-in blob from doing anything surprising."""
    if not text:
        return Markup("")
    html = md_lib.markdown(
        text,
        extensions=["extra", "sane_lists", "nl2br", "toc", "admonition"],
        output_format="html",
    )
    clean = bleach.clean(
        html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True
    )
    clean = bleach.linkify(clean, callbacks=[_external_link])
    return Markup(clean)


def _external_link(attrs, new=False):
    href = attrs.get((None, "href"), "")
    if href.startswith("http"):
        attrs[(None, "target")] = "_blank"
        attrs[(None, "rel")] = "noopener noreferrer"
    return attrs


def strip_markdown(text, limit=180):
    if not text:
        return ""
    plain = re.sub(r"[#*_`>\[\]()!-]", " ", text)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:limit] + ("…" if len(plain) > limit else "")


# --- numbers --------------------------------------------------------------
NICE_FRACTIONS = {
    Fraction(1, 8): "⅛", Fraction(1, 6): "⅙", Fraction(1, 5): "⅕",
    Fraction(1, 4): "¼", Fraction(1, 3): "⅓", Fraction(3, 8): "⅜",
    Fraction(2, 5): "⅖", Fraction(1, 2): "½", Fraction(3, 5): "⅗",
    Fraction(5, 8): "⅝", Fraction(2, 3): "⅔", Fraction(3, 4): "¾",
    Fraction(4, 5): "⅘", Fraction(5, 6): "⅚", Fraction(7, 8): "⅞",
}


def pretty_quantity(value):
    """1.5 -> '1½', 0.25 -> '¼', 3.0 -> '3'. Cooks read fractions, not decimals."""
    if value is None:
        return ""
    if abs(value) < 1e-9:
        return "0"

    frac = Fraction(value).limit_denominator(8)
    # limit_denominator always returns *something*, and for a small quantity
    # that something can be wildly off - 0.07 becomes 1/8, nearly double. Only
    # use the fraction when it genuinely represents the number.
    if abs(float(frac) - value) > 0.02 * abs(value):
        return f"{round(value, 2):g}"

    whole, rest = divmod(frac, 1)
    if rest == 0:
        return str(int(whole))
    symbol = NICE_FRACTIONS.get(rest)
    if symbol is None:
        return f"{round(value, 2):g}"
    return f"{int(whole)}{symbol}" if whole else symbol


def money(value, blank_zero=False):
    if value is None or (blank_zero and not value):
        return ""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def money_short(value):
    """$1,234 with no cents - for tiles and totals."""
    if value is None:
        return ""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def minutes(value):
    if not value:
        return ""
    hours, mins = divmod(int(value), 60)
    if hours and mins:
        return f"{hours} hr {mins} min"
    if hours:
        return f"{hours} hr"
    return f"{mins} min"


# --- dates ----------------------------------------------------------------
def as_utc(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def humandate(value):
    if not value:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    today = date.today()
    delta = (value - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta == -1:
        return "yesterday"
    if 0 < delta < 7:
        return value.strftime("%A")
    if value.year == today.year:
        return value.strftime("%b %-d")
    return value.strftime("%b %-d, %Y")


def timeago(value):
    if not value:
        return ""
    value = as_utc(value)
    seconds = (datetime.now(timezone.utc) - value).total_seconds()
    if seconds < 90:
        return "just now"
    for limit, div, name in (
        (3600, 60, "minute"), (86400, 3600, "hour"), (604800, 86400, "day"),
        (2592000, 604800, "week"),
    ):
        if seconds < limit:
            n = int(seconds // div)
            return f"{n} {name}{'s' if n != 1 else ''} ago"
    return value.strftime("%b %-d, %Y")


def month_label(period):
    """'2026-07' -> 'July 2026'."""
    try:
        return datetime.strptime(period, "%Y-%m").strftime("%B %Y")
    except (ValueError, TypeError):
        return period or ""


def shift_period(period, months):
    year, month = (int(p) for p in period.split("-"))
    total = year * 12 + (month - 1) + months
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def current_period():
    return date.today().strftime("%Y-%m")


def bytes_h(value):
    """Bytes as a human size. Mirrors services.disks.human_bytes so a figure
    read from /proc is formatted the same as one read from the disk report."""
    if not value:
        return "0 B"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if size < 1024 or unit == "PB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def register_filters(app):
    app.jinja_env.filters.update(
        markdown=render_markdown,
        plain=strip_markdown,
        qty=pretty_quantity,
        money=money,
        money_short=money_short,
        minutes=minutes,
        humandate=humandate,
        timeago=timeago,
        month_label=month_label,
        bytes_h=bytes_h,
    )
