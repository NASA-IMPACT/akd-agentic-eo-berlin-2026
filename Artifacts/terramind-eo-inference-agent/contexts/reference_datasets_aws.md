# Reference datasets on AWS Open Data

## Summary
Primary source of independent reference datasets used for verification.

## Dataset / knowledge source inventory

- **Impact Observatory 10 m Annual Land Cover (annual)**
  - **Owner:** Impact Observatory
  - **Purpose:** Reference land cover for verification
  - **Location/access:** AWS Open Data S3 bucket `io-10m-annual-lulc`
  - **Structure:** one GeoTIFF per UTM zone and year
  - **Temporal matching:** match to the Sentinel-2 scene’s year

- **Copernicus DEM GLO-30 (30 m)**
  - **Owner:** Copernicus
  - **Purpose:** Reference elevation (DEM)
  - **Location/access:** AWS Open Data S3 bucket `copernicus-dem-30m`
  - **Structure:** one tile per 1-degree cell
  - **Temporal matching:** static

- **Sentinel-1 GRD (for radar reference)**
  - **Owner:** ESA/Copernicus
  - **Purpose:** Reference radar backscatter comparison
  - **Discovery:** Earth Search STAC collection `sentinel-1-grd`
  - **Assets used:** `vv` and `vh`
  - **Location/access:** S3 bucket `sentinel-s1-l1c` (**requester-pays**)
  - **Access note:** Read using the TerraMind service’s own AWS credentials.
  - **Temporal matching:** nearest Sentinel-1 acquisition date to the Sentinel-2 scene date

## Permissions, limits, and operational constraints
- Land cover and DEM buckets are free to read.
- Sentinel-1 GRD bucket is requester-pays.

## Alignment / resampling policy
- Every reference dataset is reprojected onto the generated tile’s grid.
- **Land cover:** nearest-neighbor resampling.
- **Elevation and radar:** bilinear resampling.

## Known error patterns / failure modes
- CRS/resolution mismatches requiring careful reprojection/resampling.
- Temporal mismatch (e.g., annual land cover vs specific scene date; nearest Sentinel-1 acquisition).
- Land cover reference is annual and cannot reflect transient events (e.g., floods) for validation.
- Large data volumes and slow reads for big AOIs.
