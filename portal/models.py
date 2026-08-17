"""Database models for the household portal."""
import json
import re
import unicodedata
from datetime import date, datetime, timezone

from flask_login import UserMixin
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


def slugify(text, fallback="item"):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text or fallback


def unique_slug(model, text, fallback="item", ignore_id=None):
    """Slugify, then add -2, -3 ... until it is free.

    Runs with autoflush off: this is normally called while the object being
    named is already pending in the session, and flushing it mid-query would
    try to INSERT a row whose slug is not set yet.
    """
    base = slugify(text, fallback)
    slug, n = base, 1
    with db.session.no_autoflush:
        while True:
            q = model.query.filter_by(slug=slug)
            if ignore_id is not None:
                q = q.filter(model.id != ignore_id)
            if not q.first():
                return slug
            n += 1
            slug = f"{base}-{n}"


class TagsMixin:
    """Tags stored as a comma-separated string; small scale, no join table needed."""

    @property
    def tag_list(self):
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    @tag_list.setter
    def tag_list(self, values):
        self.tags = ", ".join(sorted({v.strip() for v in values if v.strip()}))


# --------------------------------------------------------------------------
# People and settings
# --------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120))
    avatar_url = db.Column(db.String(500))
    role = db.Column(db.String(20), default="member", nullable=False)  # admin|member
    is_active_flag = db.Column("is_active", db.Boolean, default=True, nullable=False)
    theme = db.Column(db.String(40))  # personal override of the household theme
    font = db.Column(db.String(40))
    password_hash = db.Column(db.String(255))  # only used by local-password mode
    created_at = db.Column(db.DateTime, default=utcnow)
    last_seen_at = db.Column(db.DateTime)

    @property
    def is_active(self):  # Flask-Login uses this to block disabled accounts
        return bool(self.is_active_flag)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def display_name(self):
        return self.name or (self.email or "").split("@")[0]

    @property
    def initials(self):
        parts = [p for p in re.split(r"[\s._-]+", self.display_name) if p]
        return "".join(p[0].upper() for p in parts[:2]) or "?"

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return bool(self.password_hash) and check_password_hash(self.password_hash, raw)


class Setting(db.Model):
    """Simple key/value store for household-wide preferences."""

    __tablename__ = "settings"

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text)

    @staticmethod
    def get(key, default=None):
        row = db.session.get(Setting, key)
        return row.value if row and row.value is not None else default

    @staticmethod
    def set(key, value):
        row = db.session.get(Setting, key)
        if row is None:
            row = Setting(key=key)
            db.session.add(row)
        row.value = None if value is None else str(value)

    @staticmethod
    def all_as_dict():
        return {r.key: r.value for r in Setting.query.all()}


