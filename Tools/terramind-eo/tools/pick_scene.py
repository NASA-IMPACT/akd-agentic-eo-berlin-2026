"""pick_scene: the Sentinel-2 scene to run TerraMind on for a date. Nearest first, judged over the window.

Scene-level cloud cover (`eo:cloud_cover`) says nothing about the few kilometres the agent cares about,
and sorting a search by it hands back the clearest scene of the year instead of the one nearest the event.
This tool searches Earth Search outwards from the date (±2, 5, 10, 21, 45, 90 days), keeps only scenes
whose footprint fully contains the window the TerraMind service will cut (same 2.24 km tile grid, same
centring, same snapping), reads the scene classification (SCL) over that window and reports the cloud
fraction there. It returns the item id plus the exact `aoi` to pass to `run_area`, which splits the area into
parallel jobs and stitches them: up to 16 tiles (about 9 km) while the service's GPU tier is asleep, up to 81
tiles (about 20 km) with a GPU.
"""
from __future__ import annotations

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date as _date, datetime, timedelta

import httpx
import numpy as np
import rasterio
from fastmcp import FastMCP
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds
from shapely.geometry import Point, box, mapping, shape

mcp = FastMCP("Pick scene")
EARTH_SEARCH = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-c1-l2a"
# Your own TerraMind inference service (Tools/README.md, "Serve TerraMind yourself"). No default: this
# repository ships no endpoint.
DEFAULT_API = os.environ.get("TM_API_URL", "")

# Mirrors terramind_service.constants / tiling: the window must match what the service cuts.
TILE, GSD = 224, 10
SPAN_M = TILE * GSD                      # 2240 m per tile
SCL_CLOUDY = [3, 8, 9, 10]               # cloud shadow, cloud medium, cloud high, thin cirrus
SCL_NODATA = [0]
SERVICE_MAX_CLOUD = 0.5                  # the service refuses a window cloudier than this
FALLBACK_MAX_TILES = 4                   # tiles per job when the service's health endpoint cannot be read
AREA_MAX_TILES = {"gpu": 81, "cpu": 16}  # stitched by run_area: 9 x 9 tiles (about 20 km) with a GPU, 4 x 4 on CPU
STEPS_DAYS = (2, 5, 10, 21, 45, 90)
DEFAULT_MAX_DAYS = {"before": 90, "after": 21, "nearest": 30}
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
                GDAL_HTTP_MULTIPLEX="YES", GDAL_HTTP_VERSION="2", VSI_CACHE="TRUE",
                CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.tiff")


def _bbox(aoi) -> tuple[float, float, float, float]:
    if isinstance(aoi, (list, tuple)):
        if len(aoi) == 2:  # a point, e.g. a GDACS event centre: the service centres a tile on it
            lon, lat = (float(v) for v in aoi)
            aoi = [lon, lat, lon, lat]
        if len(aoi) != 4:
            raise ValueError("aoi must be a bbox [west, south, east, north] in WGS84 degrees")
        w, s, e, n = (float(v) for v in aoi)
        if not (-180 <= w <= e <= 180 and -90 <= s <= n <= 90):
            raise ValueError("aoi must be [west, south, east, north] in WGS84 degrees")
        if w == s == e == n == 0:
            # A placeholder, not a place: a model that skipped geocode writes zeros.
            raise ValueError("aoi [0, 0, 0, 0] is not an area. Call geocode for the place and pass its window_8km.")
        return w, s, e, n
    if isinstance(aoi, dict):
        geom = aoi.get("geometry", aoi) if aoi.get("type") == "Feature" else aoi
        return shape(geom).bounds
    raise ValueError("aoi must be a bbox list or a GeoJSON geometry")


def _geom(bbox: tuple):
    """A zero-area bbox (a point AOI) is a Point: STAC rejects degenerate polygons and the service centres a tile on it."""
    w, s, e, n = bbox
    return Point(w, s) if (w == e and s == n) else box(w, s, e, n)


def _item_epsg(item: dict) -> int:
    p = item["properties"]
    if p.get("proj:epsg"):
        return int(p["proj:epsg"])
    code = p.get("proj:code") or item["assets"]["red"].get("proj:code")
    if code and code.startswith("EPSG:"):
        return int(code.split(":")[1])
    raise ValueError(f"item {item['id']} has no projection info")


