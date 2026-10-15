# Tool: eo_tools.geocode

## Purpose
Resolve a user-provided place description to a geographic bounding box that downstream tools can use as an AOI.

## When it should be used
- When the user provides a place name/description instead of an explicit AOI.
- When the workflow needs to confirm/standardize an AOI for subsequent scene search or generation.

## Inputs (schema)
- `query` (string): place name or description.

## Outputs (schema)
### Unambiguous match
- `display_name` (string)
- `centre` ([lon, lat])
- `bbox` ([west, south, east, north])
- `window_4km` ([west, south, east, north]): a 4 km × 4 km bbox around `centre` (2 × 2 tiles, always accepted by the service).
- `window_8km` ([west, south, east, north]): an 8 km × 8 km bbox around `centre` (4 × 4 tiles, the service's 16-tile limit; needs its GPU tier). The default AOI for `pick_scene`, which shrinks it when the service cannot take 16 tiles.

### Ambiguous match
- `candidates` (array, max 3), each with:
  - `display_name`
  - `centre`
  - `bbox`
  - `window_4km`
  - `window_8km`
- `message` (string): asks the user to pick a candidate.

### No match
- `error` (string): human-readable error message (returned as a normal response, not an exception).

## Validation / business rules inside the tool
- Internally request English names (no user-controlled locale inputs).
- Enforce `candidates` length ≤ 3.
- Compute `window_4km` and `window_8km` deterministically from `centre`.

## Failures / retry hints
- If no match, return `error` describing that nothing matched and prompt for a more specific query.

## Notes (tool vs context boundary)
- The tool returns candidate AOIs; choosing among ambiguous candidates remains a user decision.
- The tool does not infer AOI when the user provides no location; the agent asks.
