# Tools

`terramind-eo/` is an MCP server with the seven tools the TerraMind EO inference agent uses. It is laid out
like a server in ESA's EVE tool registry (https://github.com/eve-esa/mcp-tool-registry): one folder with
`server.py`, `requirements.txt` and a test.

| Tool | Does |
| --- | --- |
| geocode | Place name to a bounding box plus a ready 8 km window; ambiguous names return candidates. Cached, 1 request/s to Nominatim |
| reverse_geocode | Coordinates to a place name, so the report names the right place |
| search_gdacs_events | Live and recent disasters worldwide (GDACS), from the EVE registry |
| pick_scene | The Sentinel-2 scene nearest a date that is clear over the area and fully covers it, on TerraMind's tile grid. Measures cloud over the area, not the whole scene |
| run_area | Runs TerraMind over the area (up to about 20 x 20 km) as parallel jobs and stitches them: land-cover shares, observed NDVI, true-colour and land-cover images |
| compare_area | Checks each generated layer against an independent reference: land cover against ESRI's annual map, radar against the real Sentinel-1 pass, elevation against the Copernicus DEM, water against radar, snow against the snow index |
| compare_dates | Before versus after of the same area: per-class change checked against observations (flood: Sentinel-1 radar; fire: burn index dNBR; snow: snow index NDSI), with a Yes / No / Cannot tell answer by fixed rules |

The tools need no API keys. Four work out of the box: `geocode`, `reverse_geocode`, `search_gdacs_events` and
`pick_scene`. The other three (`run_area`, `compare_area`, `compare_dates`) generate layers with TerraMind, so they
need a TerraMind inference service that **you run yourself**: set `TM_API_URL` to its base URL (see
[Serve TerraMind yourself](#serve-terramind-yourself)). This repository ships no endpoint; without one, those
three answer "TM_API_URL is not set".

## Run it locally

Python 3.10 or later (tested with 3.12).

```bash
cd terramind-eo
pip install -r requirements.txt
export TM_API_URL=...             # optional: your TerraMind service, for run_area, compare_area, compare_dates
python server.py                  # serves http://127.0.0.1:8000/mcp
python test.py                   # in another terminal: lists the tools and calls three of them
```

## Put it on FastMCP Cloud (Horizon), free

FastMCP Cloud (https://horizon.prefect.io) builds an MCP server from a GitHub repository you own and gives it a
public URL. Pick one of two routes.

### Route A: through ESA's EVE tool registry

Your server sits next to ESA's servers, ready to be proposed to the registry later.

1. Fork https://github.com/eve-esa/mcp-tool-registry to your GitHub account.
2. Copy `terramind-eo/` from this folder into your fork as `servers/terramind-eo/`, then commit and push:
   ```bash
   git clone https://github.com/<you>/mcp-tool-registry.git
   cp -r terramind-eo mcp-tool-registry/servers/terramind-eo
   cd mcp-tool-registry && git add servers/terramind-eo && git commit -m "Add terramind-eo" && git push
   ```
3. Sign in at https://horizon.prefect.io with GitHub and give it access to your fork.
4. Create a server: repository = your fork, entrypoint = `servers/terramind-eo/server.py:mcp`.
5. Deploy, then connect it (below).

If the build does not install the packages in `servers/terramind-eo/requirements.txt`, use Route B.

### Route B: a repository of its own

The simplest build: the server is the whole repository.

1. Create an empty repository on GitHub, for example `<you>/terramind-eo`.
2. Put the contents of `terramind-eo/` at its top level, then commit and push:
   ```bash
   cp -r terramind-eo my-terramind-eo && cd my-terramind-eo
   git init -b main && git add . && git commit -m "TerraMind EO tools"
   git remote add origin https://github.com/<you>/terramind-eo.git && git push -u origin main
   ```
3. Sign in at https://horizon.prefect.io with GitHub and give it access to that repository.
4. Create a server: repository = yours, entrypoint = `server.py:mcp`.
5. Deploy, then connect it (below).

### Connect it

- Your server is at `https://<server-name>.fastmcp.app/mcp`. Every push to `main` redeploys it.
- With **authentication off**, anyone with the URL can call the tools. With it **on**, only people in your
  Horizon organisation can connect.
- Add the URL to the agent: in the harness (`../Harness`), one line under *MCP servers* (add a space and a token
  after the URL if your server needs one); in the AKD Agent Co-Design Studio, the agent's MCP servers.
- Keep secrets out of this server's code and repository.

### The TerraMind tools on FastMCP Cloud

`geocode`, `reverse_geocode`, `search_gdacs_events` and `pick_scene` work as soon as the server is deployed.
`run_area`, `compare_area` and `compare_dates` also need `TM_API_URL`, the address of your TerraMind inference
service, which must be reachable from the internet (FastMCP Cloud cannot reach your laptop). If you cannot set
environment variables for your FastMCP Cloud server, run this server on a machine where you can (see
*Run it locally*), next to your TerraMind service.

## Serve TerraMind yourself

*Placeholder: how to run your own TerraMind inference service, locally or in the cloud, is coming.*

`run_area`, `compare_area` and `compare_dates` call a TerraMind inference service over HTTP; set `TM_API_URL` to
its base URL. They use these routes:

| Route | Used for |
| --- | --- |
| `GET /v1/health` | how many tiles one job may cover right now |
| `POST /v1/jobs` | start a job for a Sentinel-2 item and an area; answers `200` with the result or `202` to poll |
| `GET /v1/jobs/{id}` | poll a job; the result lists the output files (GeoTIFFs, PNG previews, statistics) by URL |

## Add your own model as a tool

```python
@mcp.tool
def my_model(bbox: list[float], date: str) -> dict:
    """What it returns, its units, and when NOT to call it. The agent reads this."""
    result = call_my_model_or_its_api(bbox, date)
    return {"stats": result.stats, "scene": result.scene_id}   # numbers, not pixels
```

Typed arguments, a docstring that says when not to use it, and a dict of numbers back. If your model needs a GPU,
host it behind an HTTP API and call that API from the tool.

## Sending it upstream

The registry accepts servers by pull request (see its `CONTRIBUTING.md`). Its servers use the official MCP SDK;
this one uses the `fastmcp` package (it mounts several modules into one server), so it needs adapting before a
pull request.
