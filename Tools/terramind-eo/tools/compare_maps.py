"""compare_maps: check TerraMind's generated products against independent references.

Land cover against ESRI 10 m Annual Land Cover, elevation against Copernicus DEM GLO-30, radar
backscatter against the nearest real Sentinel-1 RTC pass, NDVI against the value computed from the
input bands. References come from Microsoft Planetary Computer, no key needed. Returns metrics as
structured content and a side-by-side image for the human.
"""
from __future__ import annotations

import io
import json
import os
from datetime import datetime, timedelta

import httpx
import numpy as np
import planetary_computer as pc
import rasterio
from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from fastmcp.utilities.types import Image
from mcp.types import TextContent
from PIL import Image as PILImage, ImageDraw
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

mcp = FastMCP("Compare maps")
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
# Your own TerraMind inference service (Tools/README.md, "Serve TerraMind yourself"). No default: this
# repository ships no endpoint.
DEFAULT_API = os.environ.get("TM_API_URL", "")
NO_API = "TM_API_URL is not set: point it at your own TerraMind inference service (see Tools/README.md)"

# TerraMesh / TerraMind class ids, and the ESRI Annual Land Cover ids they correspond to.
CLASSES = {0: "no data", 1: "water", 2: "trees", 3: "flooded vegetation", 4: "crops", 5: "built area",
           6: "bare ground", 7: "snow/ice", 8: "clouds", 9: "rangeland"}
ESRI_TO_TM = {0: 0, 1: 1, 2: 2, 4: 3, 5: 4, 7: 5, 8: 6, 9: 7, 10: 8, 11: 9}
PALETTE = {0: (0, 0, 0), 1: (49, 113, 173), 2: (70, 156, 118), 3: (131, 202, 112), 4: (234, 225, 89),
           5: (192, 124, 184), 6: (193, 147, 104), 7: (111, 178, 228), 8: (241, 241, 241), 9: (198, 101, 38)}
# Verdict thresholds. This table is the CARE Phase 2.4 output-format artifact in code: the agent reports
# these hints, it does not invent its own thresholds. Edit here, re-verify, redeploy.
THRESHOLDS = {
    "LULC":  {"fit": {"pixel_accuracy": 0.80}, "caveat": {"pixel_accuracy": 0.60}},
    "DEM":   {"fit": {"pearson_r": 0.70, "mae_max": 5.0}, "caveat": {"pearson_r": 0.30}},
    "S1GRD": {"fit": {"pearson_r": 0.60, "bias_abs_max": 3.0}, "caveat": {"pearson_r": 0.30}},
}
WATER_VV_DB = -15.0   # open or flooded surfaces are darker than this in VV
WATER_AGREE_PCT = 60.0  # or: generated water at least WATER_SEP_DB darker than the rest of the tile
WATER_SEP_DB = 4.0
WATER_JUDGE_MIN_PCT = 1.0  # below this share of the area there is too little generated water to judge against radar
# Snow: the annual map shows the land cover under the snow, so generated snow is judged against the snow index of
# the same Sentinel-2 image instead (Hall et al.: NDSI above 0.4 with near-infrared reflectance above 0.11).
SNOW_NDSI = 0.4
SNOW_NIR = 0.11
SNOW_AGREE_PCT = 60.0
FLAT_RELIEF_M = 30.0   # below this 2-98 percentile relief, an elevation correlation is mostly noise


def _water_agrees(radar: dict | None) -> bool:
    return bool(radar) and (radar["agreement_pct"] >= WATER_AGREE_PCT or radar["separation_db"] >= WATER_SEP_DB)


