# Tool group: eo_tools

General EO helper tools used for AOI selection/labeling and quality checks.

- `geocode.md` — place → AOI
- `pick_scene.md` — date → nearest Sentinel-2 scene that is clear over the AOI window (replaces hand-made scene searches)
- `reverse_geocode.md` — coordinates → place label
- `run_area.md` — run TerraMind over the whole area as parallel jobs and stitch them
- `compare_area.md` — compare the stitched area against independent references
- `compare_dates.md` — change between the two dates, checked against observations; the answer, finding and facts to quote
- `compare_maps.md` — compare a single TerraMind job against independent references
- `search_gdacs_events.md` — find current disaster events (GDACS) for AOI selection
