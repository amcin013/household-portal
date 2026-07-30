"""Properties: weather, indoor readings, and the facts worth writing down."""
from flask import (
    Blueprint, flash, jsonify, redirect, render_template, request, url_for,
)
from flask_login import login_required

from ..extensions import db
from ..models import Place, PlaceFact, Sensor, unique_slug, utcnow
from ..services import sensors as sensor_service
from ..services.weather import get_weather, worst_alert

bp = Blueprint("places", __name__, url_prefix="/places")


@bp.route("/")
@login_required
def index():
    places = Place.query.order_by(Place.sort_order, Place.name).all()
    return render_template("places/index.html", places=places)


@bp.route("/<slug>")
@login_required
def detail(slug):
    place = Place.query.filter_by(slug=slug).first_or_404()
    weather = get_weather(place) if place.has_coords else None

    facts = {}
    for fact in place.facts:
        facts.setdefault(fact.category or "General", []).append(fact)

    return render_template(
        "places/detail.html",
        place=place,
        weather=weather,
        alert=worst_alert(weather),
        facts=sorted(facts.items()),
    )


@bp.route("/api/weather")
@login_required
def api_weather():
    """The dashboard fetches this after paint, so weather.gov never blocks a
    page load."""
    places = Place.query.filter_by(show_on_dashboard=True).order_by(
        Place.sort_order, Place.name
    ).all()

    out = []
    for place in places:
        weather = get_weather(place) if place.has_coords else {"error": "No coordinates"}
        current = (weather or {}).get("current") or {}
        periods = (weather or {}).get("periods") or []
        today = periods[0] if periods else {}
        alert = worst_alert(weather)

        out.append(
            {
                "id": place.id,
                "slug": place.slug,
                "name": place.name,
                "icon": place.icon,
                "city": place.city,
                "state": place.state,
                "temp": current.get("temp_f"),
                "text": current.get("text") or today.get("short"),
                "weather_icon": current.get("icon") or today.get("icon") or "🌡️",
                "humidity": current.get("humidity"),
                "wind": current.get("wind_mph"),
                "heat_index": current.get("heat_index_f"),
                "forecast": today.get("detailed") or today.get("short"),
                "forecast_name": today.get("name"),
                "high_low": [
                    {"name": p.get("name"), "temp": p.get("temp"),
                     "icon": p.get("icon"), "short": p.get("short")}
                    for p in periods[:4]
                ],
                "alert": (
                    {"event": alert.get("event"), "severity": alert.get("severity")}
                    if alert else None
                ),
                "sensors": [
                    {
                        "name": s.name,
                        "value": s.last_value,
                        "unit": s.unit,
                        "stale": s.is_stale,
                        "error": s.last_error,
                    }
                    for s in sorted(place.sensors, key=lambda s: (s.sort_order, s.name))
                ],
                "stale": (weather or {}).get("stale", False),
                "error": (weather or {}).get("error"),
            }
        )
    return jsonify(out)


@bp.route("/<slug>/refresh", methods=["POST"])
@login_required
def refresh(slug):
    place = Place.query.filter_by(slug=slug).first_or_404()
    if place.has_coords:
        get_weather(place, force=True)
    result = sensor_service.refresh_place(place)
    if result["failed"]:
        flash(
            f"Weather updated. {result['ok']} sensors read, "
            f"{result['failed']} could not be reached.",
            "warning",
        )
    else:
        flash("Refreshed.", "success")
    return redirect(url_for("places.detail", slug=place.slug))


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        place = Place()
        db.session.add(place)
        _apply(place, request.form)
        db.session.commit()
        flash(f"Added {place.name}.", "success")
        return redirect(url_for("places.detail", slug=place.slug))
    return render_template("places/edit.html", place=None)


