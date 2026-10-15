# Raster alignment + metrics computation libraries (Python)

## Summary
Local Python libraries used for raster alignment and computing verification metrics.

## Tool inventory
- **Name:** rasterio
  - **Purpose:** Read/write/warp/align raster data
  - **Access method:** Python package

- **Name:** numpy
  - **Purpose:** Numerical computing for metric calculations
  - **Access method:** Python package

## Metrics mentioned
- Land cover: accuracy, IoU, class agreement
- Elevation & backscatter: bias, MAE, RMSE, correlation

## Operational constraints / failure modes
- CRS/resolution alignment complexity and potential for subtle misalignment bugs.
- Memory constraints when processing large rasters.
