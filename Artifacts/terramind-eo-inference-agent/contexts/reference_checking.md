# Reference checking procedure (alignment + metrics)

## What this covers
How users compare generated layers to independent reference datasets (alignment approach + metrics).

## Alignment approach (SME practice)
- The **generated tile sets the target grid**:
  - CRS
  - 10 m resolution
  - extent
- Each reference raster is reprojected/resampled onto the generated grid:
  - **Land cover:** nearest-neighbor resampling
  - **Elevation:** bilinear resampling
  - **Radar backscatter:** bilinear resampling
- **Radar preprocessing:** convert radar to dB before comparison.
  - **Masking note:** exclude non-positive radar values before the dB conversion.

## Metrics computed
### Land cover
- Evaluation uses the **10-class TerraMesh scheme** (TerraMesh order):
  - 0 no data
  - 1 water
  - 2 trees
  - 3 flooded vegetation
  - 4 crops
  - 5 built area
  - 6 bare ground
  - 7 snow/ice
  - 8 clouds
  - 9 rangeland
- **Impact Observatory 10 m Annual Land Cover → TerraMesh mapping:** one-to-one, using ESRI ids in this same order:
  - `[0, 1, 2, 4, 5, 7, 8, 9, 10, 11]`
- Compute:
  - Pixel accuracy
  - IoU per class
  - Main confusions (confusion matrix highlights)

### Elevation
- Against Copernicus DEM GLO-30:
  - Bias
  - MAE
  - RMSE
  - Correlation

### Radar backscatter
- Against nearest Sentinel-1 GRD acquisition:
  - Bias
  - MAE
  - RMSE
  - Correlation
- Computed **per polarization** (VV and VH).

### NDVI
- Compare generated NDVI to NDVI computed directly from Sentinel-2 bands.
- Use the same metrics: bias, MAE, RMSE, correlation.

## Special case: floods
- Land-cover comparison is only indicative for flood dates because the annual land-cover reference cannot capture transient water.
- Additional check: compare generated water against radar behavior (VV drives this flood check):
  - A radar pixel counts as **dark** when **VV < −15 dB**.
  - Generated water is treated as **corroborated** when either:
    - at least **60%** of generated-water pixels are dark in VV, **or**
    - the mean VV over generated-water pixels is at least **4 dB** below the mean VV over the rest of the tile.

## Masking / nodata handling
- Exclude **nodata** pixels in either layer from metrics.
- Exclude land-cover class **0 (no data)** from land-cover evaluation.
- Exclude non-positive radar values before dB conversion.

## Authority
- **Authoritative** (must follow).

## Discovery triggers (when to look this up)
- After every completed generation.
- Before making any statement about a product’s quality.
