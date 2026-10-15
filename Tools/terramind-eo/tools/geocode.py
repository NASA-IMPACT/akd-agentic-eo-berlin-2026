"""Geocode and reverse geocode via OpenStreetMap Nominatim, cached and throttled to 1 request/s."""
from __future__ import annotations

import os
import threading
import time
from functools import lru_cache

import httpx
from fastmcp import FastMCP

mcp = FastMCP("Geocode")
_UA = {"User-Agent": os.environ.get("NOMINATIM_USER_AGENT", "eo-mcp-tools/0.2")}
_lock = threading.Lock()
_last = 0.0


def _get(url: str, params: dict) -> dict | list:
    global _last
    with _lock:
        wait = 1.0 - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        r = httpx.get(url, params=params, headers=_UA, timeout=15)
    r.raise_for_status()
    return r.json()


@lru_cache(maxsize=4096)
def _search(query: str) -> tuple:
    out = []
    for hit in _get("https://nominatim.openstreetmap.org/search", {"q": query, "format": "json", "limit": 5, "accept-language": "en"}):
        s, n, w, e = (float(x) for x in hit["boundingbox"])
        out.append((hit["display_name"], (w, s, e, n)))
    return tuple(out)


@lru_cache(maxsize=4096)
def _reverse(lat: float, lon: float, zoom: int) -> dict:
    return _get("https://nominatim.openstreetmap.org/reverse", {"lat": lat, "lon": lon, "format": "json", "zoom": zoom, "accept-language": "en"})


def _window(bbox: tuple) -> dict:
    """Square windows centred on the bbox, sized to TerraMind's 2.24 km tile grid: 4 km re-plans to 2 x 2
    tiles (always accepted) and 8 km to 4 x 4 (the service's 16-tile limit, needs its GPU tier)."""
    import math
    w, s, e, n = bbox
    clat, clon = (s + n) / 2, (w + e) / 2
    out = {"centre": [round(clon, 5), round(clat, 5)]}
    for km in (4.0, 8.0):
        dlat = km / 2 / 111.0
        dlon = km / 2 / (111.0 * max(math.cos(math.radians(clat)), 0.1))
        out[f"window_{km:.0f}km"] = [round(clon - dlon, 5), round(clat - dlat, 5), round(clon + dlon, 5), round(clat + dlat, 5)]
    return out


@mcp.tool
def geocode(query: str) -> dict:
    """Place name or description to a bounding box [west, south, east, north], EPSG:4326.

    Returns one bbox when the match is unambiguous, otherwise up to 3 candidates to choose from.
    Also returns `centre` [lon, lat] and `window_4km`, a 4 by 4 km bbox around the centre: pass
    `window_4km` to TerraMind's generate instead of the full bbox, and never compute windows yourself.
    Returns an error message, not an exception, when nothing matches.

    Args:
        query: Place name, e.g. "Conselice, Italy" or "Guaraqueçaba, Brazil".
    """
    try:
        hits = _search(query.strip())
    except httpx.HTTPError as e:
        return {"error": f"geocoding service unavailable: {e}"}
    if not hits:
        return {"error": f"no match for '{query}'. Try adding the country or a nearby city."}
    if len(hits) == 1:
        name, bbox = hits[0]
        return {"bbox": list(bbox), "display_name": name, **_window(bbox)}
    return {"candidates": [{"display_name": n, "bbox": list(b), **_window(b)} for n, b in hits[:3]],
            "message": "Several matches. Pick one, or ask the user."}


@mcp.tool
def reverse_geocode(lat: float, lon: float) -> dict:
    """Coordinates to a place: country, state or region, county, nearest town.

    Use this before naming the location of a tile or an event. Never infer a place name from
    coordinates without calling it.

    Args:
        lat: Latitude in degrees, EPSG:4326.
        lon: Longitude in degrees, EPSG:4326.
    """
    try:
        j = _reverse(round(lat, 3), round(lon, 3), 10)
    except httpx.HTTPError as e:
        return {"error": f"geocoding service unavailable: {e}"}
    a = j.get("address", {})
    return {"display_name": j.get("display_name"), "country": a.get("country"),
            "state": a.get("state"), "county": a.get("county"),
            "town": a.get("city") or a.get("town") or a.get("village") or a.get("municipality")}
