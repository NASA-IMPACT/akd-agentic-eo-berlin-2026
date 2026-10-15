# Contexts index

This directory contains context notes used to ground the agent in the operational environment (systems, datasets, and SME practices).

## Files
- `earth_search_stac.md` — How Earth Search STAC is used for Sentinel-2/1 discovery (collections, filters, pagination).
- `scene_selection.md` — Practical scene acceptance/rejection criteria (date, cloud cover, AOI coverage).
- `terramind_output_reading.md` — How users interpret TerraMind job outputs (what to check, what to ignore, what looks suspect).
- `nominatim.md` — Nominatim geocoding usage and constraints (rate limits, ambiguity).
- `terramind_inference_service.md` — Hosted TerraMind service interface (tools, async jobs, fields, outputs).
- `terramind_model_artifacts.md` — TerraMind weights on Hugging Face + TerraTorch toolkit notes.
- `reference_datasets_aws.md` — AWS Open Data reference datasets and temporal matching rules.
- `reference_checking.md` — How generated layers are aligned to references and compared (metrics + flood-specific check).
- `metrics_reporting_libs.md` — Metrics computed and libraries used today.
- `code_artifacts.md` — Existing workshop script and service repo + outputs.
- `disaster_context_sources.md` — GDACS usage (in scope) and EO Dashboard status (not used).
