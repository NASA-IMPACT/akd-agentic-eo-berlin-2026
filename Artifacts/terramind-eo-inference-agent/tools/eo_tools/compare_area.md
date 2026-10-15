# Tool: eo_tools.compare_area

## Purpose
Compare the stitched TerraMind area with independent references and return error metrics, verdict hints and ready-made summary sentences.

## When it should be used
- After `run_area` reported `succeeded`, with the same `item_id` and `aoi`; before any statement about whether a product is fit for use.

## Inputs (schema)
- `item_id` (string), `aoi` (bbox): the same values passed to `run_area`.
- `include_image` (bool, default true): attach the generated-versus-reference panels.

## Outputs (schema)
- `area`: item id, tiles, bbox, job ids
- `products`: LULC (pixel accuracy, class IoU, confusions, water versus radar with `agrees`, snow versus the snow index), S1GRD (VV/VH bias, MAE, RMSE, r), DEM (bias, MAE, RMSE, r), each with a `verdict_hint`
- `references`: dataset, item id and date per product
- `notes`, `summary` (sentences to quote verbatim); `notes` adds a flat-terrain note when the reference elevation varies by less than 30 m
- `caveats`: a dated sentence when generated water does not agree with the radar
- `table`: the report's 3-row trust table (product | verdict | why), ready to copy

## Validation / business rules inside the tool
- References: ESRI 10 m Annual Land Cover, Copernicus DEM GLO-30, nearest Sentinel-1 RTC pass (within 12 days). An area that straddles several reference tiles or frames is read from all of them.
- Same metrics and thresholds as `compare_maps`; the agent never sets its own thresholds.
- Land cover is "fit for water detection" when generated water agrees with the radar, and "fit for snow detection" when 60% of generated snow/ice is snow by the snow index of the same Sentinel-2 image (NDSI above 0.4): the annual map cannot show either. The summary says whether the water agrees with the radar.

## Failures / retry hints
- "still running": call `run_area` until it succeeds, then `compare_area` again.