class DashboardWidget(db.Model):
    """One panel on one person's home page.

    Per person rather than shared: the home page is the first thing anyone sees
    and what belongs there differs by who you are. Whoever is mid-remodel wants
    project costs; whoever cooks wants the recipes. A row exists only once
    somebody has customised - until then the defaults in modules.py apply, so a
    new account gets a sensible page without any setup.
    """

    __tablename__ = "dashboard_widgets"
    __table_args__ = (
        db.UniqueConstraint("user_id", "widget_key", name="uq_user_widget"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    widget_key = db.Column(db.String(40), nullable=False)
    position = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=True)
    # Per-widget options, for when a widget grows them (which property a
    # weather panel shows, how many rows a list gives).
    config_json = db.Column(db.Text, default="{}")

    user = db.relationship("User", backref=db.backref(
        "widgets", cascade="all, delete-orphan", order_by="DashboardWidget.position"
    ))

    @property
    def config(self):
        try:
            return json.loads(self.config_json or "{}")
        except ValueError:
            return {}

    @config.setter
    def config(self, mapping):
        self.config_json = json.dumps(mapping or {})


# --------------------------------------------------------------------------
# Links
# --------------------------------------------------------------------------
class Link(db.Model):
    __tablename__ = "links"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    description = db.Column(db.String(500))
    category = db.Column(db.String(80), default="General", index=True)
    icon = db.Column(db.String(16))  # an emoji reads better than a sprite sheet
    pinned = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    open_new_tab = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    @property
    def host(self):
        m = re.match(r"https?://([^/]+)", self.url or "")
        return m.group(1) if m else ""


# --------------------------------------------------------------------------
# Recipes
# --------------------------------------------------------------------------
class Food(db.Model):
    """Nutrition reference, per 100 g. Optional - recipes work without it."""

    __tablename__ = "foods"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    kcal = db.Column(db.Float, default=0)
    protein_g = db.Column(db.Float, default=0)
    carbs_g = db.Column(db.Float, default=0)
    fat_g = db.Column(db.Float, default=0)
    fiber_g = db.Column(db.Float, default=0)
    sodium_mg = db.Column(db.Float, default=0)
    # {"cup": 240, "tbsp": 15, "each": 50} - grams for one of that unit
    unit_grams_json = db.Column(db.Text, default="{}")

    @property
    def unit_grams(self):
        try:
            return json.loads(self.unit_grams_json or "{}")
        except ValueError:
            return {}

    @unit_grams.setter
    def unit_grams(self, mapping):
        self.unit_grams_json = json.dumps(mapping or {})


class Recipe(TagsMixin, db.Model):
    __tablename__ = "recipes"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    servings = db.Column(db.Integer, default=4)
    serving_noun = db.Column(db.String(40), default="servings")
    prep_minutes = db.Column(db.Integer)
    cook_minutes = db.Column(db.Integer)
    instructions = db.Column(db.Text)  # markdown
    notes = db.Column(db.Text)
    source = db.Column(db.String(300))
    source_url = db.Column(db.String(1000))
    image_url = db.Column(db.String(1000))
    course = db.Column(db.String(60), index=True)  # dinner, dessert, ...
    tags = db.Column(db.String(400))
    favorite = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    created_by = db.relationship("User")
    ingredients = db.relationship(
        "RecipeIngredient",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.position",
    )

    @property
    def total_minutes(self):
        return (self.prep_minutes or 0) + (self.cook_minutes or 0)


class RecipeIngredient(db.Model):
    __tablename__ = "recipe_ingredients"

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(
        db.Integer, db.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    position = db.Column(db.Integer, default=0)
    quantity = db.Column(db.Float)  # null for "salt to taste"
    unit = db.Column(db.String(40))
    item = db.Column(db.String(200), nullable=False)
    note = db.Column(db.String(200))  # "finely chopped"
    heading = db.Column(db.Boolean, default=False)  # section header, e.g. "For the sauce"
    food_id = db.Column(db.Integer, db.ForeignKey("foods.id"))

    recipe = db.relationship("Recipe", back_populates="ingredients")
    food = db.relationship("Food")


# --------------------------------------------------------------------------
# Places (properties) and their readings
# --------------------------------------------------------------------------
class Place(db.Model):
    __tablename__ = "places"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)  # "Bayshore"
    address = db.Column(db.String(300))
    city = db.Column(db.String(120))
    state = db.Column(db.String(40))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    notes = db.Column(db.Text)  # markdown
    icon = db.Column(db.String(16), default="🏠")
    sort_order = db.Column(db.Integer, default=0)
    show_on_dashboard = db.Column(db.Boolean, default=True)
    # The NOAA radar loop for this spot. Off by default: it is a big animated
    # image, and on a wall tablet it is a lot of bandwidth for something you
    # only want when the weather is doing something.
    show_radar = db.Column(db.Boolean, default=False)

    facts = db.relationship(
        "PlaceFact",
        back_populates="place",
        cascade="all, delete-orphan",
        order_by="PlaceFact.sort_order",
    )
    sensors = db.relationship(
        "Sensor", back_populates="place", cascade="all, delete-orphan"
    )

    @property
    def label(self):
        bits = [b for b in (self.city, self.state) if b]
        return f"{self.name} — {', '.join(bits)}" if bits else self.name

    @property
    def has_coords(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def radar_station(self):
        """Which NEXRAD site covers this spot.

        NOAA hands it back with the forecast, so it arrives with the first
        weather fetch rather than needing to be looked up or configured. One
        extra query per place, and there are two of them.
        """
        cache = WeatherCache.query.filter_by(place_id=self.id).first()
        return (cache.payload or {}).get("radar_station") if cache else None


class PlaceFact(db.Model):
    """Anything worth writing down about a property: wifi, trash day, codes."""

    __tablename__ = "place_facts"

    id = db.Column(db.Integer, primary_key=True)
    place_id = db.Column(
        db.Integer, db.ForeignKey("places.id", ondelete="CASCADE"), nullable=False
    )
    label = db.Column(db.String(120), nullable=False)
    value = db.Column(db.Text)
    category = db.Column(db.String(60), default="General")
    # Hidden behind a click so shoulder-surfing a wall-mounted tablet is harder.
    sensitive = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)

    place = db.relationship("Place", back_populates="facts")


class Sensor(db.Model):
    """Indoor readings. Filled by an integration, or typed in by hand."""

    __tablename__ = "sensors"

    id = db.Column(db.Integer, primary_key=True)
    place_id = db.Column(
        db.Integer, db.ForeignKey("places.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(120), nullable=False)  # "Living room"
    kind = db.Column(db.String(40), default="temperature")  # temperature|humidity|other
    provider = db.Column(db.String(40), default="manual")  # manual|homeassistant|ecobee
    config_json = db.Column(db.Text, default="{}")  # entity id, device id, etc.
    unit = db.Column(db.String(16), default="°F")
    last_value = db.Column(db.Float)
    last_reading_at = db.Column(db.DateTime)
    last_error = db.Column(db.String(300))
    sort_order = db.Column(db.Integer, default=0)

    place = db.relationship("Place", back_populates="sensors")

    @property
    def config(self):
        try:
            return json.loads(self.config_json or "{}")
        except ValueError:
            return {}

    @config.setter
    def config(self, mapping):
        self.config_json = json.dumps(mapping or {})

    @property
    def is_stale(self):
        if not self.last_reading_at:
            return True
        age = utcnow() - self.last_reading_at.replace(tzinfo=timezone.utc)
        return age.total_seconds() > 3 * 3600


class WeatherCache(db.Model):
    """NWS responses cached so a dashboard refresh does not hammer weather.gov."""

    __tablename__ = "weather_cache"

    id = db.Column(db.Integer, primary_key=True)
    place_id = db.Column(
        db.Integer, db.ForeignKey("places.id", ondelete="CASCADE"), unique=True
    )
    payload_json = db.Column(db.Text)
    fetched_at = db.Column(db.DateTime, default=utcnow)
    error = db.Column(db.String(400))

    @property
    def payload(self):
        try:
            return json.loads(self.payload_json or "{}")
        except ValueError:
            return {}

    @payload.setter
    def payload(self, data):
        self.payload_json = json.dumps(data or {})


# --------------------------------------------------------------------------
# Money: who we pay, what we hold, what is coming
# --------------------------------------------------------------------------
class Payee(db.Model):
    """A company we pay - TXU, Pflugerville Water, the mortgage."""

    __tablename__ = "payees"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), default="Utilities", index=True)
    place_id = db.Column(db.Integer, db.ForeignKey("places.id"))  # which property
    typical_amount = db.Column(db.Float, default=0)
    due_day = db.Column(db.Integer, default=1)  # day of month
    pay_url = db.Column(db.String(1000))
    login_url = db.Column(db.String(1000))
    phone = db.Column(db.String(40))
    account_hint = db.Column(db.String(120))  # "ends 4417" - never a full number
    autopay = db.Column(db.Boolean, default=False)
    variable_amount = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)
    # What this utility is metered in, if it is metered at all. Recording the
    # units alongside the dollars is the only way to tell a rate rise apart
    # from actually using more.
    usage_unit = db.Column(db.String(16))  # kWh | ccf | therm | gal | kgal
    meter_number = db.Column(db.String(60))

    place = db.relationship("Place")
    payments = db.relationship(
        "BillPayment", back_populates="payee", cascade="all, delete-orphan"
    )

    def payment_for(self, period):
        return next((p for p in self.payments if p.period == period), None)


