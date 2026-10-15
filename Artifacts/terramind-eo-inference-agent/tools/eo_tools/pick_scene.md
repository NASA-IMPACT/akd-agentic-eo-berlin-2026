# Tool: eo_tools.pick_scene

## Purpose
Choose the Sentinel-2 scene nearest a date that is clear over the AOI window and fully covers it, ready to pass to `eo_tools.run_area`.

## When it should be used
- Once per date, after the AOI window is known (step 2) and before `run_area`.
- Change study: once with `side` "before" (event start date) and once with `side` "after" (event end date; the same date when only one is given). Single date: `side` "nearest".

## Inputs (schema)
- `aoi` (bbox `[w,s,e,n]`, a `[lon, lat]` point, or GeoJSON geometry): the AOI window, e.g. `window_8km` from `geocode` or a GDACS event `centre`.
- `date` (string, ISO date, e.g. `2023-05-17`): the date of interest (event date for a change study).
- `side` (string): `before`, `after` or `nearest` (default `nearest`).
- `max_days` (integer, optional): how far from the date to look. Defaults: before 90, after 21, nearest 30.
- `max_cloud_fraction` (number, optional, default 0.2): cloud over the window accepted without looking further from the date.

## Outputs (schema)
### Success
- `item_id` (string), `datetime` (string), `days_from_date` (integer, negative = before)
- `usable` (bool): false when every scene in the window is more than 50% cloudy over the area; the clearest is returned anyway so the user can see it, with a NOT VERIFIED warning
- `scene_cloud_cover_pct` (number): scene-level figure, for information only
- `window` (object): `cloud_fraction`, `nodata_fraction` (over the window, from the scene classification layer), `tiles`, `km` ([x, y]), `bbox_wgs84`
- `aoi` (bbox): pass this to `run_area` exactly; it is the input AOI, or a smaller centred box when the area is larger than what runs right now (16 tiles while the GPU tier sleeps, 81 with a GPU)
- `nearer_rejected` (array): scenes closer to the date that were too cloudy over the window (`item_id`, `datetime`, `window_cloud_fraction`)
- `searched` (object): `side`, `max_days`, `scenes_checked`, `not_covering`, `tiles_allowed_now`, `why`
- `note` (string | null): set when the area was reduced to what runs right now; carry it into the report's caveats
- `warning` (string | null): set when the chosen scene has more than `max_cloud_fraction` cloud over the window
- `summary` (string): one sentence to quote in the report

### Failure
- `error` (string): no scene within `max_days` covers the window at all, with `checked`. The date is then `not verified`.
- `error` (string): the AOI needs more than 81 tiles (about 20 x 20 km), the most `run_area` can stitch. The tool never shrinks such an area to its centre: ask the user which sub-area matters, geocode it, and call again.

## Validation / business rules inside the tool
- Searches outwards from the date in steps (2, 5, 10, 21, 45, 90 days) up to `max_days`; `before` ends the day before the date, `after` starts on it.
- Drops scenes whose footprint does not fully contain the window the service will cut (same 2.24 km tile grid, centring and snapping as the service).
- Measures cloud and no-data over the window itself; never uses a scene above 2% no-data; a scene above 50% cloud is returned only when nothing clearer exists, marked `usable: false`.
- Reads the service's health endpoint for the tier in force and shrinks an area above what runs right now (16 tiles while the GPU tier sleeps, 81 with a GPU) to its centre, with a `note`; an AOI above 81 tiles is refused (see Failure).

## Failures / retry hints
- `error` means no clear scene within the cap: report the date as not verified; widening `max_days` is a user decision.
- Earth Search unavailable: returned as `error`; retry once later.

## Notes (tool vs context boundary)
- The tool decides which scene; the agent decides nothing about scenes and never searches by hand.
- Scene-level `eo:cloud_cover` is reported but not used for the choice.