AREA_TOLERANCE = 0.07  # an area's own window bounds, re-read as an AOI, grow by grid convergence (up to ~6 %)


def _plan(item: dict, bbox: tuple, tol: float = 0.0) -> dict:
    """The window the service would cut for this AOI on this scene, whether the scene covers it, and `aoi`: a bbox
    that plans back to exactly this window (what the tools hand to the agent).

    tol=0 mirrors the service exactly (used to check each job's block). Areas are planned with AREA_TOLERANCE so that
    a bbox which is already a planned window (rotated into UTM it is a little larger) keeps its tile count."""
    plan = _plan_core(item, bbox, tol)
    plan["aoi"] = _snapped_aoi(item, plan, tol)
    return plan


def _snapped_aoi(item: dict, plan: dict, tol: float) -> list[float]:
    """The window inset by 300 m, as a WGS84 bbox, nudged until it plans back to the very same window (centring
    rounds to the 10 m grid, and the round trip through degrees can land one pixel off)."""
    epsg, (bx0, by0, bx1, by1) = plan["epsg"], plan["bounds"]
    dx = dy = 0.0
    bb = None
    for _ in range(4):
        ub = box(bx0 + 300 + dx, by0 + 300 + dy, bx1 - 300 + dx, by1 - 300 + dy)
        bb = [round(v, 6) for v in shape(transform_geom(f"EPSG:{epsg}", "EPSG:4326", mapping(ub))).bounds]
        q = _plan_core(item, tuple(bb), tol)
        ex, ey = bx0 - q["bounds"][0], by1 - q["bounds"][3]
        if abs(ex) < 1e-6 and abs(ey) < 1e-6 and (q["nx"], q["ny"]) == (plan["nx"], plan["ny"]):
            break
        dx, dy = dx + ex, dy + ey
    return bb


def _plan_core(item: dict, bbox: tuple, tol: float = 0.0) -> dict:
    epsg = _item_epsg(item)
    g = shape(transform_geom("EPSG:4326", f"EPSG:{epsg}", mapping(_geom(bbox))))
    minx, miny, maxx, maxy = g.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    nx = max(1, math.ceil((maxx - minx) * (1 - tol) / SPAN_M))
    ny = max(1, math.ceil((maxy - miny) * (1 - tol) / SPAN_M))
    t = item["assets"]["red"].get("proj:transform")
    ox, oy = (t[2], t[5]) if t else (0.0, 0.0)
    x0 = ox + round((cx - nx * SPAN_M / 2 - ox) / GSD) * GSD
    y0 = oy + round((cy + ny * SPAN_M / 2 - oy) / GSD) * GSD
    bounds = (x0, y0 - ny * SPAN_M, x0 + nx * SPAN_M, y0)
    window_wgs = shape(transform_geom(f"EPSG:{epsg}", "EPSG:4326", mapping(box(*bounds))))
    covered = shape(item["geometry"]).buffer(1e-9).contains(window_wgs)
    return {"epsg": epsg, "bounds": bounds, "nx": nx, "ny": ny, "covered": covered,
            "bbox_wgs84": [round(v, 6) for v in window_wgs.bounds]}


def _plan_area(item: dict, bbox: tuple) -> dict:
    return _plan(item, bbox, AREA_TOLERANCE)


def _scl_fractions(item: dict, plan: dict) -> tuple[float, float]:
    """(cloud, nodata) fractions over the window, from the scene classification at its native 20 m."""
    with rasterio.Env(**GDAL_ENV), rasterio.open(item["assets"]["scl"]["href"]) as src:
        win = from_bounds(*plan["bounds"], transform=src.transform)
        scl = src.read(1, window=win, boundless=False)
    if scl.size == 0:
        return 1.0, 1.0
    return float(np.isin(scl, SCL_CLOUDY).mean()), float(np.isin(scl, SCL_NODATA).mean())


def _search(bbox: tuple, start: _date, end: _date, limit: int = 100) -> list[dict]:
    # Sorted by date and cut at `limit`: a short limit silently drops the later half of a step's scenes (an area on
    # two overlapping MGRS tiles returns two items per date), so ask for all of them.
    body = {"collections": [COLLECTION], "intersects": mapping(_geom(bbox)),
            "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
            "sortby": [{"field": "properties.datetime", "direction": "asc"}], "limit": limit}
    r = httpx.post(EARTH_SEARCH, json=body, timeout=30)
    r.raise_for_status()
    return r.json().get("features", [])


