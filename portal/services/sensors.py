"""Indoor readings - thermostats and temperature sensors.

Providers:
  manual        - somebody types the number in. Always available.
  homeassistant - reads an entity's state from a Home Assistant instance.
  http_json     - any URL returning JSON, plus a dotted path to the value.
                  Covers most DIY sensors and a lot of vendor APIs.
  ecobee        - stub. Ecobee needs a registered developer app and a refresh
                  token; see docs/integrations.md before turning it on.

A sensor that fails records the error against itself and leaves the last good
reading in place - one dead sensor never takes the dashboard down.
"""
import logging

import requests

from ..extensions import db
from ..models import Sensor, utcnow

log = logging.getLogger(__name__)
TIMEOUT = 10


class SensorError(Exception):
    pass


def dig(data, path):
    """dig({'a': {'b': [1,2]}}, 'a.b.0') -> 1"""
    current = data
    for part in str(path).split("."):
        if part == "":
            continue
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current


def read_homeassistant(config):
    """config: base_url, token, entity_id, [attribute]"""
    for field in ("base_url", "token", "entity_id"):
        if not config.get(field):
            raise SensorError(f"Home Assistant sensor needs '{field}'.")

    url = f"{config['base_url'].rstrip('/')}/api/states/{config['entity_id']}"
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {config['token']}"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()

    attribute = config.get("attribute")
    raw = data.get("attributes", {}).get(attribute) if attribute else data.get("state")
    if raw in (None, "unknown", "unavailable", ""):
        raise SensorError(f"Entity {config['entity_id']} reported '{raw}'.")
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise SensorError(f"Entity {config['entity_id']} returned non-numeric '{raw}'.")


def read_http_json(config):
    """config: url, path, [headers], [token]"""
    if not config.get("url"):
        raise SensorError("HTTP sensor needs a 'url'.")
    headers = dict(config.get("headers") or {})
    if config.get("token"):
        headers.setdefault("Authorization", f"Bearer {config['token']}")

    r = requests.get(config["url"], headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    try:
        value = dig(data, config.get("path", "")) if config.get("path") else data
        return float(value)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise SensorError(f"Could not read '{config.get('path')}' from the response: {exc}")


def read_ecobee(config):
    raise SensorError(
        "Ecobee is not wired up yet - it needs a developer app and a refresh "
        "token. See docs/integrations.md. Until then, point this sensor at "
        "Home Assistant if it already has the thermostat, or set it to manual."
    )


READERS = {
    "homeassistant": read_homeassistant,
    "http_json": read_http_json,
    "ecobee": read_ecobee,
}

PROVIDER_LABELS = {
    "manual": "Typed in by hand",
    "homeassistant": "Home Assistant",
    "http_json": "Any JSON URL",
    "ecobee": "Ecobee (not yet available)",
}


def refresh_sensor(sensor, commit=True):
    """Pull one sensor. Returns True if it got a fresh number."""
    if sensor.provider == "manual":
        return False

    reader = READERS.get(sensor.provider)
    if reader is None:
        sensor.last_error = f"Unknown provider '{sensor.provider}'."
        if commit:
            db.session.commit()
        return False

    try:
        value = reader(sensor.config)
    except Exception as exc:
        log.warning("Sensor %s failed: %s", sensor.name, exc)
        sensor.last_error = str(exc)[:300]
        if commit:
            db.session.commit()
        return False

    sensor.last_value = value
    sensor.last_reading_at = utcnow()
    sensor.last_error = None
    if commit:
        db.session.commit()
    return True


def refresh_place(place):
    results = {"ok": 0, "failed": 0}
    for sensor in place.sensors:
        if sensor.provider == "manual":
            continue
        if refresh_sensor(sensor, commit=False):
            results["ok"] += 1
        else:
            results["failed"] += 1
    db.session.commit()
    return results


def refresh_all():
    results = {"ok": 0, "failed": 0}
    for sensor in Sensor.query.filter(Sensor.provider != "manual").all():
        if refresh_sensor(sensor, commit=False):
            results["ok"] += 1
        else:
            results["failed"] += 1
    db.session.commit()
    return results
