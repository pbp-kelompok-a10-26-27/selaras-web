"""Saran aktivitas dari cuaca saat ini (Open-Meteo)."""

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

# Lokasi bawaan: Jakarta
DEFAULT_LATITUDE = -6.2088
DEFAULT_LONGITUDE = 106.8456


def _interpret_weather_code(code: int, temp: float) -> dict:
    """Ubah kode cuaca WMO jadi teks dan ikon."""
    if code == 0:
        condition = "Cerah"
        icon = "sun"
        is_outdoor = True
        suggestion = (
            "Langit cerah! Pas banget untuk challenge di luar ruangan "
            "seperti bersepeda atau jalan kaki."
        )
    elif code in (1, 2, 3):
        condition = "Cerah berawan"
        icon = "cloud-sun"
        is_outdoor = True
        suggestion = "Adem dan nyaman. Cocok untuk aktivitas hijau di luar."
    elif code in (45, 48):
        condition = "Berkabut"
        icon = "cloud"
        is_outdoor = True
        suggestion = (
            "Hari yang teduh. Waktu yang pas untuk menuntaskan challenge harianmu."
        )
    elif code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        condition = "Hujan"
        icon = "cloud-rain"
        is_outdoor = False
        suggestion = (
            "Lagi hujan. Saatnya aksi di dalam rumah, seperti memilah "
            "sampah dapur atau hemat listrik."
        )
    elif code in (95, 96, 99):
        condition = "Badai petir"
        icon = "cloud-lightning"
        is_outdoor = False
        suggestion = (
            "Cuaca lagi kurang bersahabat. Tetap di dalam dan fokus hemat energi, ya."
        )
    else:
        condition = "Berawan"
        icon = "cloud"
        is_outdoor = True
        suggestion = "Hari yang baik untuk berbuat sesuatu bagi bumi."

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
    location_label = "Jakarta (bawaan)"

    if lat is not None and lon is not None:
        try:
            parsed_lat = float(lat)
            parsed_lon = float(lon)
            if -90.0 <= parsed_lat <= 90.0 and -180.0 <= parsed_lon <= 180.0:
                target_lat = round(parsed_lat, 4)
                target_lon = round(parsed_lon, 4)
                is_custom_location = True
                location_label = "Lokasimu"
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

    # Cadangan saat API gagal, supaya halaman tetap tampil
    return {
        "temperature": 28,
        "condition": "Cerah berawan",
        "icon": "cloud-sun",
        "is_outdoor_friendly": True,
        "suggestion": (
            "Cuaca hari ini cocok untuk aktivitas hijau. "
            "Pilih challenge dan mulai sekarang."
        ),
        "location_label": location_label,
        "is_custom_location": is_custom_location,
        "latitude": target_lat,
        "longitude": target_lon,
        "is_fallback": True,
    }
