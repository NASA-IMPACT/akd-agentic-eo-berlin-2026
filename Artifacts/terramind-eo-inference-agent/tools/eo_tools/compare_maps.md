# Tool: eo_tools.compare_maps

## Purpose
Compare a completed TerraMind generation against independent reference datasets, returning alignment-aware metrics plus minimal human-readable summaries.

## When it should be used
- After a TerraMind generation has completed successfully, before discussing product quality.

## Inputs (schema)
- `job_id` (string): job id of a **succeeded** TerraMind generation.
- `include_image` (boolean, default `true`): whether to attach side-by-side comparison imagery for a human.

## Outputs (schema)
### Success
- `scene`:
  - `item_id` (string)
  - `datetime` (string)

- `products`: object with one entry per generated product present in the job. Expected keys include `LULC`, `DEM`, `S1GRD`, `NDVI`.

  - `LULC`:
    - `pixel_accuracy`
    - `classes`: per-class generated + reference share, with `iou`
    - `top_confusions`
    - `water_vs_radar`:
      - `generated_water_share`
      - `water_share_dark_in_vv`
      - `db_separation`
    - `verdict_hint`

  - `DEM`:
    - `bias`, `mae`, `rmse`, `pearson_r`
    - `generated_stats`: `mean`, `min`, `max`
    - `reference_stats`: `mean`, `min`, `max`
    - `verdict_hint`

  - `S1GRD`:
    - `VV`: `bias`, `mae`, `rmse`, `pearson_r`, `verdict_hint`
    - `VH`: `bias`, `mae`, `rmse`, `pearson_r`, `verdict_hint`

  - `NDVI`:
    - `bias`, `mae`, `rmse`, `pearson_r`
    - `range_compression`
    - `verdict_hint` (includes guidance to prefer the observed/band-computed NDVI)

- `references`: one entry per product with:
  - dataset name
  - reference item id
  - reference date used

- `notes`: **standardized** caveats the agent must repeat (fixed phrasing; e.g., annual land cover cannot show transient water)

- `summary`: one plain sentence per product, generated per run from a fixed sentence pattern including actual numbers/references (intended to be quoted verbatim)

- `image` (optional, when `include_image=true`): side-by-side image comparing generated vs reference (returned/attached for the human).

### Failure
- `error` (string): plain-language message (e.g., job missing, or job not in `succeeded` state).

## Validation / business rules inside the tool
- Must verify the job exists and has `status: succeeded` before attempting comparisons.
- Tool automatically discovers and selects references:
  - land cover: year nearest the scene date
  - DEM: relevant tile(s) for the AOI
  - radar: Sentinel-1 pass nearest the scene date
- Perform land-cover reference → 10-class scheme mapping inside the tool; the agent does not see raw reference classes.

## Failures / retry hints
- If `error` indicates job not succeeded/missing, the agent may need to re-fetch job status or run a new generation.

## Notes (tool vs context boundary)
- Tool returns metrics and constrained summaries; narrative interpretation/report writing remains agent-owned.
- Tool does not return `next_action` fields; sequencing/orchestration is handled outside the tool.
