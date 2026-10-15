"""
EO MCP tools: the seven tools the Earth Observation FM Inference Agent uses, on one server.
=========================================================================================

Places:     geocode, reverse_geocode (cached, throttled Nominatim)
Events:     search_gdacs_events (ESA EVE tool registry)
TerraMind:  pick_scene, run_area, compare_area, compare_dates

Run locally:   pip install -r requirements.txt && python server.py     # http://127.0.0.1:8000/mcp
Deploy:        Horizon, entrypoint `server.py:mcp`, authentication off.
Add a model:   one typed function with a docstring under @mcp.tool. See README.md.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys

from fastmcp import FastMCP

mcp = FastMCP(
    "EO MCP tools",
    instructions=(
        "Tools for Earth-observation agents. geocode and reverse_geocode resolve places; search_gdacs_events "
        "lists live disasters; pick_scene, run_area, compare_area and compare_dates choose a Sentinel-2 scene, run "
        "TerraMind over an area and check the result. Name a place only after reverse_geocode."
    ),
)


# (module, environment variables it needs, packages it imports lazily). Missing either = skipped, not crashed.
# compare_area lives in tools/run_area.py; tools/compare_maps.py holds the reference checks it uses.
ESA_SERVERS = [
    ("tools.geocode", (), ()),
    ("esa.gdacs", (), ()),
    ("tools.pick_scene", (), ("rasterio", "shapely")),
    ("tools.run_area", (), ("rasterio", "shapely", "planetary_computer", "PIL")),
    ("tools.compare_dates", (), ("rasterio", "shapely", "planetary_computer", "PIL")),
]

mounted, skipped = [], []
for module, env, packages in ESA_SERVERS:
    missing = [v for v in env if not os.environ.get(v)]
    if missing:
        skipped.append(f"{module} (needs {', '.join(missing)})"); continue
    absent = [pk for pk in packages if importlib.util.find_spec(pk) is None]
    if absent:
        skipped.append(f"{module} (pip install {' '.join(absent)})"); continue
    try:
        mcp.mount(importlib.import_module(module).mcp)
        mounted.append(module)
    except Exception as e:  # missing optional package, bad data file: skip, never crash the server
        skipped.append(f"{module} ({type(e).__name__}: {str(e)[:60]})")

print(f"mounted: {', '.join(mounted)}", file=sys.stderr)
if skipped:
    print(f"skipped: {'; '.join(skipped)}", file=sys.stderr)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
