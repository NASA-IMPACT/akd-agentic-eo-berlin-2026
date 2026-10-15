"""run_area and compare_area: TerraMind over an area larger than one job, stitched.

The TerraMind service takes at most 16 tiles of 2.24 km per job (4 while its GPU tier is asleep). run_area splits
the area into 2 x 2-tile blocks on the service's own tile grid, submits one job per block in parallel and stitches
the results, so a 9 km area runs as four jobs (about 3 minutes on the CPU tier) and a 20 km area as 25 jobs that the
GPU worker batches together.

Both tools are stateless and idempotent: the service caches identical requests, so calling run_area again with the
same item_id and aoi re-attaches to the same jobs instead of starting new ones. The agent simply calls it again until
it reports `succeeded`, then calls compare_area with the same arguments.
"""
from __future__ import annotations

import io
import json
import math
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import numpy as np
import rasterio
from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from fastmcp.utilities.types import Image
from mcp.types import TextContent
from PIL import Image as PILImage
from rasterio.io import MemoryFile
from rasterio.merge import merge
from rasterio.warp import transform_geom
from shapely.geometry import box, mapping, shape

from tools.compare_maps import PALETTE, compare_outputs, tool_result
from tools.pick_scene import AREA_MAX_TILES, COLLECTION, SPAN_M, TILE, _plan, _plan_area, _tiles_allowed

mcp = FastMCP("Run area")
# Your own TerraMind inference service (Tools/README.md, "Serve TerraMind yourself"). No default: this
# repository ships no endpoint.
DEFAULT_API = os.environ.get("TM_API_URL", "")
NO_API = "TM_API_URL is not set: point it at your own TerraMind inference service (see Tools/README.md)"
ITEM_URL = "https://earth-search.aws.element84.com/v1/collections/{collection}/items/{item_id}"
OUTPUTS = ["S1GRD", "DEM", "LULC"]
WAIT_S = 40                               # per call; the service keeps working between calls
# The TerraMind API is rate limited for everyone together (API Gateway, 20 requests/s in October 2026). While jobs
# wait in its queue, each user's checks add up, so: check every POLL_S plus a random offset (users do not fall into
# step), retry a throttled or briefly unavailable request instead of failing the tool call, and remember jobs so a
# finished one is never asked about again and a running one is checked by id rather than re-submitted.
POLL_S, POLL_JITTER_S = 15.0, 5.0
RETRY_STATUS = (429, 502, 503, 504)
RETRY_BUDGET_S = 45.0
KNOWN_FRESH_S = 6 * 3600                  # job file links stay valid 24 h; re-read a finished job after 6 h
_known: dict[str, dict] = {}              # request body -> {"job": last job record, "at": time}
_known_lock = threading.Lock()
PREVIEW_PX = 768
NAMES = {0: "no data", 1: "water", 2: "trees", 3: "flooded vegetation", 4: "crops", 5: "built area",
         6: "bare ground", 7: "snow/ice", 8: "clouds", 9: "rangeland"}


def _area_limit(api_url: str) -> tuple[int, int, str]:
    """(tiles per job, tiles per area, why) for the tier the service is on right now."""
    per_job, why = _tiles_allowed(api_url)
    return per_job, AREA_MAX_TILES["gpu" if per_job >= 16 else "cpu"], why


def _blocks(item: dict, plan: dict) -> list[dict]:
    """Split the planned window into blocks of at most 2 x 2 tiles, each a bbox the service plans to exactly that
    block (same grid, no gaps, no overlap). Always 2 x 2, whatever the tier: the layout must not change if a GPU wakes
    between two calls (run_area and compare_area re-derive the same jobs from it), every tier accepts 4 tiles, and the
    GPU worker batches tiles across jobs anyway."""
    side = 2
    epsg, (x0, _, _, y0) = plan["epsg"], plan["bounds"]
    out = []
    for r0 in range(0, plan["ny"], side):
        for c0 in range(0, plan["nx"], side):
            h, w = min(side, plan["ny"] - r0), min(side, plan["nx"] - c0)
            ub = (x0 + c0 * SPAN_M, y0 - (r0 + h) * SPAN_M, x0 + (c0 + w) * SPAN_M, y0 - r0 * SPAN_M)
            inner = box(ub[0] + 300, ub[1] + 300, ub[2] - 300, ub[3] - 300)
            bbox = [round(v, 6) for v in shape(transform_geom(f"EPSG:{epsg}", "EPSG:4326", mapping(inner))).bounds]
            p = _plan(item, tuple(bbox))
            if (p["nx"], p["ny"]) != (w, h) or any(abs(a - b) > 1e-6 for a, b in zip(p["bounds"], ub)):
                raise ValueError(f"block at row {r0}, col {c0} does not land on the service grid")
            out.append({"bbox": bbox, "row": r0, "col": c0, "tiles": w * h})
    return out


