# Hosted TerraMind inference service (AWS + MCP)

## Summary
A hosted TerraMind inference service on AWS, built for this workshop, exposed via an MCP server (and corresponding HTTP API). It is used to run TerraMind remotely (avoiding local GPU setup) and generate products such as land cover, radar backscatter, and elevation layers.

## Tool / API inventory
- **Name:** TerraMind hosted inference service
- **Owner:** TBD (team/org)
- **Purpose:** Remote TerraMind inference + generation
- **When currently used:** Model inference / generation step

## Access
- **Interfaces:** MCP server; HTTP API (behind the MCP server)
- **Endpoint(s):** Configured on the agent as its MCP server connection; not recorded in this design.
- **Auth model:** No auth (unlisted but public endpoint)

## Tools / operations
- `search_scenes` (offered by the service; not used by this design, which chooses scenes with `eo_tools.pick_scene`)
- `generate` (this design calls it through `eo_tools.run_area`, one job per block of the area)
- `get_generation`

## Inputs / outputs
- **AOI constraints / limits:**
  - AOI may cover up to **4 tiles** (each tile ~**2.24 km**) when running on CPU.
  - AOI may cover up to **16 tiles** when GPUs are warm.
  - AOI must sit inside a **single Sentinel-2 tile** (if the AOI crosses a tile border, the service rejects the request).
- **Temporal selector:** date range may be **any length**; the service/agent selects the clearest scene within the range.
- **Async behavior:** `generate` may return results if quick; otherwise it returns a `job_id` to poll via `get_generation`.
- **Outputs:**
  - JSON containing per-product statistics and provenance
  - GeoTIFFs and preview imagery returned as signed URLs

## Request/response schema (field-level, as currently used)

### `search_scenes`
- **Input fields:** `aoi`, `start_date`, `end_date`, `max_cloud_cover`, `limit`
- **Output fields:** list of scenes, each with: `item_id`, `datetime`, `cloud_cover`

### `generate`
- **Input fields:** `aoi`, `start_date`, `end_date`, `outputs`, `timesteps`, optional `item_id`
- **Output fields:**
  - `job_id`
  - `status`
  - `retry_after_s` (when not done)
  - (on success) the same success payload described under `get_generation`

### `get_generation`
- **Input fields:** `job_id`
- **Output fields (while not done):**
  - `job_id`
  - `status` one of: `queued`, `starting`, `running`, `succeeded`, `failed`
  - `retry_after_s`
- **Output fields (on success):**
  - `scene`: `item_id`, `datetime`
  - `tile`: `bbox`, `tile_count`
  - `seed`
  - `timings`
  - `outputs`: keyed by product; each includes `stats`, `cog_url`, `png_url`
  - `input`: `cog_url`, `observed_ndvi`

## Permissions, limits, operational constraints
- Jobs can take minutes on a shared endpoint (cold-starts can be slow).

## Known error patterns / failure modes
- Service rejects AOIs that are too large.
- Service rejects AOIs that cross a Sentinel-2 tile border.
- Cold-start behavior: first job of a session can take minutes.
- Queue saturation / throttling may occur under load.
