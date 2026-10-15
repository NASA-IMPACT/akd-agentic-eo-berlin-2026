# TerraMind model artifacts (Hugging Face) + TerraTorch

## Summary
Model weights and runtime library/toolkit used to run TerraMind inside the hosted service.

## Tool / API inventory
- **TerraMind 1.0 weights (Hugging Face, `ibm-esa-geospatial`)**
  - **Purpose:** Provide TerraMind model checkpoints/weights
  - **Auth model:** Public
  - **Runtime access:** Pre-baked into the hosted service’s container image (nothing is fetched at runtime)

- **TerraTorch**
  - **Owner:** IBM
  - **Purpose:** Toolkit for loading/running TerraMind (and related workflows)
  - **Access method:** Python library/package (inside the service environment)

## Input data requirements (as used)
- **Source imagery:** Sentinel-2 L2A
- **Bands:** 12 bands in this order:
  1. B01
  2. B02
  3. B03
  4. B04
  5. B05
  6. B06
  7. B07
  8. B08
  9. B8A
  10. B09
  11. B11
  12. B12
- **Values:** raw reflectance values; the scene’s offset handling is performed by the hosted service.

## Known error patterns / failure modes
- Wrong band order or scaling leading to incorrect outputs.
- Dependency/version mismatches in Python environment.
