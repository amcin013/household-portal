"""The blocks the home page is built from.

Every panel on the home page is a module that can be switched off and moved
around, because what belongs on a household's front page is not the same from
one household to the next - and it changes. Somebody mid-remodel wants project
costs and storage; somebody else wants recipes and the trash day.

Adding a module means adding an entry here and a partial in
templates/dashboard/. Nothing else needs to know about it.
"""

MODULES = {
    "glance": {
        "label": "At a glance",
        "icon": "▣",
        "blurb": "A row of tiles across the top: bills left, disk free, sensors, recipes.",
        "default": True,
        "wide": True,
    },
    "machine": {
        "label": "Server status",
        "icon": "🖥️",
        "blurb": "Memory, uptime, load and every filesystem - the whole box at a glance.",
        "default": True,
        "wide": True,
    },
    "weather": {
        "label": "Weather",
        "icon": "🌤️",
        "blurb": "Current conditions and the forecast at each property.",
        "default": True,
        "wide": True,
    },
    "radar": {
        "label": "Radar",
        "icon": "🌧️",
        "blurb": "The NOAA radar loop for each property that has one switched on.",
        "default": False,
        "wide": True,
    },
    "alerts": {
        "label": "Weather alerts",
        "icon": "⚠️",
        "blurb": "Watches and warnings, across the top. Only appears when there are any.",
        "default": True,
        "wide": True,
    },
    "bills": {
        "label": "Bills due",
        "icon": "💵",
        "blurb": "This month's total, what is left to pay, and what falls due soon.",
        "default": True,
    },
    "obligations": {
        "label": "Obligations",
        "icon": "🧾",
        "blurb": "Balances being paid down, and any cheque not yet cleared.",
        "default": True,
    },
    "accounts": {
        "label": "Accounts",
        "icon": "🏦",
        "blurb": "Balances and net worth at a glance.",
        "default": False,
    },
    "links": {
        "label": "Quick links",
        "icon": "🔗",
        "blurb": "The links you pinned.",
        "default": True,
    },
    "essentials": {
        "label": "Essentials",
        "icon": "🧭",
        "blurb": "The pages someone would need to keep the house running.",
        "default": True,
    },
    "recipes": {
        "label": "Kitchen",
        "icon": "🍳",
        "blurb": "Favourites and whatever was cooked recently.",
        "default": True,
    },
    "pages": {
        "label": "Pinned how-tos",
        "icon": "📄",
        "blurb": "Pages you pinned.",
        "default": True,
    },
    "storage": {
        "label": "Storage",
        "icon": "💾",
        "blurb": "How full the drives are, and anything in trouble.",
        "default": False,
    },
    "activity": {
        "label": "Recently updated",
        "icon": "🕒",
        "blurb": "What changed lately, and who changed it.",
        "default": True,
    },
}

# The order they appear in when nobody has said otherwise. Roughly: things that
# need attention, then things you look at, then things you browse.
DEFAULT_ORDER = [
    "alerts", "glance", "weather", "bills", "obligations", "links",
    "essentials", "recipes", "machine", "pages", "activity",
]

def default_layout():
    return [k for k in DEFAULT_ORDER if k in MODULES]


def layout_for(user):
    """The ordered widget keys this person's home page should render.

    Nobody has a stored layout until they change something, so an untouched
    account falls back to the defaults rather than to an empty page. Unknown
    keys are dropped, which keeps a stored layout working after a widget is
    renamed or removed.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return default_layout()

    rows = [w for w in getattr(user, "widgets", []) if w.enabled]
    if not rows and not getattr(user, "widgets", []):
        return default_layout()

    return [w.widget_key for w in sorted(rows, key=lambda w: w.position)
            if w.widget_key in MODULES]


def choices_for(user):
    """Every widget with its state for this person, ordered as they see it."""
    stored = {w.widget_key: w for w in getattr(user, "widgets", [])} if user else {}

    if stored:
        order = [w.widget_key for w in sorted(stored.values(), key=lambda w: w.position)]
    else:
        order = default_layout()

    seen, rows = set(), []
    for key in order:
        if key in MODULES and key not in seen:
            seen.add(key)
            widget = stored.get(key)
            rows.append({
                "key": key,
                "on": widget.enabled if widget else True,
                **MODULES[key],
            })
    for key, spec in MODULES.items():
        if key not in seen:
            rows.append({"key": key, "on": False, **spec})
    return rows


def save_layout(user, enabled, order):
    """Persist one person's layout. Every widget gets a row, on or off, so the
    order of the switched-off ones survives being switched back on."""
    from .extensions import db
    from .models import DashboardWidget

    enabled = {k for k in enabled if k in MODULES}
    ordered = [k for k in order if k in MODULES]
    ordered += [k for k in MODULES if k not in ordered]

    existing = {w.widget_key: w for w in user.widgets}
    for position, key in enumerate(ordered):
        widget = existing.get(key)
        if widget is None:
            widget = DashboardWidget(user_id=user.id, widget_key=key)
            db.session.add(widget)
        widget.position = position
        widget.enabled = key in enabled

    # Drop rows for widgets that no longer exist in the catalog.
    for key, widget in existing.items():
        if key not in MODULES:
            db.session.delete(widget)

    db.session.commit()
