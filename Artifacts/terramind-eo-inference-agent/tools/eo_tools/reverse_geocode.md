# Tool: eo_tools.reverse_geocode

## Purpose
Convert a coordinate point into a human-readable place label for reporting and user confirmation.

## When it should be used
- When the system needs to label an AOI (e.g., the centre point of the AOI window) in outputs/reports.

## Inputs (schema)
- `lat` (number)
- `lon` (number)

## Outputs (schema)
### Success
- `display_name` (string)
- `country` (string | null)
- `state` (string | null)
- `county` (string | null)
- `town` (string | null)

### Failure
- `error` (string): human-readable error message (returned as a normal response, not an exception).

## Validation / business rules inside the tool
- Return exactly one best match (no candidates list).

## Failures / retry hints
- On failure, return `error` (e.g., invalid coordinates or no result).

## Notes (tool vs context boundary)
- This tool is for labeling; it does not decide the AOI.
