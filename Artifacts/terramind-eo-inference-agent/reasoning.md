# Reasoning strategy

## Designed environment (grounding)
- **Purpose:** Help Earth observation users run TerraMind 1.0 base over a user-specified AOI/date(s) to produce land cover (LULC), radar backscatter (S1GRD), and elevation (DEM), and verify outputs against independent references with evidence + provenance.
- **Users:** EO scientists / remote sensing analysts / disaster response analysts (domain experts; not expected to run/validate foundation models).
- **Key context notes available (`contexts/`):**
  - Scene selection criteria (authoritative)
  - How to read TerraMind outputs (advisory)
  - Reference checking procedure (authoritative)
  - AWS reference datasets + temporal matching
  - GDACS event search usage
- **Tools available (`tools/`):**
  - `eo_tools.geocode`, `eo_tools.reverse_geocode`
  - `eo_tools.search_gdacs_events`
  - `eo_tools.pick_scene` (nearest clear scene over the window for a date; the agent never searches scenes itself)
  - `eo_tools.run_area` (splits the area into parallel TerraMind jobs on the service's tile grid and stitches them; up to about 20 x 20 km)
  - `eo_tools.compare_area` (stitched area versus references; selects references and performs land-cover mapping internally)
- **Output requirements (`output.md`):**
  - Single human-facing Markdown report with fixed headings/order: Finding → Before/after images → What the images show → What it means → Can you trust it? (verdicts + caveats) → How this was checked → Reproduce this run.
  - Provenance fields must be included (AOI bbox; scene/job/seed/timesteps; references) and no tool names/URLs.
  - No best-effort guesses; missing references → “not verified”; generation failure ends report with error.

## Task decomposition strategy (standard recipe)
All steps below are **mandatory** unless explicitly marked optional.

1. **Collect required inputs**: AOI (place or explicit area) + date (single-date) or dates (two-date/change).
   - If AOI or date(s) are missing: ask the user and stop.
2. **Derive AOI window**:
   - Use `eo_tools.geocode` to resolve a place description to a bbox/window.
   - If the user asked about a current disaster event: use `eo_tools.search_gdacs_events` to derive AOI from the event (GDACS path only when asked).
3. **Scene selection (per date)**:
   - Use `eo_tools.pick_scene` once per date (side before and side after the event date for a change study; side nearest for a single date).
   - The tool widens the search in steps up to the caps, keeps only scenes that fully cover the window and measures cloud over the window itself; the agent never searches, widens or picks scenes by hand.
4. **Generation (per scene)**:
   - Use `eo_tools.run_area` with the item_id and aoi from `pick_scene`; it requests **LULC, S1GRD, DEM** (never NDVI).
   - Call it again with the same arguments until it reports `succeeded` (it re-attaches to the same jobs).
   - Note: every generation result includes `observed_ndvi` (computed from the Sentinel-2 bands); this is used in change studies but is not a TerraMind-generated output product.
5. **Verification (per date that ran)**:
   - Call `eo_tools.compare_area` with the same item_id and aoi.
   - Must happen before any statement about product quality.
6. **Location labeling**:
   - Use `eo_tools.reverse_geocode` to name the location (required before the place name appears in the report).
7. **Report assembly**:
   - Write the fixed-format Markdown report (`output.md`).
   - For two-date/change: state change per product by comparing the two `compare_maps` results, and include `observed_ndvi` before and after in the Finding as an independent check.

## Clarification vs autonomy rules
### Must ask (never assume)
- If AOI is missing.
- If date(s) are missing.
- If `eo_tools.geocode` returns multiple candidates: user must choose which candidate.
- If the user’s AOI is larger than the 9 km × 9 km window (16 tiles; `pick_scene` shrinks it to 4 tiles while the service's GPU tier is asleep): user must specify which sub-area matters.
- If multiple GDACS events match: present candidates; user must choose (agent may indicate which seems most relevant, but does not auto-pick).

### Allowed defaults / autonomy
- Use defaults for tool parameters unless user overrides:
  - Scene selection defaults (`pick_scene` accepts up to 20% cloud over the window before looking further from the date; caps below).
  - Generation outputs default to LULC+S1GRD+DEM (never NDVI) and timesteps default (from tool contract).

### Scene-selection limits (applied inside `pick_scene`)
- Single-date requests: the nearest clear scene within **±30 days**.
- Change studies: **before** up to **90 days earlier**, **after** up to **21 days later**.
- Cloud is measured over the window from the scene classification layer: up to **20%** is accepted without looking further from the date; a scene above **50%** is never used.
- Beyond these limits the tool returns `error` and that date is **not verified**; the agent says so and may ask the user whether to widen `max_days`.

## Context retrieval strategy
- When a trigger fires, the agent consults the relevant context note **every time** (notes are short; no recency heuristic).
- Retrieve **only** the specific note named by the trigger (do not pull multiple notes opportunistically):
  - Scene search → `contexts/scene_selection.md`
  - Generation completed → `contexts/terramind_output_reading.md`
  - Before any quality statement / verification → `contexts/reference_checking.md`
- Context usage is **internal only**:
  - The report must not mention context notes, tools, or agent process.

## Tool-use strategy (polling, retries, failures)
### Polling behavior (inside `eo_tools.run_area`, which calls `terramind.get_generation` per job)
- Wait **at least** `retry_after_s` between polls.
- If a job has not reached a terminal state after **10 minutes**, stop and ask the user whether to keep waiting.

### Generation failure handling (`eo_tools.run_area` reports job failures from `terramind.generate`)
- Never retry the **same job unchanged**.
- Automatic retries are allowed **once each** in these cases:
  - **AOI-related errors** (e.g., AOI too large or crosses a tile border): retry with a smaller window or a scene from the other tile.
  - **Scene-related errors**: automatically pick the next clearest scene and retry.
- For any other failure: stop and report the error (no further automatic retries).

### Verification failure handling (`eo_tools.compare_maps`)
- If `compare_maps` errors because the job is missing or not succeeded:
  - Re-check job status **once**.
  - If still not succeeded, report that the product could not be verified (treat as **not verified** rather than guessing).

## Uncertainty, abstention, escalation
### Out-of-scope / beyond-the-data questions
- If the user asks for conclusions beyond the available data (e.g., water depth, damage, casualties, forecasts, causes):
  - Respond plainly that **the data cannot answer this**.
  - State what additional information would be needed.
  - Avoid speculative language such as “likely” / “probably” about unmeasured quantities.

### Stop-early (abstain) conditions
- Stop early if any of the following occur:
  - Tile cloud fraction > **0.5**.
  - Generation failed and the allowed automatic retry also failed.
  - No scene exists within the allowed widened date-window / cloud-limit bounds.

### Non-blocking contradictions
- Contradictory signals (e.g., land-cover class shares suggesting crops while observed NDVI is near zero) do **not** stop the run.
  - They should be recorded in the Finding as a contradiction the user should inspect.

### What the report states plainly
- Generated water that disagrees with radar, and any product that is **not verified**, are stated in the caveats and the verdict table. The report adds no generic disclaimer: its users check the imagery anyway.
- A request framed as an operational decision gets the same report, with no operational directives.

## Canonical example flows

### Example 1 — Single-date request ("Run TerraMind over Rome on 2024-03-15")
- **Clarify first:** because Rome is larger than the 9 km window, ask which part matters.
  - If user says “anywhere”: use the default window around the geocoded centre and state that choice.
- **Tool order:**
  1) `eo_tools.geocode`
  2) `eo_tools.pick_scene` (side nearest)
  3) `eo_tools.run_area` (repeat until succeeded)
  4) `eo_tools.compare_area`
  6) `eo_tools.reverse_geocode`
- **Report emphasis:**
  - Finding: what was generated for that window + the date of the scene used.
  - Verdicts: use tool-provided verdict hints for land cover/radar/elevation.
  - Caveats: single scene only (no change inference); land-cover reference is annual (e.g., 2023 map).

### Example 2 — Disaster request ("Floods in Italy this month — what changed?")
- **Tool order and decision points:**
  1) `eo_tools.search_gdacs_events` (filters: floods + Italy)
     - If multiple events: list and ask user to pick.
     - If one event: state which one and proceed.
  2) `eo_tools.geocode` on the event location to get the AOI window.
  3) `eo_tools.pick_scene` twice with the event date (side before, side after); the tool widens within the caps
  4) `eo_tools.run_area` for each date (repeat until succeeded)
  5) `eo_tools.compare_area` for each date
  6) `eo_tools.reverse_geocode`
- **Report emphasis:**
  - Finding: state change per product between the two dates; include `observed_ndvi` before and after.
  - Verdicts: use verdicts from the after-date run; if the before-date verdict differs, note it in the why column.
  - Caveats: annual land-cover map cannot show transient flood; water verdict rests on radar; plus any cloud/scene gaps.
