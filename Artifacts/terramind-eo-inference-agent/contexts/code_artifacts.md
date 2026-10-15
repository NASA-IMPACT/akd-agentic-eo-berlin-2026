# Existing code artifacts (repos, scripts, notebooks)

## Summary
Code artifacts currently used around TerraMind runs, evaluation, and result viewing.

## Inventory
- **TerraMind test script (workshop folder)**
  - **Purpose:** Run TerraMind on sample tiles and compare output with ground truth
  - **Where used:** Local/workshop environment
  - **Outputs produced:** GeoTIFFs, comparison PNG, JSON report of metrics and timings
  - **Ground truth used:** TerraMesh sample tiles that ship with IBM’s TerraMind repository

- **TerraMind service repository**
  - **Purpose:** Back-end for hosted TerraMind inference service + result artifacts
  - **Outputs produced per job:** GeoTIFFs, PNG previews, JSON statistics
  - **UI:** small Streamlit map UI for viewing results
  - **Location:** GitHub `NASA-IMPACT/terramind-service` (private)

## Not present / manual today
- No existing dedicated code for reference-data alignment or final report writing.
- Reference alignment and write-ups are currently done manually in notebooks.
