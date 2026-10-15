# Reading TerraMind outputs (practical interpretation)

## What this covers
How users interpret a completed TerraMind `get_generation` result (JSON + preview PNGs + GeoTIFF COGs).

## How it is used (SME practice)
### Fields looked at first
- **Tile cloud fraction**: `tile.cloud_fraction` (0 to 1)
  - **> 0.2** counts as **high** (results are suspect)
  - **> 0.5** means the run **should not be used**
- Scene identifier (`scene.item_id`) and acquisition time (`scene.datetime`)
- Land-cover class shares (from land-cover output stats)
- Observed NDVI (from `input.observed_ndvi`)

### What previews vs GeoTIFFs are used for
- Preview PNGs: quick sanity check / visual inspection.
- GeoTIFFs (COGs): used when the user needs the full map/layer for analysis.

### Typically ignored
- Timings
- Generated NDVI

## What makes a run suspect
- Tile is cloudy (`tile.cloud_fraction` > 0.2)
- Land-cover class shares contradict observed NDVI
- Re-running the same area yields noticeably different elevation

## Authority
- **Advisory** (guidance / sanity checks).

## Discovery triggers (when to look this up)
- When a generation completes, before describing/interpreting results.

## Usability gate
- Nothing is considered usable until it is compared against an independent reference dataset.
- If `tile.cloud_fraction` > 0.5, the run should not be used.

## Open questions (TBD)
- What magnitude of elevation difference across runs is considered concerning.
