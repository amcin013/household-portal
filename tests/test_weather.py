"""The NOAA client, against recorded responses.

No network here on purpose: these must pass on a machine with no internet, and
the point is the parsing and the failure handling, not weather.gov's uptime.
"""
from unittest.mock import patch

import pytest
import requests

from portal.extensions import db
from portal.models import Place, WeatherCache
from portal.services.weather import (
    c_to_f, get_weather, icon_for, kmh_to_mph, worst_alert,
)

POINTS = {
    "properties": {
        "cwa": "HGX", "gridId": "HGX", "gridX": 12, "gridY": 34,
        "timeZone": "America/Chicago", "radarStation": "KHGX",
        "forecast": "https://api.weather.gov/gridpoints/HGX/12,34/forecast",
        "observationStations": "https://api.weather.gov/gridpoints/HGX/12,34/stations",
        "relativeLocation": {"properties": {"city": "Palacios", "state": "TX"}},
    }
}
FORECAST = {
    "properties": {
        "periods": [
            {"name": "Today", "isDaytime": True, "temperature": 88,
             "temperatureUnit": "F", "windSpeed": "10 mph", "windDirection": "SE",
             "shortForecast": "Sunny", "detailedForecast": "Sunny and hot.",
             "probabilityOfPrecipitation": {"value": 10}},
            {"name": "Tonight", "isDaytime": False, "temperature": 74,
             "temperatureUnit": "F", "windSpeed": "5 mph", "windDirection": "S",
             "shortForecast": "Partly Cloudy", "detailedForecast": "Mild.",
             "probabilityOfPrecipitation": {"value": None}},
        ]
    }
}
STATIONS = {
    "features": [
        {"properties": {"stationIdentifier": "KPSX", "name": "Palacios Municipal"}}
    ]
}
OBSERVATION = {
    "properties": {
        "temperature": {"value": 31.1},
        "relativeHumidity": {"value": 78.4},
        "dewpoint": {"value": 26.0},
        "heatIndex": {"value": 38.3},
        "windSpeed": {"value": 16.2},
        "windDirection": {"value": 140},
        "textDescription": "Mostly Cloudy",
        "timestamp": "2026-07-30T15:53:00+00:00",
    }
}
ALERTS = {
    "features": [
        {"properties": {"event": "Heat Advisory", "severity": "Moderate",
                        "urgency": "Expected", "headline": "Heat Advisory today",
                        "description": "Hot.", "ends": None}},
        {"properties": {"event": "Hurricane Warning", "severity": "Extreme",
                        "urgency": "Immediate", "headline": "Hurricane Warning",
                        "description": "Take shelter.", "ends": None}},
    ]
}


def fake_get(url, params=None):
    if "/points/" in url:
        return POINTS
    if url.endswith("/forecast"):
        return FORECAST
    if url.endswith("/stations"):
        return STATIONS
    if "observations/latest" in url:
        return OBSERVATION
    if "/alerts/active" in url:
        return ALERTS
    raise AssertionError(f"unexpected URL {url}")


@pytest.fixture
def place(app):
    place = Place(name="Bayshore", slug="bayshore", city="Palacios", state="TX",
                  latitude=28.7086, longitude=-96.2169)
    db.session.add(place)
    db.session.commit()
    return place


def test_temperature_conversion():
    assert c_to_f(0) == 32
    assert c_to_f(100) == 212
    assert c_to_f(None) is None
    assert kmh_to_mph(100) == pytest.approx(62.1371)


def test_parses_current_conditions(place):
    with patch("portal.services.weather._get", side_effect=fake_get):
        data = get_weather(place)

    assert data["current"]["temp_f"] == 88  # 31.1C
    assert data["current"]["humidity"] == 78
    assert data["current"]["heat_index_f"] == 101
    assert data["current"]["wind_mph"] == 10
    assert data["current"]["station"] == "KPSX"


def test_parses_forecast_periods(place):
    with patch("portal.services.weather._get", side_effect=fake_get):
        data = get_weather(place)

    assert len(data["periods"]) == 2
    assert data["periods"][0]["name"] == "Today"
    assert data["periods"][0]["temp"] == 88
    assert data["periods"][0]["icon"] == "☀️"


def test_parses_alerts(place):
    with patch("portal.services.weather._get", side_effect=fake_get):
        data = get_weather(place)
    assert len(data["alerts"]) == 2


def test_worst_alert_picks_most_severe(place):
    with patch("portal.services.weather._get", side_effect=fake_get):
        data = get_weather(place)
    assert worst_alert(data)["event"] == "Hurricane Warning"


def test_response_is_cached(place):
    with patch("portal.services.weather._get", side_effect=fake_get) as mock:
        get_weather(place)
        first_calls = mock.call_count
        get_weather(place)
        assert mock.call_count == first_calls  # second call served from cache


def test_force_bypasses_cache(place):
    with patch("portal.services.weather._get", side_effect=fake_get) as mock:
        get_weather(place)
        first = mock.call_count
        get_weather(place, force=True)
        assert mock.call_count > first


def test_falls_back_to_cache_when_api_is_down(place):
    with patch("portal.services.weather._get", side_effect=fake_get):
        get_weather(place)

    with patch("portal.services.weather._get",
               side_effect=requests.ConnectionError("down")):
        data = get_weather(place, force=True)

    assert data["stale"] is True
    assert data["current"]["temp_f"] == 88  # last good reading survives
    assert "not answering" in data["error"]


def test_never_raises_when_api_is_down_and_nothing_cached(place):
    with patch("portal.services.weather._get",
               side_effect=requests.ConnectionError("down")):
        data = get_weather(place)

    assert data["stale"] is True
    assert "error" in data


def test_place_without_coordinates_is_handled(app):
    place = Place(name="Nowhere", slug="nowhere")
    db.session.add(place)
    db.session.commit()

    data = get_weather(place)
    assert "No coordinates" in data["error"]


def test_forecast_survives_a_missing_observation_station(place):
    """A dead station must not lose the forecast too."""
    def partial(url, params=None):
        if url.endswith("/stations"):
            raise requests.HTTPError("500")
        return fake_get(url, params)

    with patch("portal.services.weather._get", side_effect=partial):
        data = get_weather(place)

    assert "current" not in data
    assert len(data["periods"]) == 2


@pytest.mark.parametrize("text,icon", [
    ("Sunny", "☀️"),
    ("Mostly Cloudy", "☁️"),
    ("Partly Sunny", "⛅"),
    ("Chance Showers And Thunderstorms", "⛈️"),
    ("Hurricane Warning", "🌀"),
    ("Patchy Fog", "🌫️"),
    ("Light Snow", "🌨️"),
    ("Something unheard of", "🌡️"),
])
def test_icon_matching(text, icon):
    assert icon_for(text) == icon