_health_cache: dict[str, tuple[float, dict]] = {}
HEALTH_TTL_S = 30.0  # every pick_scene and run_area asks; the rate-limited API need not answer each one


def _tiles_allowed(api_url: str) -> tuple[int, str]:
    """How many tiles the service takes right now, and why."""
    try:
        cached = _health_cache.get(api_url)
        if cached and time.time() - cached[0] < HEALTH_TTL_S:
            h = cached[1]
        else:
            h = httpx.get(f"{api_url}/v1/health", timeout=10).json()
            _health_cache[api_url] = (time.time(), h)
        limits = h.get("limits") or {}
        gpu, cpu = int(limits.get("max_tiles_gpu", 16)), int(limits.get("max_tiles_cpu", FALLBACK_MAX_TILES))
        if h.get("mode") != "aws":
            return gpu, "local service"
        if str(h.get("compute", "")).startswith("gpu-ready"):
            return gpu, "GPU ready"
        return cpu, f"GPU tier asleep ({h.get('compute', 'cpu-only')}), CPU tier limit"
    except Exception as e:  # health unreachable: be conservative, never block the pick
        return FALLBACK_MAX_TILES, f"service health unreadable ({type(e).__name__}), assumed CPU tier"


def _shrink(bbox: tuple, nx: int, ny: int, allowed: int) -> tuple[tuple, int, int]:
    """A centred WGS84 bbox that re-plans to at most `allowed` tiles, keeping the AOI's aspect."""
    while nx * ny > allowed:
        if nx >= ny:
            nx -= 1
        else:
            ny -= 1
    w, s, e, n = bbox
    clat, clon = (s + n) / 2, (w + e) / 2
    # 600 m under the tile multiple so grid convergence (up to ~3 deg) cannot push ceil() to one more tile.
    half_x, half_y = (nx * SPAN_M - 600) / 2, (ny * SPAN_M - 600) / 2
    dlat = half_y / 111320.0
    dlon = half_x / (111320.0 * max(math.cos(math.radians(clat)), 0.1))
    return (round(clon - dlon, 6), round(clat - dlat, 6), round(clon + dlon, 6), round(clat + dlat, 6)), nx, ny


def _parse_date(value: str) -> _date:
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).date()
    except ValueError:
        raise ValueError(f"date must be ISO, e.g. 2023-05-17, got {value!r}") from None