class BillPayment(db.Model):
    """One month's bill for one payee. period is 'YYYY-MM'."""

    __tablename__ = "bill_payments"
    __table_args__ = (db.UniqueConstraint("payee_id", "period", name="uq_payee_period"),)

    id = db.Column(db.Integer, primary_key=True)
    payee_id = db.Column(
        db.Integer, db.ForeignKey("payees.id", ondelete="CASCADE"), nullable=False
    )
    period = db.Column(db.String(7), nullable=False, index=True)
    amount = db.Column(db.Float)
    due_date = db.Column(db.Date)
    paid_on = db.Column(db.Date)
    status = db.Column(db.String(20), default="due")  # due|paid|skipped
    note = db.Column(db.String(300))
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    # How much was actually consumed, and over how many days. The day count
    # matters more than people expect: a 33-day bill against a 28-day one is
    # 18% more before anything real has happened.
    usage = db.Column(db.Float)
    usage_unit = db.Column(db.String(16))
    service_days = db.Column(db.Integer)
    usage_source = db.Column(db.String(20))  # manual | smt | greenbutton | csv

    payee = db.relationship("Payee", back_populates="payments")

    @property
    def is_paid(self):
        return self.status == "paid"

    @property
    def unit_cost(self):
        """Dollars per kWh / ccf / gallon - the actual rate paid."""
        if not self.usage or self.amount is None:
            return None
        return self.amount / self.usage

    @property
    def usage_per_day(self):
        if not self.usage or not self.service_days:
            return None
        return self.usage / self.service_days

    @property
    def cost_per_day(self):
        if self.amount is None or not self.service_days:
            return None
        return self.amount / self.service_days


