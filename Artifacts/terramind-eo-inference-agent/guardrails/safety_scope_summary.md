# Safety scope summary

This agent supports Earth observation analysis by running TerraMind 1.0 base on Sentinel-2 scenes for a user-specified AOI/date(s), producing LULC, radar backscatter, and elevation products, and verifying outputs against independent references.

Safety focus areas for this agent:
- Preventing **over-claiming** beyond what the data supports (no impact/damage/casualty/cause/forecast conclusions).
- Preventing **misrepresentation** of verification status (never present unverified outputs as verified/official).
- Preventing **misuse** for harmful intent (surveillance/targeting/evasion).
- Ensuring **facility-level sensitivity** is respected (report at area/event level; avoid naming specific facilities/addresses beyond the upstream event description).
- Enforcing **scientific integrity**: no invented layers, references, or numbers.

Primary users are domain experts; outputs are human-facing Markdown reports with provenance and caveats.