def pick(aoi, date: str, side: str = "nearest", max_days: int | None = None,
         max_cloud_fraction: float = 0.2, api_url: str | None = None) -> dict:
    """The logic behind the tool, callable without MCP."""
    side = (side or "nearest").strip().lower()
    if side not in DEFAULT_MAX_DAYS:
        return {"error": "side must be 'before', 'after' or 'nearest'"}
    try:
        bbox = _bbox(aoi)
        target = _parse_date(date)
    except ValueError as e:
        return {"error": str(e)}
    max_days = int(max_days or DEFAULT_MAX_DAYS[side])
    base = (api_url or DEFAULT_API).rstrip("/")
    # The scene search needs no TerraMind service; without one, plan for the CPU tier's tile limit.
    per_job, allowed_why = (
        _tiles_allowed(base) if base else (FALLBACK_MAX_TILES, "no TerraMind service set (TM_API_URL), CPU tier limit assumed")
    )
    allowed = AREA_MAX_TILES["gpu" if per_job >= 16 else "cpu"]

    seen: dict[str, dict] = {}        # item id -> evaluation
    not_covering = 0
    steps = [d for d in STEPS_DAYS if d < max_days] + [max_days]
    best: dict | None = None
    note = None
    for step in steps:
        # "before" stops the day before the date (the event day may already show it); "after" includes it.
        start = target - timedelta(days=step) if side != "after" else target
        end = target + timedelta(days=step) if side != "before" else target - timedelta(days=1)
        try:
            items = [i for i in _search(bbox, start, end) if i["id"] not in seen]
        except httpx.HTTPError as e:
            return {"error": f"Earth Search unavailable: {e}"}
        fresh = []
        for item in items:
            try:
                plan = _plan_area(item, bbox)
                if plan["nx"] * plan["ny"] > AREA_MAX_TILES["gpu"]:
                    # Larger than can ever run: never silently shrink a user's area to its centre.
                    km_x, km_y = round(plan["nx"] * SPAN_M / 1000, 1), round(plan["ny"] * SPAN_M / 1000, 1)
                    return {"error": f"the AOI needs {plan['nx']}x{plan['ny']}={plan['nx'] * plan['ny']} tiles of 2.24 km "
                                     f"(about {km_x} x {km_y} km); at most {AREA_MAX_TILES['gpu']} tiles (about 20 x 20 km) "
                                     "can run. Ask the user which sub-area matters, then geocode that place or pass a bbox "
                                     "of at most 20 km a side."}
                if note is None and plan["nx"] * plan["ny"] > allowed:
                    # Shrink once, before measuring anything, so every number is for the window that will run.
                    bbox, nx, ny = _shrink(bbox, plan["nx"], plan["ny"], allowed)
                    note = (f"The AOI needs {plan['nx']}x{plan['ny']}={plan['nx'] * plan['ny']} tiles but only {allowed} "
                            f"run right now ({allowed_why}); the area is reduced to the central {nx}x{ny} tiles "
                            f"(about {round(nx * SPAN_M / 1000, 1)} km) and `aoi` is that smaller box. Say so in the report.")
                    plan = _plan_area(item, bbox)
            except ValueError:
                seen[item["id"]] = {"skipped": "no projection info"}
                continue
            if not plan["covered"]:
                not_covering += 1
                seen[item["id"]] = {"skipped": "does not cover the window"}
                continue
            fresh.append((item, plan))
        if fresh:
            with ThreadPoolExecutor(min(6, len(fresh))) as ex:
                fractions = list(ex.map(lambda ip: _scl_fractions(*ip), fresh))
            for (item, plan), (cloud, nodata) in zip(fresh, fractions):
                when = datetime.fromisoformat(item["properties"]["datetime"].replace("Z", "+00:00"))
                ev = {"item": item, "plan": plan, "cloud": cloud, "nodata": nodata,
                      "days": (when.date() - target).days, "datetime": item["properties"]["datetime"]}
                seen[item["id"]] = ev
                if nodata > 0.02:
                    continue  # the service rejects swath-edge windows
                if best is None or (round(cloud, 2), abs(ev["days"])) < (round(best["cloud"], 2), abs(best["days"])):
                    best = ev
        if best is not None and best["cloud"] <= max_cloud_fraction:
            break  # clear enough this close to the date: stop widening

    checked = [{"item_id": k, "datetime": v.get("datetime"), "window_cloud_fraction": round(v["cloud"], 3),
                "days_from_date": v["days"]} for k, v in seen.items() if "cloud" in v]
    checked.sort(key=lambda c: abs(c["days_from_date"]))
    if best is None and not checked:
        # Nothing covered the window at all: that is about the area, not the weather, so it must never be reported
        # as "no clear scene".
        why = ("no single Sentinel-2 scene covers this whole window (it crosses the edge of the satellite's tiles)"
               if not_covering else "Sentinel-2 has no scene over this area")
        return {"error": f"{why}. Check the aoi: call geocode for the place and pass its window_8km, or a smaller "
                         "area. This says nothing about clouds; do not report that no clear scene exists.",
                "date": target.isoformat(), "side": side}
    if best is None:
        return {"error": f"no usable Sentinel-2 scene within {max_days} days {side} {target}: "
                         f"{len(checked)} scenes cover the window, none under {SERVICE_MAX_CLOUD:.0%} cloud over it"
                         + (f"; {not_covering} more only cover it partly" if not_covering else ""),
                "checked": checked[:8], "date": target.isoformat(), "side": side,
                "report": (f"This date is not verified: no clear Sentinel-2 scene within {max_days} days {side} "
                           f"{target}. Say so in the report; describe only the date that ran; make no statement about "
                           "change between the dates; for a change question the answer is 'Cannot tell'.")}

    item, plan = best["item"], best["plan"]
    nx, ny = plan["nx"], plan["ny"]
    km_x, km_y = round(nx * SPAN_M / 1000, 1), round(ny * SPAN_M / 1000, 1)
    warning = None
    usable = best["cloud"] <= SERVICE_MAX_CLOUD
    if not usable:
        # Nothing clear enough to verify anything: still return the clearest scene, so the user sees the actual
        # before and after (and the clouds that make this date unusable) instead of an empty side.
        warning = (f"NOT VERIFIED: every scene within {max_days} days {side} {target} is more than "
                   f"{SERVICE_MAX_CLOUD:.0%} cloudy over the window; this is the clearest, {best['cloud']:.0%} cloud. "
                   "Run it with run_area and compare_area so the user can see it, but use none of its numbers as a "
                   "finding, make no statement about change between the dates, and answer 'Cannot tell'.")
    elif best["cloud"] > max_cloud_fraction:
        warning = (f"Nothing clearer than {best['cloud']:.0%} cloud over the window within {max_days} days; "
                   "say so in the report, or widen max_days.")
    days = best["days"]
    # Scenes nearer the date that lost to the chosen one: the report can say why they were not used.
    nearer = [{"item_id": c["item_id"], "datetime": c["datetime"][:10], "window_cloud_fraction": c["window_cloud_fraction"]}
              for c in checked if abs(c["days_from_date"]) < abs(days)][:5]
    rel = "on" if days == 0 else f"{abs(days)} day{'s' if abs(days) != 1 else ''} {'after' if days > 0 else 'before'}"
    summary = (("NOT VERIFIED, too cloudy to use: " if not usable else "") +
               f"Scene {item['id']} from {best['datetime'][:10]} ({rel} {target}): {best['cloud']:.0%} cloud over "
               f"the {km_x} x {km_y} km window ({nx * ny} tile{'s' if nx * ny != 1 else ''}); scene-level cloud "
               f"{item['properties'].get('eo:cloud_cover', float('nan')):.0f}%.")
    if nearer:
        summary += (f" {len(nearer)} nearer scene{'s' if len(nearer) > 1 else ''} rejected as cloudy over the window"
                    f" ({', '.join(f'{n['datetime']} {n['window_cloud_fraction']:.0%}' for n in nearer)}).")
    return {
        "item_id": item["id"], "datetime": best["datetime"], "days_from_date": days, "usable": usable,
        "scene_cloud_cover_pct": round(float(item["properties"].get("eo:cloud_cover") or 0), 1),
        "window": {"cloud_fraction": round(best["cloud"], 3), "nodata_fraction": round(best["nodata"], 3),
                   "tiles": nx * ny, "km": [km_x, km_y]},
        "aoi": plan["aoi"],
        "nearer_rejected": nearer,
        "searched": {"side": side, "max_days": max_days, "scenes_checked": len(checked), "not_covering": not_covering,
                     "tiles_allowed_now": allowed, "why": allowed_why},
        "note": note, "warning": warning, "summary": summary,
    }


