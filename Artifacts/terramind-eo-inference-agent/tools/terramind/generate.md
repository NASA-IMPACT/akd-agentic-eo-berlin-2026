# Tool: terramind.generate

## Purpose
Submit a TerraMind generation job for a given AOI and date range (or a forced scene), producing requested output layers.

## When it should be used
- After an AOI and dates are confirmed (and optionally after a scene is selected).

## Inputs (schema)
- `aoi` (bbox `[w,s,e,n]` **or** GeoJSON polygon)
- `start_date` (string, date or datetime)
- `end_date` (string, date or datetime)
- `outputs` (array of strings; default: all four)
  - Allowed values: `S1GRD`, `DEM`, `LULC`, `NDVI`
  - Typical agent request: `S1GRD`, `DEM`, `LULC` (omit `NDVI`)
- `timesteps` (integer, 1–25; default: 10)
- `item_id` (string, optional): force a specific Sentinel-2 scene

## Outputs (schema)
Single stable shape (agent checks `status`, not response shape):
- `job_id` (string)
- `status` (string; exactly one of: `queued`, `starting`, `running`, `succeeded`, `failed`)
- `retry_after_s` (number, present while not done)
- `message` (string, optional): present while not done when the service has a human-readable status message

On success (`status: succeeded`), additionally includes:
- `scene`: `item_id`, `datetime`
- `tile`: `bbox`, `tile_count`
- `seed`
- `timings`
- `outputs`: keyed by product; each contains `stats`, `cog_url`
- `input`: `cog_url`, `observed_ndvi`
- Preview images may be attached as tool-returned images (no `png_url` fields)

On failure (`status: failed`):
- `error` (string): plain-language error message
- (no `retry_after_s`; failure is final)

## Validation / business rules inside the tool
- Validate `outputs` is a subset of {`S1GRD`,`DEM`,`LULC`,`NDVI`}.
- Validate `timesteps` is within 1–25.
- Validate AOI size and tile-boundary constraints (service may reject AOIs that are too large or cross a tile border).

## Failures / retry hints
- If rejected due to AOI constraints or no suitable scene exists, return `status: failed` + `error`.

## Notes (tool vs context boundary)
- The tool executes the job and returns artifacts + provenance; interpretation and narrative reporting remain agent-owned.