def _api(method: str, url: str, **kw) -> httpx.Response:
    """One request to the TerraMind API. A 429 or a 502/503/504 is retried with backoff (Retry-After when given,
    else 1, 2, 4, 8 s plus jitter) for up to RETRY_BUDGET_S; the last answer is returned either way."""
    give_up = time.time() + RETRY_BUDGET_S
    attempt = 0
    while True:
        try:
            resp = httpx.request(method, url, timeout=60, **kw)
        except httpx.TransportError:              # connect or read timeout, dropped connection: a blip, try again
            if time.time() >= give_up:
                raise
            time.sleep(min(8.0, 2.0 ** attempt) + random.uniform(0, 1.0))
            attempt += 1
            continue
        if resp.status_code not in RETRY_STATUS or time.time() >= give_up:
            return resp
        try:
            delay = float(resp.headers.get("retry-after", ""))
        except ValueError:
            delay = min(8.0, 2.0 ** attempt)
        delay += random.uniform(0, 1.0)
        attempt += 1
        time.sleep(max(0.0, min(delay, give_up - time.time())))


def _remember(key: str, job: dict) -> dict:
    with _known_lock:
        _known[key] = {"job": job, "at": time.time()}
    return job


def _area(item_id: str, aoi, api_url: str, outputs: list[str]) -> dict:
    """Plan the area and submit (or re-attach to) one job per block. Returns jobs and metadata, or {'error'}."""
    try:
        w, s, e, n = (float(v) for v in aoi)
    except (TypeError, ValueError):
        return {"error": "aoi must be a bbox [west, south, east, north]; pass the `aoi` returned by pick_scene"}
    r = httpx.get(ITEM_URL.format(collection=COLLECTION, item_id=item_id), timeout=30)
    if r.status_code == 404:
        return {"error": f"no Sentinel-2 item {item_id}; pass the `item_id` returned by pick_scene"}
    r.raise_for_status()
    item = r.json()
    plan = _plan_area(item, (w, s, e, n))
    per_job, area_max, why = _area_limit(api_url)
    tiles = plan["nx"] * plan["ny"]
    if tiles > area_max:
        km = round(math.sqrt(area_max) * SPAN_M / 1000, 1)
        return {"error": f"the area needs {plan['nx']}x{plan['ny']}={tiles} tiles; the most that runs right now is "
                         f"{area_max} tiles (about {km} x {km} km, {why}). Use the `aoi` from pick_scene, or ask the "
                         "user which sub-area matters."}
    if not plan["covered"]:
        return {"error": "the area is not fully covered by this scene; use the item_id and aoi pick_scene returned"}
    blocks = _blocks(item, plan)

    def submit(b):
        body = {"input": {"type": "stac_item", "item_id": item_id, "aoi": b["bbox"]}, "outputs": outputs,
                "timesteps": 10, "wait": 0}
        key = api_url + json.dumps(body, sort_keys=True)
        with _known_lock:
            known = _known.get(key)
        if known:
            job = known["job"]
            if job.get("status") == "succeeded" and time.time() - known["at"] < KNOWN_FRESH_S:
                return job                       # finished and its file links still valid: no request at all
            if job.get("job_id") and job.get("status") != "failed":
                resp = _api("GET", f"{api_url}/v1/jobs/{job['job_id']}")
                if resp.status_code in (200, 202):           # 202 = still running
                    return _remember(key, resp.json())
        resp = _api("POST", f"{api_url}/v1/jobs", json=body)
        if resp.status_code == 422:
            return {"status": "failed", "error": resp.json().get("detail")}
        resp.raise_for_status()
        return _remember(key, resp.json())

    with ThreadPoolExecutor(min(8, len(blocks))) as ex:
        jobs = list(ex.map(submit, blocks))
    return {"item": item, "plan": plan, "blocks": blocks, "jobs": jobs, "per_job": per_job, "why": why}


