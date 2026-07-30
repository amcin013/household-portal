"""NOAA / National Weather Service.

api.weather.gov is free and needs no key - it only asks for a contact string in
the User-Agent (set NWS_USER_AGENT in .env).

Three calls per place, all cached:
  /points/{lat},{lon}            -> which grid and stations cover this spot
  {forecast url}                 -> the multi-day forecast
  /stations/{id}/observations/latest -> what it is doing right now
plus /alerts/active for watches and warnings, which matters on the coast.

Everything degrades quietly: if weather.gov is unreachable the dashboard shows
the last good reading with a note, not an error page.
"""
import logging
from datetime import timezone

import requests
from flask import current_app

from ..extensions import db
from ..models import WeatherCache, utcnow

log = logging.getLogger(__name__)

API = "https://api.weather.gov"
TIMEOUT = 12


def _headers():
    return {
        "User-Agent": current_app.config.get("NWS_USER_AGENT", "household-portal"),
        "Accept": "application/geo+json",
    }


def _get(url, params=None):
    r = requests.get(url, headers=_headers(), params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def c_to_f(celsius):
    return None if celsius is None else celsius * 9 / 5 + 32


def kmh_to_mph(kmh):
    return None if kmh is None else kmh * 0.621371


def fetch_place_weather(place):
    """Live call to NWS. Returns a dict shaped for the templates."""
    points = _get(f"{API}/points/{place.latitude},{place.longitude}")
    props = points["properties"]

    out = {
        "grid": f"{props.get('gridId')}/{props.get('gridX')},{props.get('gridY')}",
        "forecast_office": props.get("cwa"),
        "radar_station": props.get("radarStation"),
        "timezone": props.get("timeZone"),
    }
    rel = (props.get("relativeLocation") or {}).get("properties") or {}
    if rel.get("city"):
        out["nws_city"] = f"{rel['city']}, {rel.get('state', '')}".strip(", ")

    # --- forecast ---------------------------------------------------------
    try:
        periods = _get(props["forecast"])["properties"]["periods"]
        out["periods"] = [
            {
                "name": p.get("name"),
                "is_daytime": p.get("isDaytime"),
                "temp": p.get("temperature"),
                "unit": p.get("temperatureUnit"),
                "wind": p.get("windSpeed"),
                "wind_dir": p.get("windDirection"),
                "short": p.get("shortForecast"),
                "detailed": p.get("detailedForecast"),
                "precip": ((p.get("probabilityOfPrecipitation") or {}).get("value")),
                "icon": icon_for(p.get("shortForecast", "")),
            }
            for p in periods[:8]
        ]
    except Exception as exc:  # forecast is nice-to-have, keep going
        log.warning("NWS forecast failed for %s: %s", place.name, exc)

    # --- current conditions ----------------------------------------------
    try:
        stations = _get(props["observationStations"])["features"]
        for station in stations[:3]:  # first station is sometimes offline
            sid = station["properties"]["stationIdentifier"]
            try:
                obs = _get(f"{API}/stations/{sid}/observations/latest")["properties"]
            except Exception:
                continue
            temp_c = (obs.get("temperature") or {}).get("value")
            if temp_c is None:
                continue
            out["current"] = {
                "station": sid,
                "station_name": station["properties"].get("name"),
                "temp_f": round(c_to_f(temp_c)),
                "humidity": _round((obs.get("relativeHumidity") or {}).get("value")),
                "dewpoint_f": _round(c_to_f((obs.get("dewpoint") or {}).get("value"))),
                "heat_index_f": _round(c_to_f((obs.get("heatIndex") or {}).get("value"))),
                "wind_mph": _round(kmh_to_mph((obs.get("windSpeed") or {}).get("value"))),
                "wind_dir": (obs.get("windDirection") or {}).get("value"),
                "text": obs.get("textDescription"),
                "observed_at": obs.get("timestamp"),
                "icon": icon_for(obs.get("textDescription") or ""),
            }
            break
    except Exception as exc:
        log.warning("NWS observations failed for %s: %s", place.name, exc)

    # --- active alerts ----------------------------------------------------
    try:
        alerts = _get(
            f"{API}/alerts/active", params={"point": f"{place.latitude},{place.longitude}"}
        )["features"]
        out["alerts"] = [
            {
                "event": a["properties"].get("event"),
                "severity": a["properties"].get("severity"),
                "urgency": a["properties"].get("urgency"),
                "headline": a["properties"].get("headline"),
                "description": a["properties"].get("description"),
                "ends": a["properties"].get("ends") or a["properties"].get("expires"),
            }
            for a in alerts
        ]
    except Exception as exc:
        log.warning("NWS alerts failed for %s: %s", place.name, exc)
        out["alerts"] = []

    return out


def _age_seconds(stamp):
    """SQLite hands back naive datetimes; treat those as UTC."""
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (utcnow() - stamp).total_seconds()


def _round(value, digits=0):
    if value is None:
        return None
    return round(value, digits) if digits else round(value)


def get_weather(place, force=False):
    """Cached weather for a place. Never raises."""
    if not place.has_coords:
        return {"error": "No coordinates set for this place.", "stale": True}

    cache = WeatherCache.query.filter_by(place_id=place.id).first()
    max_age = current_app.config.get("WEATHER_CACHE_MINUTES", 20) * 60

    if cache and not force and cache.fetched_at:
        if _age_seconds(cache.fetched_at) < max_age and cache.payload:
            data = dict(cache.payload)
            data["fetched_at"] = cache.fetched_at
            data["stale"] = False
            return data

    try:
        data = fetch_place_weather(place)
        if cache is None:
            cache = WeatherCache(place_id=place.id)
            db.session.add(cache)
        cache.payload = data
        cache.fetched_at = utcnow()
        cache.error = None
        db.session.commit()
        data["fetched_at"] = cache.fetched_at
        data["stale"] = False
        return data
    except Exception as exc:
        log.warning("Weather fetch failed for %s: %s", place.name, exc)
        if cache is not None:
            cache.error = str(exc)[:400]
            db.session.commit()
            if cache.payload:
                data = dict(cache.payload)
                data["fetched_at"] = cache.fetched_at
                data["stale"] = True
                data["error"] = "Showing the last reading - weather.gov is not answering."
                return data
        return {"error": "Could not reach weather.gov.", "stale": True}


ICONS = [
    (("tornado",), "🌪️"),
    (("hurricane", "tropical"), "🌀"),
    (("thunder", "t-storm"), "⛈️"),
    (("snow", "flurr", "blizzard"), "🌨️"),
    (("sleet", "freezing", "ice"), "🧊"),
    (("rain", "shower", "drizzle"), "🌧️"),
    (("fog", "haze", "mist"), "🌫️"),
    (("wind", "breezy", "blustery"), "💨"),
    (("mostly cloudy", "overcast"), "☁️"),
    (("partly cloudy", "partly sunny", "mostly sunny", "few clouds"), "⛅"),
    (("clear", "sunny", "fair"), "☀️"),
    (("hot",), "🥵"),
    (("cold", "frost", "freeze"), "🥶"),
]


def icon_for(text):
    low = (text or "").lower()
    for words, icon in ICONS:
        if any(w in low for w in words):
            return icon
    return "🌡️"


SEVERITY_RANK = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3, "Unknown": 4}


def worst_alert(weather):
    alerts = (weather or {}).get("alerts") or []
    if not alerts:
        return None
    return sorted(alerts, key=lambda a: SEVERITY_RANK.get(a.get("severity"), 9))[0]