@bp.route("/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit(slug):
    place = Place.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        _apply(place, request.form)
        db.session.commit()
        flash("Saved.", "success")
        return redirect(url_for("places.detail", slug=place.slug))
    return render_template("places/edit.html", place=place)


@bp.route("/<slug>/delete", methods=["POST"])
@login_required
def delete(slug):
    place = Place.query.filter_by(slug=slug).first_or_404()
    name = place.name
    db.session.delete(place)
    db.session.commit()
    flash(f"Removed {name}.", "info")
    return redirect(url_for("places.index"))


# --- facts ----------------------------------------------------------------
@bp.route("/<slug>/facts", methods=["POST"])
@login_required
def add_fact(slug):
    place = Place.query.filter_by(slug=slug).first_or_404()
    label = (request.form.get("label") or "").strip()
    if not label:
        flash("A fact needs a label.", "error")
        return redirect(url_for("places.detail", slug=slug))

    db.session.add(
        PlaceFact(
            place_id=place.id,
            label=label,
            value=request.form.get("value"),
            category=(request.form.get("category") or "General").strip(),
            sensitive=request.form.get("sensitive") == "on",
            sort_order=len(place.facts),
        )
    )
    db.session.commit()
    flash(f"Added “{label}”.", "success")
    return redirect(url_for("places.detail", slug=slug))


@bp.route("/facts/<int:fact_id>/edit", methods=["POST"])
@login_required
def edit_fact(fact_id):
    fact = db.get_or_404(PlaceFact, fact_id)
    fact.label = (request.form.get("label") or fact.label).strip()
    fact.value = request.form.get("value")
    fact.category = (request.form.get("category") or "General").strip()
    fact.sensitive = request.form.get("sensitive") == "on"
    db.session.commit()
    flash("Saved.", "success")
    return redirect(url_for("places.detail", slug=fact.place.slug))


@bp.route("/facts/<int:fact_id>/delete", methods=["POST"])
@login_required
def delete_fact(fact_id):
    fact = db.get_or_404(PlaceFact, fact_id)
    slug = fact.place.slug
    db.session.delete(fact)
    db.session.commit()
    return redirect(url_for("places.detail", slug=slug))


# --- sensors --------------------------------------------------------------
@bp.route("/<slug>/sensors", methods=["POST"])
@login_required
def add_sensor(slug):
    place = Place.query.filter_by(slug=slug).first_or_404()
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("A sensor needs a name.", "error")
        return redirect(url_for("places.detail", slug=slug))

    sensor = Sensor(place_id=place.id, name=name, sort_order=len(place.sensors))
    _apply_sensor(sensor, request.form)
    db.session.add(sensor)
    db.session.commit()

    if sensor.provider != "manual":
        if sensor_service.refresh_sensor(sensor):
            flash(f"{sensor.name} is reading {sensor.last_value}{sensor.unit}.", "success")
        else:
            flash(f"Saved, but the first read failed: {sensor.last_error}", "warning")
    else:
        flash(f"Added {sensor.name}.", "success")
    return redirect(url_for("places.detail", slug=slug))


@bp.route("/sensors/<int:sensor_id>/edit", methods=["POST"])
@login_required
def edit_sensor(sensor_id):
    sensor = db.get_or_404(Sensor, sensor_id)
    sensor.name = (request.form.get("name") or sensor.name).strip()
    _apply_sensor(sensor, request.form)
    db.session.commit()
    flash("Saved.", "success")
    return redirect(url_for("places.detail", slug=sensor.place.slug))


@bp.route("/sensors/<int:sensor_id>/reading", methods=["POST"])
@login_required
def set_reading(sensor_id):
    """Manual sensors get their number typed in."""
    sensor = db.get_or_404(Sensor, sensor_id)
    try:
        sensor.last_value = float(request.form.get("value"))
        sensor.last_reading_at = utcnow()
        sensor.last_error = None
        db.session.commit()
    except (TypeError, ValueError):
        flash("That reading was not a number.", "error")
    return redirect(url_for("places.detail", slug=sensor.place.slug))


@bp.route("/sensors/<int:sensor_id>/delete", methods=["POST"])
@login_required
def delete_sensor(sensor_id):
    sensor = db.get_or_404(Sensor, sensor_id)
    slug = sensor.place.slug
    db.session.delete(sensor)
    db.session.commit()
    return redirect(url_for("places.detail", slug=slug))


def _apply_sensor(sensor, form):
    sensor.kind = form.get("kind") or "temperature"
    sensor.provider = form.get("provider") or "manual"
    sensor.unit = (form.get("unit") or "°F").strip()

    config = {}
    for field in ("base_url", "token", "entity_id", "attribute", "url", "path"):
        value = (form.get(field) or "").strip()
        if value:
            config[field] = value
    # Keep an existing token if the field was left blank on an edit.
    if not config.get("token") and sensor.config.get("token"):
        config["token"] = sensor.config["token"]
    sensor.config = config


def _apply(place, form):
    place.name = (form.get("name") or "Untitled").strip()
    place.slug = unique_slug(
        Place, form.get("slug") or place.name, "place", ignore_id=place.id
    )
    place.address = form.get("address")
    place.city = (form.get("city") or "").strip() or None
    place.state = (form.get("state") or "").strip() or None
    place.notes = form.get("notes")
    place.icon = (form.get("icon") or "🏠").strip()[:16] or "🏠"
    place.show_on_dashboard = form.get("show_on_dashboard") == "on"

    for field in ("latitude", "longitude"):
        raw = (form.get(field) or "").strip()
        try:
            setattr(place, field, float(raw) if raw else None)
        except ValueError:
            setattr(place, field, None)
    try:
        place.sort_order = int(form.get("sort_order") or 0)
    except ValueError:
        place.sort_order = 0