def _refresh(api_url: str, jobs: list[dict], deadline: float) -> list[dict]:
    """Check unfinished jobs every POLL_S (+ jitter) until all are final or the deadline passes."""
    final = ("succeeded", "failed")
    while any(j.get("status") not in final for j in jobs):
        wait = min(POLL_S + random.uniform(0, POLL_JITTER_S), deadline - time.time())
        if wait <= 0:
            break
        time.sleep(wait)
        pending = [i for i, j in enumerate(jobs) if j.get("status") not in final and j.get("job_id")]

        def check(i):
            try:
                resp = _api("GET", f"{api_url}/v1/jobs/{jobs[i]['job_id']}")
            except httpx.HTTPError:               # a check that fails is simply made again next time
                return jobs[i]
            # 200 finished, 202 still running; anything else (still throttled): keep the old state
            return resp.json() if resp.status_code in (200, 202) else jobs[i]

        with ThreadPoolExecutor(min(8, len(pending) or 1)) as ex:
            fresh = list(ex.map(check, pending))
        for i, j in zip(pending, fresh):
            jobs[i] = j
        with _known_lock:                                      # keep the job memory current
            for k, v in _known.items():
                for j in fresh:
                    if j.get("job_id") and v["job"].get("job_id") == j["job_id"]:
                        v["job"], v["at"] = j, time.time()
    return jobs


def _get(url: str) -> bytes:
    """Download a job file. Network blips and S3's 500/503 ('slow down') are retried a few times."""
    for attempt in range(4):
        try:
            r = httpx.get(url, timeout=120, follow_redirects=True)
            if r.status_code in (500, 502, 503, 504) and attempt < 3:
                raise httpx.HTTPStatusError("retry", request=r.request, response=r)
            r.raise_for_status()
            return r.content
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            if attempt == 3 or (isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500):
                raise
            time.sleep(1.5 * (attempt + 1) + random.uniform(0, 1.0))


def _stitch_rgb(jobs: list[dict]) -> PILImage.Image:
    """True colour over the whole area with ONE contrast stretch. The service stretches each job's preview to its
    own 1-99 percentiles, so stitched job previews come out as visibly different squares (a block of sea next to a
    block of land); here the input bands B04, B03, B02 are stitched first and stretched once, as the service does."""
    data, _ = _mosaic([j["input"]["cog_url"] for j in jobs], indexes=[4, 3, 2])
    rgb = (data.astype(np.float32) - 1000) / 10000.0  # TerraMind input convention carries the +1000 offset
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99)
    hi = max(hi, lo + 0.05)
    x = np.clip((rgb - lo) / (hi - lo), 0, 1) ** (1 / 1.3)
    return PILImage.fromarray((x.transpose(1, 2, 0) * 255).round().astype(np.uint8))


def _mosaic(urls: list[str], indexes: list[int] | None = None) -> tuple[np.ndarray, dict]:
    """Stitch per-job GeoTIFFs (same CRS and grid) into one array plus its profile."""
    with ThreadPoolExecutor(8) as ex:
        blobs = list(ex.map(_get, urls))
    mems = [MemoryFile(b) for b in blobs]
    srcs = [m.open() for m in mems]
    data, transform = merge(srcs, indexes=indexes)
    profile = {**srcs[0].profile, "height": data.shape[1], "width": data.shape[2], "transform": transform,
               "driver": "GTiff"}
    profile.pop("tiled", None); profile.pop("blockxsize", None); profile.pop("blockysize", None)
    for s_, m in zip(srcs, mems):
        s_.close(); m.close()
    return data, profile


def _png(im: PILImage.Image, fmt: str) -> bytes:
    im = im.copy()
    im.thumbnail((PREVIEW_PX, PREVIEW_PX), PILImage.NEAREST if fmt == "png" else PILImage.BILINEAR)
    buf = io.BytesIO()
    im.save(buf, format=fmt.upper(), **({"quality": 85} if fmt == "jpeg" else {"optimize": True}))
    return buf.getvalue()