class Account(db.Model):
    """Something with a balance: savings, TSP, a card, the mortgage."""

    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(40), default="savings")  # savings|retirement|checking|debt
    institution = db.Column(db.String(160))
    url = db.Column(db.String(1000))
    account_hint = db.Column(db.String(120))
    monthly_contribution = db.Column(db.Float, default=0)
    annual_growth_pct = db.Column(db.Float, default=0)  # for the forecast
    include_in_net_worth = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)

    snapshots = db.relationship(
        "AccountSnapshot",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="AccountSnapshot.as_of.desc()",
    )

    @property
    def is_debt(self):
        return self.kind == "debt"

    @property
    def latest(self):
        return self.snapshots[0] if self.snapshots else None

    @property
    def balance(self):
        latest = self.latest
        return latest.balance if latest else 0.0

    @property
    def signed_balance(self):
        return -self.balance if self.is_debt else self.balance

    @property
    def as_of(self):
        latest = self.latest
        return latest.as_of if latest else None

    def change_over(self, n=1):
        """Difference between the latest snapshot and the one n back."""
        if len(self.snapshots) <= n:
            return None
        return self.balance - self.snapshots[n].balance


class AccountSnapshot(db.Model):
    __tablename__ = "account_snapshots"
    __table_args__ = (
        db.UniqueConstraint("account_id", "as_of", name="uq_account_asof"),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    as_of = db.Column(db.Date, nullable=False, default=date.today)
    balance = db.Column(db.Float, default=0)
    note = db.Column(db.String(200))

    account = db.relationship("Account", back_populates="snapshots")


class LedgerItem(db.Model):
    """Recurring money in or out that is not a company bill: pay, child support,
    a TSP contribution, the gym."""

    __tablename__ = "ledger_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(20), default="expense")  # income|expense|transfer
    amount = db.Column(db.Float, default=0)
    day_of_month = db.Column(db.Integer, default=1)
    frequency = db.Column(db.String(20), default="monthly")  # monthly|biweekly|annual
    category = db.Column(db.String(80), default="Other")
    to_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)

    to_account = db.relationship("Account")

    @property
    def monthly_amount(self):
        """Normalised to a month so the forecast can add things up."""
        if self.frequency == "biweekly":
            return (self.amount or 0) * 26 / 12
        if self.frequency == "annual":
            return (self.amount or 0) / 12
        return self.amount or 0


# --------------------------------------------------------------------------
# Obligations: a balance being paid down to zero
# --------------------------------------------------------------------------
class Obligation(db.Model):
    """Something owed that gets paid off, rather than billed forever.

    Child support, a share of the kids' medical bills, a judgement. Unlike a
    Payee (a company billed every month) or an Account (a balance you snapshot),
    the point of an obligation is the remaining balance and when it reaches
    zero - worked out from the payments actually recorded, not extrapolated.

    The balance can go up as well as down: a new medical bill arrives and gets
    added as a charge.
    """

    __tablename__ = "obligations"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)          # "Kids medical - Nancy"
    owed_to = db.Column(db.String(160))
    kind = db.Column(db.String(40), default="other")          # medical|support|loan|other
    opening_balance = db.Column(db.Float, default=0)
    payment_amount = db.Column(db.Float, default=0)           # the usual cheque
    frequency = db.Column(db.String(20), default="monthly")   # monthly|biweekly|other
    pays_by = db.Column(db.String(20), default="check")       # check|transfer|withheld
    next_check_number = db.Column(db.String(20))
    account_hint = db.Column(db.String(120))
    active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)

    entries = db.relationship(
        "ObligationEntry",
        back_populates="obligation",
        cascade="all, delete-orphan",
        order_by="ObligationEntry.happened_on, ObligationEntry.id",
    )

    # --- money in and out -------------------------------------------------
    @property
    def charges(self):
        return [e for e in self.entries if e.is_charge]

    @property
    def payments(self):
        return [e for e in self.entries if not e.is_charge]

    @property
    def total_charged(self):
        return sum(e.amount or 0 for e in self.charges)

    @property
    def total_paid(self):
        """Only money that has actually gone out. A cheque still sitting on the
        desk has not paid anything down yet."""
        return sum(e.amount or 0 for e in self.payments if e.status in ("sent", "cleared"))

    @property
    def total_scheduled(self):
        return sum(e.amount or 0 for e in self.payments if e.status == "scheduled")

    @property
    def balance(self):
        return (self.opening_balance or 0) + self.total_charged - self.total_paid

    @property
    def projected_balance(self):
        """Where it lands once everything already written has gone through."""
        return self.balance - self.total_scheduled

    @property
    def is_settled(self):
        return abs(self.balance) < 0.01

    @property
    def progress(self):
        """0 to 1, for a bar. Against everything ever owed."""
        owed = (self.opening_balance or 0) + self.total_charged
        return min(self.total_paid / owed, 1.0) if owed else 0.0

    # --- what is left -----------------------------------------------------
    @property
    def payments_remaining(self):
        if not self.payment_amount:
            return None
        import math
        return max(0, math.ceil(self.balance / self.payment_amount))

    @property
    def uncleared(self):
        return [e for e in self.payments if e.status == "sent"]

    def payoff_date(self):
        """When the balance reaches zero at the current rate."""
        remaining = self.payments_remaining
        if not remaining:
            return None
        step = {"biweekly": 14, "monthly": 30}.get(self.frequency)
        if step is None:
            return None
        last = max((e.happened_on for e in self.payments if e.happened_on),
                   default=date.today())
        from datetime import timedelta
        return last + timedelta(days=step * remaining)