@mcp.tool
def pick_scene(aoi: list[float] | dict, date: str, side: str = "nearest", max_days: int | None = None,
               max_cloud_fraction: float = 0.2, api_url: str | None = None) -> dict:
    """Choose the Sentinel-2 scene nearest a date that is clear over the AOI window, ready for TerraMind.

    Searches outwards from the date (2, 5, 10, 21, 45, 90 days, up to `max_days`), keeps only scenes
    that fully cover the window TerraMind will cut, measures cloud over that window from the scene
    classification layer (not the scene-level figure), and stops at the first step with a scene under
    `max_cloud_fraction`. Call it once per date, then pass its `item_id` and `aoi` to `run_area`
    exactly as returned. When every scene is more than 50% cloudy over the window it still returns the
    clearest one with `usable: false` and a warning: run it so the user sees it, but that date is not
    verified. Returns `error` (not an exception) when no scene covers the window at all, or when the AOI
    is larger than about 20 x 20 km (then ask the user which sub-area
    matters). For a change study call it twice: side "before" with the date the event started, side
    "after" with the date it ended.

    Args:
        aoi: Bounding box [west, south, east, north] in WGS84 (up to about 20 km a side), e.g. `window_8km` from geocode.
        date: The date of interest, ISO format, e.g. 2023-05-17 (the event date for a change study).
        side: "before" (scenes up to the date), "after" (from the date on) or "nearest" (either side).
        max_days: How far from the date to look. Defaults: before 90, after 21, nearest 30.
        max_cloud_fraction: Cloud over the window accepted without looking further (default 0.2).
        api_url: TerraMind API base URL. Defaults to TM_API_URL.
    """
    return pick(aoi, date, side, max_days, max_cloud_fraction, api_url)
