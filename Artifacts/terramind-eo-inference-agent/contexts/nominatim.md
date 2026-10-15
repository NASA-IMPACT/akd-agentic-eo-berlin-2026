# OpenStreetMap Nominatim (geocoding)

## Summary
Service used for place-name geocoding and reverse geocoding to support AOI definition.

## Tool / API inventory
- **Name:** OpenStreetMap Nominatim
- **Owner:** OpenStreetMap community / Nominatim operators
- **Purpose:** Forward geocoding (place → coordinates) and reverse geocoding (coordinates → place)
- **When currently used:** AOI lookup from named place (only geocoder used in the workflow)

## Access
- **Access method:** HTTP API
- **Endpoint:** https://nominatim.openstreetmap.org
- **Auth model:** None (public), subject to usage policy
- **Rate limits / quotas:** ~1 request/second

## Operations
- `search` (forward geocoding)
- `reverse` (reverse geocoding)

## Inputs / outputs
- **Inputs:** query string (place name) or coordinates; English names requested.
- **Outputs used by the workflow:**
  - A bounding box (as provided by Nominatim)
  - A derived **4 km × 4 km** window centered on the returned point; downstream steps use this window as the AOI.

## Known constraints / failure modes
- Rate-limited; may return ambiguous results for common place names.
- Coverage/quality varies by region.

## Fallback behavior
- If Nominatim fails to resolve an AOI, the agent asks the user for coordinates.
