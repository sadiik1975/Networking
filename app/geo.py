"""Lightweight geocoding helpers backed by a static ZIP centroid table.

This avoids a dependency on an external geocoding API so the service can run
fully offline; swap `resolve_location` for a real geocoder in production.
"""
import math

# (latitude, longitude, city, state)
ZIP_CENTROIDS: dict[str, tuple[float, float, str, str]] = {
    "10001": (40.7506, -73.9972, "New York", "NY"),
    "10011": (40.7415, -74.0014, "New York", "NY"),
    "11201": (40.6957, -73.9903, "Brooklyn", "NY"),
    "12414": (42.2168, -73.8646, "Catskill", "NY"),
    "12601": (41.7004, -73.9210, "Poughkeepsie", "NY"),
    "07030": (40.7440, -74.0324, "Hoboken", "NJ"),
    "07302": (40.7178, -74.0431, "Jersey City", "NJ"),
    "02108": (42.3576, -71.0636, "Boston", "MA"),
    "02139": (42.3629, -71.1034, "Cambridge", "MA"),
    "19102": (39.9539, -75.1654, "Philadelphia", "PA"),
    "20001": (38.9109, -77.0164, "Washington", "DC"),
    "21201": (39.2938, -76.6155, "Baltimore", "MD"),
    "30303": (33.7537, -84.3900, "Atlanta", "GA"),
    "33101": (25.7743, -80.1937, "Miami", "FL"),
    "37201": (36.1667, -86.7833, "Nashville", "TN"),
    "60601": (41.8858, -87.6229, "Chicago", "IL"),
    "48226": (42.3314, -83.0458, "Detroit", "MI"),
    "55401": (44.9820, -93.2696, "Minneapolis", "MN"),
    "63101": (38.6318, -90.1940, "St. Louis", "MO"),
    "75201": (32.7876, -96.7996, "Dallas", "TX"),
    "77002": (29.7589, -95.3677, "Houston", "TX"),
    "78701": (30.2711, -97.7437, "Austin", "TX"),
    "80202": (39.7508, -104.9963, "Denver", "CO"),
    "85003": (33.4507, -112.0745, "Phoenix", "AZ"),
    "89101": (36.1716, -115.1391, "Las Vegas", "NV"),
    "90012": (34.0567, -118.2412, "Los Angeles", "CA"),
    "94103": (37.7725, -122.4147, "San Francisco", "CA"),
    "97201": (45.5122, -122.6797, "Portland", "OR"),
    "98101": (47.6089, -122.3352, "Seattle", "WA"),
}

EARTH_RADIUS_MILES = 3958.8


class LocationNotFoundError(ValueError):
    pass


def resolve_location(location: str) -> tuple[float, float]:
    """Resolve a ZIP code or "City, ST" string to (lat, lon)."""
    normalized = location.strip()
    if normalized.isdigit() and len(normalized) == 5 and normalized in ZIP_CENTROIDS:
        lat, lon, _, _ = ZIP_CENTROIDS[normalized]
        return lat, lon

    lowered = normalized.lower()
    for lat, lon, city, state in ZIP_CENTROIDS.values():
        if lowered in (f"{city}, {state}".lower(), city.lower()):
            return lat, lon

    raise LocationNotFoundError(f"Unrecognized location: {location!r}")


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_MILES * c