def _verdict_lulc(m: dict, radar: dict | None, snow: dict | None = None) -> dict:
    acc = m.get("pixel_accuracy", 0)
    if snow and snow["generated_snow_pct"] >= 5 and snow["agreement_pct"] >= SNOW_AGREE_PCT:
        return {"verdict": "fit for snow detection", "basis": "snow index",
                "reason": f"{snow['agreement_pct']}% of generated snow/ice is snow by the snow index of the same "
                          f"Sentinel-2 image; the annual land-cover reference shows the land cover under the snow, so "
                          f"its accuracy ({acc}) does not apply"}
    if radar and radar["generated_water_pct"] >= 5 and _water_agrees(radar):
        return {"verdict": "fit for water detection", "basis": "radar agreement",
                "reason": f"{radar['agreement_pct']}% of generated water is dark in the Sentinel-1 pass and it is "
                          f"{radar['separation_db']} dB darker than the rest of the tile; the annual land-cover reference "
                          f"cannot show transient water, so its accuracy ({acc}) does not apply"}
    if acc >= THRESHOLDS["LULC"]["fit"]["pixel_accuracy"]:
        return {"verdict": "fit", "basis": "annual land cover", "reason": f"pixel accuracy {acc}"}
    if acc >= THRESHOLDS["LULC"]["caveat"]["pixel_accuracy"]:
        return {"verdict": "fit with caveat", "basis": "annual land cover", "reason": f"pixel accuracy {acc}"}
    return {"verdict": "not fit", "basis": "annual land cover", "reason": f"pixel accuracy {acc}"}


def _verdict_cont(product: str, m: dict) -> dict:
    t = THRESHOLDS[product]; r = m.get("pearson_r") or 0.0
    if r >= t["fit"]["pearson_r"] and m["mae"] <= t["fit"].get("mae_max", 1e9) and abs(m["bias"]) <= t["fit"].get("bias_abs_max", 1e9):
        return {"verdict": "fit", "reason": f"r {r}, bias {m['bias']}, MAE {m['mae']}"}
    if r >= t["caveat"]["pearson_r"]:
        return {"verdict": "fit with caveat", "reason": f"r {r} is moderate; bias {m['bias']}, MAE {m['mae']}"}
    return {"verdict": "not fit", "reason": f"r {r} is below {t['caveat']['pearson_r']}: the spatial pattern is not reproduced, whatever the bias"}


GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_USE_HEAD="NO", GDAL_HTTP_MAX_RETRY="3")


def _stac(collection: str, bbox: list[float], datetime_range: str | None = None, limit: int = 20) -> list[dict]:
    body = {"collections": [collection], "bbox": bbox, "limit": limit}
    if datetime_range:
        body["datetime"] = datetime_range
    r = httpx.post(PC_STAC, json=body, timeout=60)
    r.raise_for_status()
    return r.json().get("features", [])


def _on_grid(href: str, like: dict, band: int = 1, resampling=Resampling.nearest) -> np.ndarray:
    """Read a remote raster reprojected onto the generated product's grid."""
    with rasterio.Env(**GDAL_ENV), rasterio.open(href) as src:
        with WarpedVRT(src, crs=like["crs"], transform=like["transform"], width=like["width"], height=like["height"],
                       resampling=resampling, nodata=src.nodata) as vrt:
            a = vrt.read(band).astype("float32")
            if src.nodata is not None:
                a[a == src.nodata] = np.nan
            return a


def _on_grid_many(hrefs: list[str], like: dict, band: int = 1, resampling=Resampling.nearest, valid=np.isfinite) -> np.ndarray:
    """Like _on_grid over several reference items: each later item fills the pixels the earlier ones left empty,
    so an area that straddles two DEM tiles, land-cover zones or Sentinel-1 frames is covered completely."""
    out = None
    for href in hrefs:
        a = _on_grid(href, like, band, resampling)
        if out is None:
            out = a
        else:
            gap = ~valid(out) & valid(a)
            out[gap] = a[gap]
        if valid(out).all():
            break
    return out


def _open(href: str) -> tuple[np.ndarray, dict]:
    with rasterio.Env(**GDAL_ENV), rasterio.open(href) as src:
        data = src.read().astype("float32")
        like = {"crs": src.crs, "transform": src.transform, "width": src.width, "height": src.height,
                "bbox": list(transform_bounds(src.crs, "EPSG:4326", *src.bounds))}
    return data, like


