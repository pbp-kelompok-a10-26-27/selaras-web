"""Open-Meteo Integration for Challenges Module.

Conforms to PRD Section 9 and Section 29 (External Weather Integration).
"""

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

# Default location: Jakarta / Jabodetabek coordinates
DEFAULT_LATITUDE = -6.2088
DEFAULT_LONGITUDE = 106.8456


def _interpret_weather_code(code: int, temp: float) -> dict:
    """Interpret WMO weather codes into English text and icons."""
    if code == 0:
        condition = "Clear"
        icon = "sun"
        is_outdoor = True
        suggestion = (
            "Clear skies today. A great time for outdoor challenges "
            "like cycling or walking."
        )
    elif code in (1, 2, 3):
        condition = "Partly cloudy"
        icon = "cloud-sun"
        is_outdoor = True
        suggestion = "Mild and pleasant. Perfect for eco-friendly activities outdoors."
    elif code in (45, 48):
        condition = "Foggy or overcast"
        icon = "cloud"
        is_outdoor = True
        suggestion = "A calm, shaded day. Good for finishing your daily challenge goal."
    elif code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        condition = "Rain"
        icon = "cloud-rain"
        is_outdoor = False
        suggestion = (
            "It is raining. A good time for indoor actions like sorting "
            "kitchen waste or saving electricity."
        )
    elif code in (95, 96, 99):
        condition = "Thunderstorm"
        icon = "cloud-lightning"
        is_outdoor = False
        suggestion = "Rough weather. Stay safe indoors and focus on saving energy."
    else:
        condition = "Cloudy"
        icon = "cloud"
        is_outdoor = True
        suggestion = "A good day to do something for the planet."

    return {
        "temperature": round(temp),
        "condition": condition,
        "icon": icon,
        "is_outdoor_friendly": is_outdoor,
        "suggestion": suggestion,
        "is_fallback": False,
    }


def get_current_weather_suggestion(lat=None, lon=None) -> dict:
    """Fetch current weather from Open-Meteo API for coordinates or default to Jakarta.

    Fails gracefully to a safe default if network/API is unreachable.
    """
    target_lat = DEFAULT_LATITUDE
    target_lon = DEFAULT_LONGITUDE
    is_custom_location = False
    location_label = "Greater Jakarta (default)"

    if lat is not None and lon is not None:
        try:
            parsed_lat = float(lat)
            parsed_lon = float(lon)
            if -90.0 <= parsed_lat <= 90.0 and -180.0 <= parsed_lon <= 180.0:
                target_lat = round(parsed_lat, 4)
                target_lon = round(parsed_lon, 4)
                is_custom_location = True
                location_label = "Your location"
            else:
                logger.warning("Coordinates out of range: lat=%s, lon=%s", lat, lon)
        except (ValueError, TypeError):
            logger.warning("Invalid lat/lon values received: lat=%s, lon=%s", lat, lon)

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={target_lat}&longitude={target_lon}"
        "&current=temperature_2m,weather_code&timezone=auto"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Selaras-Challenges/1.0"},
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                current = payload.get("current", {})
                temp = current.get("temperature_2m", 28.0)
                code = current.get("weather_code", 1)
                data = _interpret_weather_code(code, temp)
                data.update(
                    {
                        "location_label": location_label,
                        "is_custom_location": is_custom_location,
                        "latitude": target_lat,
                        "longitude": target_lon,
                    }
                )
                return data
    except Exception as exc:
        logger.warning(
            "Failed to fetch weather from Open-Meteo: %s. Using fallback.", exc
        )

    # Graceful fallback (will never crash the page)
    return {
        "temperature": 28,
        "condition": "Partly cloudy",
        "icon": "cloud-sun",
        "is_outdoor_friendly": True,
        "suggestion": (
            "Today's weather suits eco-friendly activities. "
            "Pick a challenge and get started."
        ),
        "location_label": location_label,
        "is_custom_location": is_custom_location,
        "latitude": target_lat,
        "longitude": target_lon,
        "is_fallback": True,
    }
