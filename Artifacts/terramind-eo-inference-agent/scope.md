# Scope

## Purpose
- Enable Earth observation scientists to run the TerraMind foundation model for a user-specified area of interest (AOI) and date range.
- Produce derived geospatial layers from Sentinel-2 imagery, including:
  - Land cover
  - Radar backscatter
  - Elevation
- Verify each generated layer against an independent reference dataset.
- Provide results with evidence and provenance for each layer (i.e., what was generated, how it was generated, and what it was verified against).

## Primary users (roles only)
- Earth observation scientists
- Remote sensing analysts
- Disaster response analysts

## User expertise level
- Domain experts in Earth observation and remote sensing.
- Understand satellite data, land cover classes, and radar backscatter.
- Not expected to know how to run a foundation model or how to validate one.

## Tasks users expect the agent to support
1. Resolve a named place to an area of interest (AOI).
2. Find a suitable Sentinel-2 scene for that AOI and date.
3. Run TerraMind to generate land cover, radar backscatter, and elevation layers for the scene.
4. Verify each generated layer against an independent reference dataset.
5. Compare two dates of the same area to detect change (e.g., flooding, vegetation loss from fire/clearing, crop cycles, urban growth).
6. Report results with metrics, images, and full provenance.

## Current workflow (step-by-step)
1. Decide AOI and date (or two dates for change study); look up the bounding box.
2. Search a Sentinel-2 catalogue for scenes over the AOI in the date range; pick the clearest scene.
3. Download the scene; clip to AOI; prepare bands in the format TerraMind expects.
4. Run TerraMind to generate land cover, radar backscatter, and elevation; wait for completion.
5. Fetch reference datasets for the same AOI:
   - Annual land cover map
   - Digital elevation model (DEM)
   - Nearest real Sentinel-1 pass (for radar backscatter comparison)
6. Align generated layers with references; compute comparison metrics:
   - Land cover: pixel accuracy and class agreement
   - Elevation & backscatter: bias and correlation
7. For change studies: repeat steps 2–6 for the second date; compare the two results.
8. Write up findings including scene IDs, job details, reference datasets, and metrics.

## Pain points / bottlenecks
1. Model setup is heavy (GPU, weights, correct band order/scaling); many scientists never get past setup.
2. Reference data is spread across different catalogues with different projections/resolutions; alignment is slow and error-prone.
3. Verification is usually skipped; outputs are used because they look plausible rather than being checked.
   - Generated vs measured values can get mixed up (e.g., generated NDVI/elevation mistaken for observation).
4. Change studies roughly double the work and require two matching scenes; finding cloud-free pairs can be difficult.
5. Provenance is often lost (scene/run/reference/settings not captured), reducing reproducibility.

## Human-controlled decisions
1. AOI and dates: the agent asks; it does not guess.
2. Scene selection when multiple scenes are available and the choice is not obvious from cloud cover alone.
3. Fitness-for-purpose judgment: whether a generated product is good enough for the user’s needs (agent reports comparisons; user decides use).
4. Interpretive conclusions beyond the data (e.g., flood impact, damage, risk).
5. Whether to spend/trigger a long generation run (jobs take minutes on a shared endpoint).

## Definition of success
1. Users obtain land cover, radar backscatter, and elevation layers for their AOI/date without needing to handle GPU setup, catalog search, or data formatting.
2. Every layer includes an explicit comparison against an independent reference so users can judge performance on the specific scene.
3. For two-date analyses, change is shown with supporting quantitative metrics and an independent check from the observed imagery.
4. Full traceability: every number in the report links back to a tool result, and scene IDs, job details, settings, and reference datasets are recorded so another scientist can reproduce the run.
5. The agent is transparent about limitations (e.g., no cloud-free scene found) rather than filling gaps.