def _summary(item: dict, plan: dict, blocks: list[dict], jobs: list[dict]) -> dict:
    tiles = [b["tiles"] for b in blocks]
    wsum = float(sum(tiles))
    cloud = sum(t * float((j.get("tile") or {}).get("cloud_fraction") or 0) for t, j in zip(tiles, jobs)) / wsum
    ndvi = [((j.get("input") or {}).get("observed_ndvi") or {}).get("mean") for j in jobs]
    ndvi_mean = (sum(t * v for t, v in zip(tiles, ndvi) if v is not None) / sum(t for t, v in zip(tiles, ndvi) if v is not None)
                 if any(v is not None for v in ndvi) else None)
    km = [round(plan["nx"] * SPAN_M / 1000, 1), round(plan["ny"] * SPAN_M / 1000, 1)]
    return {
        "scene": {"item_id": item["id"], "datetime": item["properties"]["datetime"],
                  "cloud_cover": item["properties"].get("eo:cloud_cover")},
        "aoi": plan["aoi"],
        "tile": {"tiles": plan["nx"] * plan["ny"], "km": km,
                 "cloud_fraction": round(cloud, 4), "crs": f"EPSG:{plan['epsg']}"},
        "input": {"observed_ndvi": {"mean": round(ndvi_mean, 3) if ndvi_mean is not None else None,
                                    "note": "tile-weighted mean of the jobs' observed NDVI"}},
        "jobs": [{"job_id": j.get("job_id"), "seed": j.get("seed"), "tiles": t} for j, t in zip(jobs, tiles)],
    }


@mcp.tool
def run_area(item_id: str, aoi: list[float], outputs: list[str] | None = None, api_url: str | None = None) -> ToolResult:
    """Run TerraMind over the whole area: split it into jobs on the service's tile grid, run them in parallel, stitch.

    Pass the `item_id` and `aoi` returned by pick_scene, exactly. The call waits up to about 40 s. If the result says
    `running`, call run_area again with the same arguments (it re-attaches to the same jobs, nothing is restarted).
    When it says `succeeded` it returns the stitched land-cover shares, the cloud fraction over the area, the observed
    NDVI, the job ids for provenance, and the stitched true-colour and land-cover images for the user. Then call
    compare_area with the same item_id and aoi.

    Args:
        item_id: Sentinel-2 item id from pick_scene. Required.
        aoi: The bbox [west, south, east, north] from pick_scene.
        outputs: TerraMind outputs to generate. Default S1GRD, DEM, LULC (never NDVI).
        api_url: TerraMind API base URL. Defaults to TM_API_URL.
    """
    base = (api_url or DEFAULT_API).rstrip("/")
    if not base:
        raise ValueError(NO_API)
    outputs = [o for o in (outputs or OUTPUTS) if o in ("S1GRD", "DEM", "LULC")] or OUTPUTS
    started = time.time()
    try:
        area = _area(item_id, aoi, base, outputs)
    except (httpx.HTTPError, ValueError) as e:
        return ToolResult(content=[TextContent(type="text", text=f"run_area failed: {e}")], is_error=True)
    if "error" in area:
        return ToolResult(content=[TextContent(type="text", text=area["error"])], is_error=True)
    jobs = _refresh(base, area["jobs"], started + WAIT_S)
    plan, blocks, item = area["plan"], area["blocks"], area["item"]
    failed = [j for j in jobs if j.get("status") == "failed"]
    if failed:
        return ToolResult(content=[TextContent(type="text", text="run_area: a job failed: " + str(failed[0].get("error"))[:300])],
                          is_error=True)
    done = sum(j.get("status") == "succeeded" for j in jobs)
    if done < len(jobs):
        info = {"status": "running", "jobs_done": done, "jobs_total": len(jobs), "tiles": plan["nx"] * plan["ny"],
                "compute": jobs[0].get("compute"),
                "next_step": "Call run_area again with the same item_id and aoi; nothing restarts."}
        return ToolResult(content=[TextContent(type="text", text=str(info))], structured_content=info)

    summary = {"status": "succeeded", **_summary(item, plan, blocks, jobs)}
    lulc, _ = _mosaic([j["outputs"]["LULC"]["cog_url"] for j in jobs]) if "LULC" in outputs else (None, None)
    content: list = []
    if lulc is not None:
        c = lulc[0]
        vals, counts = np.unique(c, return_counts=True)
        classes = [{"id": int(v), "name": NAMES.get(int(v), str(v)), "fraction": round(float(k) / c.size, 4)}
                   for v, k in sorted(zip(vals, counts), key=lambda t: -t[1]) if k / c.size >= 0.001]
        summary["outputs"] = {"LULC": {"stats": {"classes": classes}}}
        # Ready to quote, as the legend prints them, so the agent never converts fractions itself.
        summary["class_shares"] = [f"{c['name'].capitalize()}: {100 * c['fraction']:.1f}% of the area" for c in classes]
    km = summary["tile"]["km"]
    summary["summary"] = (f"Stitched {len(jobs)} jobs into one {km[0]} x {km[1]} km area ({plan['nx'] * plan['ny']} tiles) "
                          f"from scene {item['id']}; cloud over the area {summary['tile']['cloud_fraction']:.0%}.")
    content.append(TextContent(type="text", text=__import__("json").dumps(summary, indent=1)))
    try:
        rgb = _stitch_rgb(jobs)
        content += [TextContent(type="text", text="preview: input S2 RGB"),
                    Image(data=_png(rgb, "jpeg"), format="jpeg").to_image_content()]
    except Exception as e:  # previews are best effort
        content.append(TextContent(type="text", text=f"(true-colour preview unavailable: {e})"))
    if lulc is not None:
        c = lulc[0]
        rgb = np.zeros(c.shape + (3,), np.uint8)
        for v, col in PALETTE.items():
            rgb[c == v] = col
        content += [TextContent(type="text", text="preview: LULC"),
                    Image(data=_png(PILImage.fromarray(rgb), "png"), format="png").to_image_content()]
    return ToolResult(content=content, structured_content=summary)


