# Earth Search STAC API (Element 84)

## Summary
STAC API used as the only catalog for discovery of Sentinel-2 L2A scenes and Sentinel-1 GRD scenes.

## Tool / API inventory
- **Name:** Earth Search STAC API
- **Owner:** Element 84
- **Purpose:** Search/discovery for scenes and datasets via STAC
- **When currently used:**
  - Sentinel-2: find a suitable L2A scene for an AOI/date; filter by cloud cover
  - Sentinel-1: discover GRD scenes for nearest-date radar reference

## Access
- **Access method:** STAC API over HTTP
- **Auth model:** No auth
- **Endpoint:** https://earth-search.aws.element84.com/v1
- **Catalog role:** Primary and only catalog (no fallback catalogs).

## Inputs / outputs
- **Collections used:**
  - `sentinel-2-c1-l2a` (primary)
  - `sentinel-2-l2a` (older dates)
  - `sentinel-1-grd` (for radar reference)
- **Search filters used:**
  - `bbox`
  - `datetime` range
  - `eo:cloud_cover` <= max cloud-cover threshold
- **Default quality threshold:**
  - Default max cloud cover: **20%**
  - If no results are found: raise to **40%**
- **Coverage / validity rules:**
  - The AOI must be **fully contained** in the selected scene footprint.
  - The AOI must sit inside a **single Sentinel-2 tile** (if it crosses a tile border the TerraMind service rejects it); if a candidate scene would cause tile-border crossing, the agent chooses a different scene for the same date.
- **Selection rule:** choose the clearest scene that fully covers the AOI.
- **Pagination:** request first page only, `limit=20`.
- **Outputs:** STAC Items (scene metadata + asset URLs).

## Permissions, limits, operational constraints
- Public endpoint.

## Known error patterns / failure modes
- Scene search can return no results for a narrow date window; users may need to widen the window.
- No low-cloud scenes available in a date window.
- Large AOIs may require pagination handling (beyond the first page).