def _stats(gen: np.ndarray, ref: np.ndarray) -> dict:
    m = np.isfinite(gen) & np.isfinite(ref)
    g, r = gen[m].astype("float64"), ref[m].astype("float64")
    if g.size < 10:
        return {"error": "no overlapping valid pixels"}
    err = g - r
    return {"n_pixels": int(g.size), "bias": round(float(err.mean()), 3), "mae": round(float(np.abs(err).mean()), 3),
            "rmse": round(float(np.sqrt((err ** 2).mean())), 3),
            "pearson_r": round(float(np.corrcoef(g, r)[0, 1]), 3) if g.std() > 0 and r.std() > 0 else None,
            "generated": {"mean": round(float(g.mean()), 3), "min": round(float(g.min()), 3), "max": round(float(g.max()), 3)},
            "reference": {"mean": round(float(r.mean()), 3), "min": round(float(r.min()), 3), "max": round(float(r.max()), 3)}}


def _lulc_metrics(gen: np.ndarray, ref: np.ndarray) -> dict:
    m = np.isfinite(ref) & (ref > 0) & (gen > 0)
    g, r = gen[m].astype(int), ref[m].astype(int)
    n = g.size
    out = {"n_pixels": int(n), "pixel_accuracy": round(float((g == r).mean()), 3), "classes": [], "top_confusions": []}
    for c in sorted(set(np.unique(g)) | set(np.unique(r))):
        inter, union = int(((g == c) & (r == c)).sum()), int(((g == c) | (r == c)).sum())
        out["classes"].append({"class": CLASSES.get(c, str(c)), "generated_pct": round(100 * float((g == c).mean()), 1),
                               "reference_pct": round(100 * float((r == c).mean()), 1),
                               "iou": round(inter / union, 3) if union else None})
    conf = {}
    for a, b in zip(r[g != r], g[g != r]):
        conf[(int(a), int(b))] = conf.get((int(a), int(b)), 0) + 1
    for (a, b), k in sorted(conf.items(), key=lambda x: -x[1])[:4]:
        out["top_confusions"].append({"reference": CLASSES[a], "generated_as": CLASSES[b], "pct_of_tile": round(100 * k / n, 1)})
    return out


def _panel(arr: np.ndarray, kind: str, lo=None, hi=None, size: int = 256) -> PILImage.Image:
    a = np.array(arr, dtype="float32")
    if kind == "lulc":
        rgb = np.zeros(a.shape + (3,), dtype="uint8")
        for c, col in PALETTE.items():
            rgb[a == c] = col
        im = PILImage.fromarray(rgb)
    else:
        a = np.nan_to_num(a, nan=lo if lo is not None else 0)
        lo = float(np.nanpercentile(a, 2)) if lo is None else lo
        hi = float(np.nanpercentile(a, 98)) if hi is None else hi
        g = np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1)
        im = PILImage.fromarray((g * 255).astype("uint8")).convert("RGB")
    return im.resize((size, size), PILImage.NEAREST if kind == "lulc" else PILImage.BILINEAR)


def _figure(panels: list[tuple[str, PILImage.Image]]) -> bytes:
    w, h, pad, top = 256, 256, 8, 18
    canvas = PILImage.new("RGB", (len(panels) * (w + pad) + pad, h + top + pad), (20, 22, 26))
    d = ImageDraw.Draw(canvas)
    for i, (label, im) in enumerate(panels):
        x = pad + i * (w + pad)
        canvas.paste(im, (x, top))
        d.text((x + 2, 3), label, fill=(230, 230, 230))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@mcp.tool