@mcp.tool
def compare_area(item_id: str, aoi: list[float], include_image: bool = True, api_url: str | None = None) -> ToolResult:
    """Compare the stitched TerraMind area with independent references and return the error metrics.

    Call after run_area has reported `succeeded`, with the same item_id and aoi. Land cover against ESRI 10 m Annual
    Land Cover, elevation against Copernicus DEM GLO-30, radar against the nearest Sentinel-1 RTC pass, plus the
    water-versus-radar cross-check, all over the whole stitched area. Same metrics, verdict hints and summary sentences
    as compare_maps. Call this before any claim about whether a generated product is fit for use.

    Args:
        item_id: Sentinel-2 item id from pick_scene.
        aoi: The bbox from pick_scene.
        include_image: Attach a side-by-side image of generated versus reference products.
        api_url: TerraMind API base URL. Defaults to TM_API_URL.
    """
    base = (api_url or DEFAULT_API).rstrip("/")
    if not base:
        raise ValueError(NO_API)
    try:
        area = _area(item_id, aoi, base, OUTPUTS)
    except (httpx.HTTPError, ValueError) as e:
        return ToolResult(content=[TextContent(type="text", text=f"compare_area failed: {e}")], is_error=True)
    if "error" in area:
        return ToolResult(content=[TextContent(type="text", text=area["error"])], is_error=True)
    jobs = _refresh(base, area["jobs"], time.time() + 10)
    if any(j.get("status") != "succeeded" for j in jobs):
        return ToolResult(content=[TextContent(type="text", text="The area is still running; call run_area until it "
                                                                 "reports succeeded, then compare_area.")], is_error=True)
    mems, hrefs = [], {}
    # The input bands go along for the snow check (the service's input convention carries the +1000 offset).
    for prod, urls in [(p, [j["outputs"][p]["cog_url"] for j in jobs]) for p in OUTPUTS] + \
                      [("input", [j["input"]["cog_url"] for j in jobs])]:
        data, profile = _mosaic(urls)
        mem = MemoryFile()
        with mem.open(**profile) as dst:
            dst.write(data)
        mems.append(mem)
        hrefs[prod] = mem.name
    try:
        scene = {"item_id": area["item"]["id"], "datetime": area["item"]["properties"]["datetime"]}
        ident = {"area": {"item_id": item_id, "tiles": area["plan"]["nx"] * area["plan"]["ny"],
                          "aoi": area["plan"]["aoi"], "job_ids": [j["job_id"] for j in jobs]}}
        input_href = hrefs.pop("input")
        result, panels = compare_outputs(hrefs, scene, ident, input_href=input_href, offset=1000.0)
    finally:
        for m in mems:
            m.close()
    return tool_result(result, panels, include_image)
