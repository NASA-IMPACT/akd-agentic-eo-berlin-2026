# Tool: eo_tools.compare_dates

## Purpose
Say what changed between the before and after runs of the same area, check that change against what was observed, and decide the answer by fixed rules. Returns the finding sentence, the per-class changes, the independent checks, the limits and the facts that explain them, all ready to quote.

## When it should be used
- Change studies only, once, after `run_area` succeeded for both dates and `compare_area` ran for both. Not when a date is not verified.

## Inputs (schema)
- `before_item_id`, `after_item_id` (string): the item ids `pick_scene` returned for the two dates.
- `aoi` (bbox): the `aoi` from `pick_scene` (the same for both dates).
- `event` (string): "flood", "fire" (also a burn scar or wildfire), "snow" or "other", from the user's words.

## Outputs (schema)
- `answer`: Yes / No / Cannot tell (null for "other")
- `finding`: the answer sentence, to quote word for word
- `changes`: one sentence per land-cover class that changed by 1 point or more
- `checks`: the observed NDVI and the independent check for the event
- `limits`: what the generated maps miss
- `caveats`: every caveat the report must carry (the limits, a sentence when the water does not agree with the radar, cloud over 10% of the area), word for word
- `facts`: correct explanations for this case; the only explanations the report may use
- `classes`, `metrics`: the numbers behind the sentences

## Validation / business rules inside the tool
- Shares are printed as `run_area` and the runtime legend print them; a change is the difference of the printed shares.
- Flood: water must rise by 1 point or more, and 60% of the generated water must be dark (VV below -15 dB) in the Sentinel-1 pass nearest the after scene, or the water must be 4 dB darker than the rest. It also reports how much of the area that turned dark in the radar between the two passes TerraMind labels as water.
- Fire: trees must fall by 2 points or more, 50% of the area TerraMind moved out of trees must be burnt by the burn index (dNBR of 0.1 or more, computed from the observed bands B08 and B12), and observed NDVI must fall.
- Snow: snow/ice must rise by 2 points or more, and 60% of it must be snow by the snow index (NDSI above 0.4 with near-infrared reflectance above 0.11, from the observed bands B03, B08 and B11).
- Otherwise: No when the generated layer shows no such change; Cannot tell when it does but the independent check does not back it.

## Failures / retry hints
- "still running": call `run_area` for both dates until each succeeds, then `compare_dates` again.
