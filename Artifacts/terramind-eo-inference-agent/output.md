# Output format

## Audience / consumers
- Single consumer: human reader.
- No downstream system consumption requirements.

## Overall style
- Hybrid, Markdown.
- Include:
  - Short narrative finding
  - Confidence language: say what the data are consistent with ("consistent with", "suggests", "indicates"); never "confirms", "proves", "clearly", "definitely", and no severity words
  - Plain-language interpretation of the results (what changed, what it means), built from tool-supplied facts
  - Verdict table ("Can you trust it?")
  - A short list of the checks the design required ("How this was checked")
  - Provenance list
  - Caveats line under the verdict table (bullets only when a trigger applies, otherwise 'none')
  - A plain-language interpretation of the images for non-specialists
  - Images returned/attached by tools displayed alongside
- No JSON output required.

## Provenance & citation requirements (must include)
- AOI used (bbox)
- For each run:
  - Sentinel-2 scene `item_id`
  - Sentinel-2 scene acquisition date/time
  - TerraMind service `job_id`
  - `seed`
  - number of diffusion steps (`timesteps`)
- References used (per product):
  - dataset name
  - reference item identifier
  - reference date
- Model statement: “TerraMind 1.0 base” (stated once per report)

## Explicitly excluded
- No tool names.
- No URLs in the report (images are displayed inline, not linked).

## Uncertainty / missing info handling
- Caveats sit under the verdict table as `**Caveats:**` bullets, one per gap, only when a trigger applies (tile cloud fraction above 0.1 on a used scene; a product not verified; generated water disagreeing with radar; operational framing). Otherwise `**Caveats:** none`.
- If a product lacks a reference comparison, mark it **“not verified”** and do not issue a verdict.
- If generation fails, end the report with the error message.
- No best-effort guesses.

## Verdict table
- Format: Markdown table.
- Rows (3): land cover, radar, elevation.
- Columns:
  - `product`
  - `verdict`
  - `why`
- Allowed verdict values (from tool output; agent must not change):
  - `fit`
  - `fit with caveat`
  - `not fit`
  - `fit for water detection`
  - `fit for snow detection`
  - `not verified`
- No metrics in the table; metrics belong in detailed sections later in the report.

## Required report structure (Markdown headings + ordering)
1. `## Finding` — change study: the `finding` of `compare_dates` word for word (it carries the Yes / No / Cannot tell answer, decided by the tool's fixed rules), then its `limits` and the observed NDVI sentence from its `checks`. A date not verified: Cannot tell. Single date: two or three sentences from `run_area` `class_shares` and the `compare_area` summary.
2. `## Before and after` — the heading alone (the Studio places the images under it); the agent writes no image syntax, file names, links or placeholders anywhere.
3. `## What changed` — the `changes` and `checks` of `compare_dates` as bullets, word for word (single date: the `class_shares` of `run_area`). The agent cannot see the images, so it never describes them.
4. `## What it means` — three to six sentences built only from the `facts` of `compare_dates` (single date: the `notes` of `compare_area`). No new claim, cause or number.
5. `## Can you trust it?` — the 3-row verdict table (product | verdict | why: the tool's verdict and reason with its key number, no added cause; verdicts include fit for water detection and fit for snow detection), then the `**Caveats:**` line (the `limits` of `compare_dates` and the other triggers; otherwise `none`).
6. `## How this was checked` — one line each: the `pick_scene` summaries, the `compare_area` summary sentences per date, the reference datasets (radar: generated GRD-like backscatter versus a terrain-corrected Sentinel-1 RTC pass), the reverse-geocoded place name.
- Window rule: percentages and areas describe the analysed window only; its size (tiles, km) is stated once in the Finding; never "x% of <place>".
7. `## Reproduce this run` — provenance per run (AOI bbox and area size; scene item_id + datetime; job ids with seeds from run_area; timesteps; references with dataset name + item id + date), per-product metrics bullets with the tool's summary sentence, and "TerraMind 1.0 base" once.