class ObligationEntry(db.Model):
    """One movement against an obligation - a payment out, or a new charge on.

    Payments carry a status because a cheque has a life: written, sent, then
    cleared the bank. Only sent and cleared count against the balance.
    """

    __tablename__ = "obligation_entries"

    id = db.Column(db.Integer, primary_key=True)
    obligation_id = db.Column(
        db.Integer, db.ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False
    )
    happened_on = db.Column(db.Date, default=date.today, index=True)
    amount = db.Column(db.Float, default=0)
    # A charge adds to what is owed; anything else pays it down.
    is_charge = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default="sent")  # scheduled|sent|cleared|void
    check_number = db.Column(db.String(20))
    cleared_on = db.Column(db.Date)
    note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=utcnow)

    obligation = db.relationship("Obligation", back_populates="entries")

    @property
    def label(self):
        if self.is_charge:
            return "Charge"
        return f"Check {self.check_number}" if self.check_number else "Payment"


# --------------------------------------------------------------------------
# Wiki-style pages
# --------------------------------------------------------------------------
class Page(TagsMixin, db.Model):
    __tablename__ = "pages"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500))
    body = db.Column(db.Text)  # markdown
    category = db.Column(db.String(80), default="How-to", index=True)
    tags = db.Column(db.String(400))
    icon = db.Column(db.String(16))
    pinned = db.Column(db.Boolean, default=False)
    # Shows in the "if something happens to me" section and prints cleanly.
    is_essential = db.Column(db.Boolean, default=False, index=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    updated_by = db.relationship("User")
    revisions = db.relationship(
        "PageRevision",
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="PageRevision.created_at.desc()",
    )


class PageRevision(db.Model):
    """Every save keeps the previous text, so nothing is ever lost."""

    __tablename__ = "page_revisions"

    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(
        db.Integer, db.ForeignKey("pages.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(200))
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    page = db.relationship("Page", back_populates="revisions")
    author = db.relationship("User")


def latest_updates(limit=8):
    """Recent activity across the portal, for the dashboard."""
    items = []
    for r in Recipe.query.order_by(Recipe.updated_at.desc()).limit(limit):
        items.append(("recipe", r.title, r.updated_at, "recipes.detail", {"slug": r.slug}))
    for p in Page.query.order_by(Page.updated_at.desc()).limit(limit):
        items.append(("page", p.title, p.updated_at, "docs.detail", {"slug": p.slug}))
    items.sort(key=lambda i: i[2] or datetime.min, reverse=True)
    return items[:limit]


def count_all():
    return {
        "recipes": db.session.query(func.count(Recipe.id)).scalar(),
        "links": db.session.query(func.count(Link.id)).scalar(),
        "pages": db.session.query(func.count(Page.id)).scalar(),
        "payees": db.session.query(func.count(Payee.id)).scalar(),
        "places": db.session.query(func.count(Place.id)).scalar(),
    }
