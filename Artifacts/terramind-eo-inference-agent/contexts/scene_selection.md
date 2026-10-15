# Scene selection criteria (Sentinel-2)

## What this covers
How users choose a Sentinel-2 scene from search results in practice.

## How it is used (SME practice)
- From each STAC item, users look at:
  - Acquisition datetime
  - Scene-level cloud cover (`eo:cloud_cover`)
  - Scene footprint coverage (must fully contain the AOI)

## Acceptance criteria
- Choose the scene **nearest the date of interest** that is **clear over the AOI window** and **fully covers** it.
- Cloud is judged over the window from the scene classification layer, not from scene-level `eo:cloud_cover` (a 30% scene can be clear over a 4 km window, and a 8% scene can be cloudy over it).
- Accept up to 20% cloud over the window before looking further from the date; never use a scene above 50%.
- `pick_scene` applies all of this: it searches outwards from the date (2, 5, 10, 21, 45, 90 days up to the cap), drops scenes that only partly cover the window, measures cloud over the window and returns the nearest clear scene with the scenes it rejected.

## Rejection criteria / common pitfalls
- Reject scenes that only partially cover the AOI (scene edge or tile border); the service refuses them.
- Reject scenes where clouds sit over the AOI even if scene-level cloud cover looks acceptable.
- Sorting a search by scene-level cloud cover picks the clearest scene of the year, far from the event; sort by distance from the date instead.

## Change-study specifics
- Need one scene on each side of the event (two dates): the latest clear scene before the event started, the earliest clear scene from the day it ended on.
- For events that last days (fires, slow floods) use the start date for "before" and the end date for "after"; a "before" scene taken during the event (smoke, active fire, rising water) is not a baseline.
- The tool widens the window in steps up to the caps (before: 90 days, after: 21 days); beyond them the date is not verified.

## Authority
- **Authoritative** (must follow).

## Discovery triggers (when to look this up)
- When starting a scene search.
- When a scene search returns no results.
- When the service rejects a scene (e.g., coverage/AOI constraints).

## Not used
- No other STAC quality flags are used for selection.
- Processing baseline is not used as a selection criterion; reflectance offset handling is assumed to be handled by the service.
