# Tool: eo_tools.run_area

## Purpose
Run TerraMind over the whole AOI: split it into blocks on the service's 2.24 km tile grid, run one job per block in parallel, and stitch the results into one area.

## When it should be used
- Once per date, after `pick_scene`, with its `item_id` and `aoi`.

## Inputs (schema)
- `item_id` (string, required): Sentinel-2 item id from `pick_scene`.
- `aoi` (bbox `[w,s,e,n]`): the `aoi` from `pick_scene`.
- `outputs` (optional): default LULC, S1GRD, DEM; NDVI is never requested.

## Outputs (schema)
### Still running
- `status`: `running`, `jobs_done`, `jobs_total`, `next_step`. Call again with the same arguments; nothing restarts.

### Success
- `status`: `succeeded`
- `scene`: `item_id`, `datetime`, `cloud_cover`
- `tile`: `bbox_wgs84`, `tiles`, `km`, `cloud_fraction` (tile-weighted over the area), `crs`
- `outputs.LULC.stats.classes`: class shares over the stitched area
- `input.observed_ndvi.mean`: tile-weighted mean of the jobs' observed NDVI (from the bands, not generated)
- `class_shares`: one sentence per land-cover class ("Trees: 89.9% of the area"), printed as the legend prints them, to quote
- `jobs`: job id, seed and tiles per block (provenance)
- `summary`: one sentence to quote
- Images: stitched true colour and stitched land cover (shown to the user by the runtime)

### Failure
- `error`: area larger than what runs right now, scene does not cover the area, or a job failed. Report it as is.

## Validation / business rules inside the tool
- Blocks are always 2 x 2 tiles. While the GPU tier sleeps an area is at most 16 tiles (4 jobs, about 3 minutes on the CPU tier); with a GPU at most 81 tiles (about 20 km, 25 jobs batched together on the GPU).
- Every block is checked to land exactly on the service grid: no gaps, no overlaps.
- Stateless and idempotent: the service caches identical requests, so repeated calls re-attach to the same jobs.
