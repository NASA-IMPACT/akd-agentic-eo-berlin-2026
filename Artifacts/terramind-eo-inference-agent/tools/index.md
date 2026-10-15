# Tools index

This directory specifies the runtime tools the agent can call (contracts, validations, outputs, and failure patterns).

## Tool inventory (grouped by deployed server)

### `terramind/` (hosted TerraMind service)
- `terramind/generate.md` — start TerraMind generation job
- `terramind/get_generation.md` — poll TerraMind generation job and fetch results

### `eo_tools/` (general EO helper tools)
- `eo_tools/geocode.md` — place → AOI
- `eo_tools/pick_scene.md` — date → nearest Sentinel-2 scene that is clear over the AOI window (replaces hand-made scene searches)
- `eo_tools/reverse_geocode.md` — coordinates → place label
- `eo_tools/run_area.md` — run TerraMind over the whole area as parallel jobs and stitch them (up to about 20 x 20 km)
- `eo_tools/compare_area.md` — compare the stitched area against independent references
- `eo_tools/compare_maps.md` — compare a single TerraMind job against independent references (used inside compare_area)
- `eo_tools/search_gdacs_events.md` — find current disaster events (GDACS) for AOI selection

## Legacy paths (deprecated)
Earlier drafts used flat per-tool folders (e.g., `tools/geocode/contract.md`). Those stubs are deprecated and are not part of the consolidated tool inventory.

## Explicit non-tools (agent-owned)
- Asking the user for missing AOI/dates (no guessing)
- Interpreting results and writing the narrative report
- Any claims beyond the data (impact/damage/risk)
