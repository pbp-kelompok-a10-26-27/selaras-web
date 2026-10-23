"""
Open-Meteo Integration for Challenges Module.
Conforms to PRD Section 9 and Section 29 (External Weather Integration).
"""

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

# Default location: Jakarta / Jabodetabek coordinates
DEFAULT_LATITUDE = -6.2088
DEFAULT_LONGITUDE = 106.8456
OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={DEFAULT_LATITUDE}&longitude={DEFAULT_LONGITUDE}"
    "&current=temperature_2m,weather_code&timezone=Asia%2FJakarta"
)


def _interpret_weather_code(code: int, temp: float) -> dict:
    """Interpret WMO Weather interpretation codes into user-friendly Indonesian text & icons."""
    if code == 0:
        condition = "Cerah"
        icon = "sun"
        is_outdoor = True
        suggestion = "Cuaca sangat cerah! Waktu sempurna untuk tantangan outdoor seperti bersepeda atau jalan kaki."
    elif code in (1, 2, 3):
        condition = "Cerah Berawan"
        icon = "cloud-sun"
        is_outdoor = True
        suggestion = "Cuaca bersahabat dan sejuk. Sangat cocok untuk aktivitas ramah lingkungan di luar ruangan!"
    elif code in (45, 48):
        condition = "Berkabut / Berawan Tebal"
        icon = "cloud"
        is_outdoor = True
        suggestion = "Udara teduh hari ini. Yuk selesaikan target tantangan harianmu."
    elif code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        condition = "Hujan Ringan / Hujan"
        icon = "cloud-rain"
        is_outdoor = False
        suggestion = "Sedang turun hujan. Waktu yang pas untuk aksi ramah lingkungan indoor seperti memilah sampah dapur atau hemat listrik."
    elif code in (95, 96, 99):
        condition = "Hujan Badai"
        icon = "cloud-lightning"
        is_outdoor = False
        suggestion = "Cuaca kurang bersahabat. Tetap aman di dalam ruangan dan lakukan aksi hemat energi!"
    else:
        condition = "Berawan"
        icon = "cloud"
        is_outdoor = True
        suggestion = "Hari yang baik untuk berkontribusi menjaga kelestarian bumi!"

    return {
        "temperature": round(temp),
        "condition": condition,
        "icon": icon,
        "is_outdoor_friendly": is_outdoor,
        "suggestion": suggestion,
        "is_fallback": False,
    }


def get_current_weather_suggestion() -> dict:
    """
    Fetch current weather from Open-Meteo API.
    Fails gracefully to a safe default if network/API is unreachable.
    """
    try:
        req = urllib.request.Request(
            OPEN_METEO_URL,
            headers={"User-Agent": "Selaras-Challenges/1.0"},
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                current = payload.get("current", {})
                temp = current.get("temperature_2m", 28.0)
                code = current.get("weather_code", 1)
                return _interpret_weather_code(code, temp)
    except Exception as exc:
        logger.warning(
            "Failed to fetch weather from Open-Meteo: %s. Using fallback.", exc
        )

    # Graceful fallback (will never crash the page)
    return {
        "temperature": 28,
        "condition": "Cerah Berawan",
        "icon": "cloud-sun",
        "is_outdoor_friendly": True,
        "suggestion": "Cuaca hari ini mendukung untuk aktivitas ramah lingkungan. Yuk ambil tantangan hari ini!",
        "is_fallback": True,
    }
