# Disaster context sources (GDACS)

## Summary
Optional external source for *current event* context. Used only when the user explicitly asks about a current disaster event.

## Tool / API inventory
- **GDACS**
  - **Owner:** GDACS
  - **Purpose:** Current disaster events feed; supports selecting AOI from a current event
  - **Role in workflow:** Optional; user-driven entrypoint for AOI selection when asking about an ongoing event

## Interface
- Exposed to the agent as a tool: `search_gdacs_events`

## Inputs / outputs (as used)
- **Input:** hazard type, alert level, country
- **Output:** list of matching events, including coordinates

## Not used
- ESA EO Dashboard is not used in this workflow.
