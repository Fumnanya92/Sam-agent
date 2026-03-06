"""
Aircraft radar using the OpenSky Network REST API (no key required).
Reports live flights over a given city/country by bounding box.
"""

import requests
from log.logger import get_logger

logger = get_logger("AIRCRAFT")

OPENSKY_URL = "https://opensky-network.org/api/states/all"

# Approximate bounding boxes for common regions
REGION_BOXES = {
    "nigeria":       (4.0,  2.7,  13.9, 14.7),
    "lagos":         (6.3,  3.0,   6.8,  3.6),
    "abuja":         (8.9,  7.0,   9.3,  7.5),
    "uk":            (49.9, -7.6,  58.7,  1.8),
    "london":        (51.3, -0.5,  51.7,  0.3),
    "usa":           (24.4,-125.0, 49.4,-66.9),
    "new york":      (40.5, -74.3, 40.9,-73.7),
    "europe":        (36.0, -10.0, 71.0, 30.0),
    "germany":       (47.3,  5.9,  55.1, 15.0),
    "france":        (42.3, -4.8,  51.1,  8.2),
    "south africa":  (-34.8, 16.5,-22.1, 32.9),
}
DEFAULT_BOX = (4.0, 2.7, 13.9, 14.7)  # Nigeria


def _get_box(region: str) -> tuple:
    region_lower = region.lower().strip()
    for key, box in REGION_BOXES.items():
        if key in region_lower or region_lower in key:
            return box
    return DEFAULT_BOX


def get_flights_over(region: str = "Nigeria", max_results: int = 5) -> dict:
    """
    Return live flights over the specified region.
    Returns {region, count, flights: [{callsign, origin_country, altitude_m, speed_ms}]}
    """
    lamin, lomin, lamax, lomax = _get_box(region)
    params = {
        "lamin": lamin, "lomin": lomin,
        "lamax": lamax, "lomax": lomax,
    }
    try:
        resp = requests.get(OPENSKY_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenSky request failed: {e}")
        return {"error": f"Couldn't reach OpenSky radar: {e}"}

    states = data.get("states") or []
    flights = []
    for s in states[:max_results]:
        callsign = (s[1] or "Unknown").strip() or "Unknown"
        origin   = s[2] or "Unknown"
        altitude = s[13]
        speed    = s[9]
        flights.append({
            "callsign": callsign,
            "origin_country": origin,
            "altitude_m": round(altitude) if altitude else None,
            "speed_ms": round(speed, 1) if speed else None,
        })
    return {"region": region, "count": len(states), "flights": flights}


def describe_flights(region: str = "Nigeria") -> str:
    """Return a natural language summary of flights over the region."""
    result = get_flights_over(region, max_results=5)
    if "error" in result:
        return result["error"]
    count = result["count"]
    region_name = result["region"].title()
    if count == 0:
        return f"No aircraft detected over {region_name} right now."
    lines = [f"There are {count} aircraft currently tracked over {region_name}."]
    for f in result["flights"]:
        alt_ft = f"{round(f['altitude_m'] * 3.281):,} ft" if f["altitude_m"] else "unknown altitude"
        spd_kts = f"{round(f['speed_ms'] * 1.944)} knots" if f["speed_ms"] else "unknown speed"
        lines.append(f"{f['callsign']} from {f['origin_country']} — {alt_ft}, {spd_kts}.")
    return " ".join(lines)