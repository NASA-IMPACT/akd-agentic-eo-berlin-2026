# Tool: eo_tools.search_gdacs_events

## Purpose
Search current and recent GDACS disaster events to support AOI selection from an event description.

## When it should be used
- When the user asks about a current/recent disaster event using natural descriptors (hazard type + country/region), and the agent needs candidate events and their locations.

## Inputs (schema)
All inputs are optional filters:
- `eventlist` (string): hazard type code (examples: `FL` flood, `WF` wildfire, `TC` cyclone, `EQ` earthquake, `DR` drought)
- `alertlevel` (string): one of `green`, `orange`, `red`
- `country` (string): full English country name (as expected by GDACS)

## Outputs (schema)
### Success
- `events` (array; may be empty)
  - each event:
    - `event_id`
    - `hazard_type`
    - `name`
    - `alert_level`
    - `country`
    - `start_date`
    - `centre`: `[lon, lat]`
    - `bbox`: `[west, south, east, north]`

### Failure
- `error` (string): returned only when the GDACS service is unreachable.

## Validation / business rules inside the tool
- Validate `eventlist` is one of the supported hazard codes; if invalid, return `error` listing allowed values (do not ignore silently).
- Validate `alertlevel` is one of `green`/`orange`/`red`; if invalid, return `error` listing allowed values (do not ignore silently).
- Pass `country` through unchanged. Unknown/unrecognized country names return `events: []` (not an error).

## Failures / retry hints
- No matches should return `events: []` (not an error).

## Notes (tool vs context boundary)
- The tool returns candidate events and locations; the agent/user selects which event to use.
- The agent may use `bbox` directly as an AOI, or derive a standardized window around `centre`.