async def compare_maps(job_id: str, api_url: str | None = None, include_image: bool = True) -> ToolResult:
    """Compare a finished TerraMind generation with independent references and return the error metrics.

    Land cover against ESRI 10 m Annual Land Cover (pixel accuracy, class-wise IoU, confusions),
    elevation against Copernicus DEM GLO-30 (bias, MAE, RMSE, r), radar backscatter against the nearest
    real Sentinel-1 RTC pass in dB (per polarisation), and generated NDVI against NDVI computed from the
    input bands. Call this before any claim about whether a generated product is fit for use. Every
    number in the result is computed from the rasters, nothing is estimated.

    Args:
        job_id: A TerraMind job id with status succeeded, from generate or get_generation.
        api_url: TerraMind API base URL. Defaults to TM_API_URL.
        include_image: Attach a side-by-side PNG of generated versus reference products.
    """
    base = (api_url or DEFAULT_API).rstrip("/")
    if not base:
        raise ValueError(NO_API)
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(f"{base}/v1/jobs/{job_id}")
    if r.status_code == 404:
        return ToolResult(content=[TextContent(type="text", text=f"No job {job_id}")], is_error=True)
    r.raise_for_status()
    job = r.json()
    if job.get("status") != "succeeded":
        return ToolResult(content=[TextContent(type="text", text=f"Job {job_id} is {job.get('status')}, not succeeded")], is_error=True)
    hrefs = {m: o["cog_url"] for m, o in (job.get("outputs") or {}).items()}
    result, panels = compare_outputs(hrefs, job["scene"], {"job_id": job_id},
                                     input_href=(job.get("input") or {}).get("cog_url"),
                                     offset=float((job.get("tile") or {}).get("offset_added", 0) or 0))
    return tool_result(result, panels, include_image)


def finite(x):
    """`x` with every NaN or infinite number replaced by None: JSON has no NaN, and a client that stores the result
    (a database, another service) rejects it."""
    if isinstance(x, dict):
        return {k: finite(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [finite(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return float(x) if np.isfinite(x) else None
    return x


def tool_result(result: dict, panels: list, include_image: bool = True) -> ToolResult:
    result = finite(result)
    # What the report quotes goes first: a reader that only takes the start (a guard with a size limit) still sees it.
    first = [k for k in ("table", "summary", "caveats", "notes") if k in result]
    result = {**{k: result[k] for k in first}, **{k: v for k, v in result.items() if k not in first}}
    content = [TextContent(type="text", text=json.dumps(result, indent=1, allow_nan=False))]
    if include_image and panels:
        content.append(Image(data=_figure(panels), format="png").to_image_content())
    return ToolResult(content=content, structured_content=result)


def compare_outputs(hrefs: dict, scene: dict, ident: dict, input_href: str | None = None,
                    offset: float = 0.0) -> tuple[dict, list]:
    """Compare generated products (product -> raster href) with the independent references. `ident` names the run
    (a job id, or the jobs of a stitched area). Returns the metrics and the image panels."""
    outputs = {m: {"cog_url": h} for m, h in hrefs.items()}
    scene_dt = scene["datetime"]
    result = {**ident, "scene": {"item_id": scene["item_id"], "datetime": scene_dt},
              "products": {}, "references": {}, "notes": []}
    panels: list[tuple[str, PILImage.Image]] = []
    like = None
    ref_vv = None

    # ---- radar vs nearest Sentinel-1 RTC pass -------------------------------------------------------------
    if "S1GRD" in outputs:
        gen, like_s = _open(outputs["S1GRD"]["cog_url"])
        t = datetime.fromisoformat(scene_dt.replace("Z", "+00:00"))
        rng = f"{(t - timedelta(days=12)).date()}/{(t + timedelta(days=12)).date()}"
        items = _stac("sentinel-1-rtc", like_s["bbox"], rng)
        if items:
            when = lambda i: datetime.fromisoformat(i["properties"]["datetime"].replace("Z", "+00:00"))
            item = min(items, key=lambda i: abs(when(i) - t))
            same_pass = [item] + [i for i in items if i is not item and abs((when(i) - when(item)).total_seconds()) < 120]
            res = {}
            for b, pol in ((0, "vv"), (1, "vh")):
                lin = _on_grid_many([pc.sign(i["assets"][pol]["href"]) for i in same_pass], like_s,
                                    resampling=Resampling.bilinear, valid=lambda a: np.isfinite(a) & (a > 0))
                ref_db = np.where(lin > 0, 10 * np.log10(np.where(lin > 0, lin, 1)), np.nan).astype("float32")
                res[pol.upper() + "_dB"] = _stats(gen[b], ref_db)
                res[pol.upper() + "_dB"]["verdict_hint"] = _verdict_cont("S1GRD", res[pol.upper() + "_dB"])
                if pol == "vv":
                    ref_vv = ref_db
                    panels += [("generated VV dB", _panel(gen[0], "gray", -25, 0)), ("Sentinel-1 RTC VV dB", _panel(ref_db, "gray", -25, 0))]
            result["products"]["S1GRD"] = res
            days = round(abs((datetime.fromisoformat(item["properties"]["datetime"].replace("Z", "+00:00")) - t).total_seconds()) / 86400, 1)
            result["references"]["S1GRD"] = {"dataset": "Sentinel-1 RTC gamma0, dB", "item": item["id"], "datetime": item["properties"]["datetime"], "days_from_scene": days}
            result["notes"].append("Generated backscatter is GRD-like and the reference is terrain corrected, so a few dB of difference on slopes is expected.")

    # ---- land cover vs ESRI annual land cover ---------------------------------------------------------
    if "LULC" in outputs:
        gen, like = _open(outputs["LULC"]["cog_url"])
        gen = gen[0]
        year = int(scene_dt[:4])
        items = _stac("io-lulc-annual-v02", like["bbox"])
        years = sorted({int(i["properties"]["start_datetime"][:4]) for i in items})
        use_year = max([y for y in years if y <= year] or years[-1:])
        zone = str(like["crs"].to_epsg())[-2:]
        cands = [i for i in items if int(i["properties"]["start_datetime"][:4]) == use_year]
        cands.sort(key=lambda i: not i["id"].startswith(zone))
        item = cands[0] if cands else None
        if item:
            ref = _on_grid_many([pc.sign(i["assets"]["data"]["href"]) for i in cands], like,
                                valid=lambda a: np.isfinite(a) & (a > 0))
            ref_tm = np.vectorize(lambda v: ESRI_TO_TM.get(int(v), 0))(np.nan_to_num(ref, nan=0)).astype("float32")
            lm = _lulc_metrics(gen, ref_tm)
            radar = None
            if ref_vv is not None and ref_vv.shape == gen.shape:
                water = gen == 1
                valid = np.isfinite(ref_vv)
                # Only where the radar has data, and only with enough water to measure: a few water pixels that all
                # fall on radar no-data would otherwise give NaN means (invalid JSON downstream).
                if (water & valid).sum() >= 100 and (~water & valid).sum() >= 100:
                    radar = {"generated_water_pct": float(f"{100 * round(float(water.mean()), 4):.1f}"),
                             "agreement_pct": round(100 * float((ref_vv[water & valid] < WATER_VV_DB).mean()), 1),
                             "ref_vv_mean_over_generated_water_db": round(float(np.nanmean(ref_vv[water & valid])), 2),
                             "ref_vv_mean_elsewhere_db": round(float(np.nanmean(ref_vv[~water & valid])), 2),
                             "threshold_db": WATER_VV_DB}
                    radar["separation_db"] = round(radar["ref_vv_mean_elsewhere_db"] - radar["ref_vv_mean_over_generated_water_db"], 2)
                    if radar["generated_water_pct"] >= WATER_JUDGE_MIN_PCT:
                        radar["agrees"] = _water_agrees(radar)
                    else:
                        radar["note"] = "too little generated water to judge against the radar"
                lm["water_vs_radar"] = radar or {
                    "generated_water_pct": float(f"{100 * round(float(water.mean()), 4):.1f}"),
                    "note": "no water generated" if not water.any() else "too little generated water to check against the radar"}
            snow = None
            gen_snow = gen == 7
            if input_href and gen_snow.mean() >= 0.01:
                inp, _ = _open(input_href)
                off = float(offset or 0)
                green, nir, swir = (inp[2] - off) / 1e4, (inp[7] - off) / 1e4, (inp[10] - off) / 1e4  # B03 B08 B11
                ndsi = np.where((green + swir) != 0, (green - swir) / np.where((green + swir) != 0, green + swir, 1), np.nan)
                if ndsi.shape == gen.shape:
                    obs = np.isfinite(ndsi) & (ndsi > SNOW_NDSI) & (nir > SNOW_NIR)
                    snow = {"generated_snow_pct": float(f"{100 * round(float(gen_snow.mean()), 4):.1f}"),
                            "agreement_pct": round(100 * float(obs[gen_snow].mean()), 1),
                            "observed_snow_pct": round(100 * float(obs.mean()), 1),
                            "index": "NDSI above 0.4 and near-infrared reflectance above 0.11, from the input bands"}
                    lm["snow_vs_index"] = snow
            lm["verdict_hint"] = _verdict_lulc(lm, radar, snow)
            result["products"]["LULC"] = lm
            result["references"]["LULC"] = {"dataset": "ESRI 10 m Annual Land Cover", "item": item["id"], "year": use_year}
            if use_year != year:
                result["notes"].append(f"Land-cover reference is for {use_year}; the scene is from {year}.")
            result["notes"].append("ESRI land cover is an annual composite. Transient water such as a flood appears as the "
                                   "usual class in the reference, so for events judge water against the Sentinel-1 pass, "
                                   "not against this map.")
            if snow:
                result["notes"].append("Snow is not in the annual map either (it shows the land cover under the snow), so "
                                       "generated snow is judged against the snow index of the same Sentinel-2 image.")
            panels += [("generated land cover", _panel(gen, "lulc")), (f"ESRI land cover {use_year}", _panel(ref_tm, "lulc"))]


    # ---- elevation vs Copernicus DEM ---------------------------------------------------------------------
    if "DEM" in outputs:
        gen, like_d = _open(outputs["DEM"]["cog_url"])
        gen = gen[0]
        items = _stac("cop-dem-glo-30", like_d["bbox"])
        if items:
            ref = _on_grid_many([pc.sign(i["assets"]["data"]["href"]) for i in items], like_d, resampling=Resampling.bilinear)
            dm = _stats(gen, ref); dm["verdict_hint"] = _verdict_cont("DEM", dm)
            result["products"]["DEM"] = dm
            relief = round(float(np.nanpercentile(ref, 98) - np.nanpercentile(ref, 2)), 1)
            if relief < FLAT_RELIEF_M and "mae" in dm:
                result["notes"].append(f"The area is nearly flat (the reference elevation varies by about {relief} m), so the "
                                       f"elevation correlation says little here; the mean elevation error is {dm['mae']} m.")
            result["references"]["DEM"] = {"dataset": "Copernicus DEM GLO-30, resampled from 30 m", "item": items[0]["id"]}
            lo, hi = float(np.nanpercentile(ref, 2)), float(np.nanpercentile(ref, 98))
            panels += [("generated elevation", _panel(gen, "gray", lo, hi)), ("Copernicus DEM", _panel(ref, "gray", lo, hi))]

    # ---- NDVI generated vs computed from the input bands -------------------------------------------------
    if "NDVI" in outputs and input_href:
        gen, _ = _open(outputs["NDVI"]["cog_url"])
        inp, _ = _open(input_href)
        off = float(offset or 0)
        red, nir = inp[3] - off, inp[7] - off   # B04, B08 in the 12-band order
        obs = np.where((nir + red) != 0, (nir - red) / np.where((nir + red) != 0, nir + red, 1), np.nan).astype("float32")
        s = _stats(gen[0], obs)
        s["range_compression"] = {"generated_span": round(s["generated"]["max"] - s["generated"]["min"], 3),
                                  "observed_span": round(s["reference"]["max"] - s["reference"]["min"], 3)}
        s["verdict_hint"] = {"verdict": "use the observed NDVI", "reason": "computed from the bands it is exact; the generated one is a model output"}
        result["products"]["NDVI"] = s
        result["references"]["NDVI"] = {"dataset": "computed from the input Sentinel-2 bands B08 and B04", "note": "exact by construction; prefer it over the generated NDVI"}

    # Caveats the report must carry, decided here rather than by the agent.
    result["caveats"] = []
    w = (result["products"].get("LULC") or {}).get("water_vs_radar") or {}
    if "agrees" in w and not w["agrees"]:
        result["caveats"].append(f"On {scene_dt[:10]}, the generated water does not agree with the Sentinel-1 radar.")

    # The report's trust table, ready to copy: the tool's verdicts with a plain reason each, so no verdict label is
    # retyped (and changed) by the agent.
    rows = []
    lulc = result["products"].get("LULC")
    if lulc:
        v = lulc["verdict_hint"]; acc = lulc.get("pixel_accuracy")
        if v["verdict"] == "fit for water detection":
            w = lulc["water_vs_radar"]
            why = (f"{w['agreement_pct']}% of the generated water is dark in the Sentinel-1 radar; the annual land-cover "
                   f"map cannot show a flood, so its accuracy ({acc}) does not apply.")
        elif v["verdict"] == "fit for snow detection":
            sn = lulc["snow_vs_index"]
            why = (f"{sn['agreement_pct']}% of the generated snow/ice is snow by the snow index; the annual land-cover "
                   f"map cannot show snow, so its accuracy ({acc}) does not apply.")
        else:
            why = f"Pixel accuracy {acc} against the ESRI annual land-cover map."
        rows.append(("Land cover", v["verdict"], why))
    radar = (result["products"].get("S1GRD") or {}).get("VV_dB")
    if radar and "verdict_hint" in radar:
        r = radar.get("pearson_r")
        why = f"VV r {r} against the real Sentinel-1 pass"
        why += (": the spatial pattern is not reproduced." if radar["verdict_hint"]["verdict"] == "not fit"
                else f"; bias {radar['bias']} dB, mean error {radar['mae']} dB.")
        rows.append(("Radar", radar["verdict_hint"]["verdict"], why))
    dem = result["products"].get("DEM")
    if dem and "verdict_hint" in dem:
        why = f"r {dem.get('pearson_r')} against the Copernicus DEM; mean error {dem['mae']} m."
        if dem["verdict_hint"]["verdict"] == "not fit":
            why = f"r {dem.get('pearson_r')} against the Copernicus DEM: the terrain pattern is not reproduced; mean error {dem['mae']} m."
        rows.append(("Elevation", dem["verdict_hint"]["verdict"], why))
    result["table"] = "\n".join(["| Product | Verdict | Why |", "|---|---|---|"] + [f"| {a} | {b} | {c} |" for a, b, c in rows])

    # Ready-made sentences per product. Quote these verbatim in the answer.
    result["summary"] = []
    for prod, m in result["products"].items():
        if prod == "LULC":
            w = m.get("water_vs_radar") or {}
            line = f"Land cover: pixel accuracy {m['pixel_accuracy']} against the annual map; verdict {m['verdict_hint']['verdict']}."
            if w.get("generated_water_pct") and "agreement_pct" in w:
                line += (f" Generated water covers {w['generated_water_pct']}% of the area; {w['agreement_pct']}% of it is dark in "
                         f"the Sentinel-1 pass, {w['separation_db']} dB darker than the rest, " +
                         (f"so the water {'agrees' if w['agrees'] else 'does not agree'} with the radar." if "agrees" in w
                          else "too little water to judge against the radar."))
            elif w.get("generated_water_pct"):
                # A little water, too little where the radar has data to measure it at all.
                line += (f" Generated water covers {w['generated_water_pct']}% of the area, too little to judge against "
                         "the radar.")
            sn = m.get("snow_vs_index") or {}
            if sn:
                line += (f" Generated snow/ice covers {sn['generated_snow_pct']}% of the area; {sn['agreement_pct']}% of it is "
                         f"snow by the snow index of the same image.")
            result["summary"].append(line)
        elif prod == "S1GRD":
            for pol in ("VV_dB", "VH_dB"):
                x = m[pol]; result["summary"].append(f"Radar {pol[:2]}: r {x['pearson_r']}, bias {x['bias']} dB, MAE {x['mae']} dB; verdict {x['verdict_hint']['verdict']}.")
        elif prod == "DEM":
            result["summary"].append(f"Elevation: r {m['pearson_r']}, bias {m['bias']} m, MAE {m['mae']} m; verdict {m['verdict_hint']['verdict']}.")
        elif prod == "NDVI":
            result["summary"].append(f"NDVI: generated mean {m['generated']['mean']} versus observed {m['reference']['mean']}; use the observed value.")
    return result, panels
