# Mini CARE, on your own: interview answers

Sign up and open the design first: [`setup.md`](setup.md). In a pair? Use
[`care-process-small-pair-scientist.md`](care-process-small-pair-scientist.md) or [`care-process-small-pair-developer.md`](care-process-small-pair-developer.md).

Every participant gets the same 15 questions, in the same order. Write your own answers, or copy the ones
below. There is no Reconcile step when you work alone: after Stage 4.1 the `agents.md` it builds is yours.

- **It asks you to confirm or continue?** Reply `Yes.`
- **"Your answer is too vague"?** That is CARE pushing back. Add one concrete example.

---

## Create the design

**Designs → New design**, from the workshop template:

| Field | Value |
| --- | --- |
| Name | `Earth Observation FM Inference Agent` |
| Description | `Checks whether a named place flooded between two dates, with TerraMind over Sentinel-2, and reports the evidence.` |
| Model | `DeepSeek-V4.1-Flash (fast, HZDR)`. If it is already selected, leave it. If it errors during the session, switch the design to `DeepSeek-V4.1-Flash (JUWELS)` or `Qwen3.8-Flash-Next`. |

No assignee. Open the interview.

## Start the interview

Send this as the first message:

```
start
```

---

## Stage 1.1: Scope

**1. What is the purpose of the agent that is being designed (e.g., data search)?**
```
The agent helps Earth observation scientists run the TerraMind foundation model over an area and date of interest, producing land cover, radar backscatter and elevation layers from Sentinel-2 imagery, and verifies each generated layer against an independent reference dataset so the results come with evidence and provenance.
```

**2. Who are the primary users of the future agent? (roles only)**
```
Earth observation scientists, remote sensing analysts, and disaster response analysts.
```

**3. What is their level of expertise?**
```
Domain experts in Earth observation and remote sensing. They understand satellite data, land cover classes and radar backscatter, but are not expected to know how to run or validate a foundation model.
```

**4. What tasks do these users expect the agent to support?**
```
1. Resolve a named place to an area of interest.
2. Find a suitable Sentinel-2 scene for that area and date.
3. Run TerraMind to generate land cover, radar backscatter and elevation layers for the scene.
4. Verify each generated layer against an independent reference dataset.
5. Compare two dates of the same area to detect change, such as flooding, vegetation loss from fire or clearing, crop cycles, or urban growth.
6. Report the results with metrics, images and full provenance.
```

**5. Walk me through the current step-by-step workflow for these tasks.**
```
1. Decide on the area of interest and the date, or the two dates for a change study, and look up the bounding box.
2. Search a Sentinel-2 catalogue for scenes over that area in the date range, and pick the clearest one.
3. Download the scene, cut it to the area, and prepare the bands in the format the model expects.
4. Run TerraMind to generate land cover, radar backscatter and elevation, and wait for the job.
5. Fetch reference datasets for the same area: an annual land cover map, a digital elevation model, and the nearest real Sentinel-1 pass.
6. Align the generated layers with the references and compute comparison metrics: pixel accuracy and class agreement for land cover, bias and correlation for elevation and backscatter.
7. For a change study, repeat steps 2 to 6 for the second date and compare the two results.
8. Write up the findings with the scene ids, job details, reference datasets and metrics.
```

**6. What are the main pain points or bottlenecks in this workflow?**
```
1. Setting up the model is heavy: GPU, weights, the right band order and scaling. Most scientists never get past this step.
2. Reference data lives in different catalogues with different projections and resolutions, so aligning it with the generated layers is slow, error-prone work.
3. Verification is usually skipped. Outputs get used because they look plausible, not because they were checked.
Generated and measured values get mixed up. A generated NDVI or elevation is easy to mistake for an observation.
4. A change study doubles everything and needs two matching scenes, which often means hunting for cloud-free dates.
5. Provenance is lost. Which scene, which run, which reference, which settings rarely make it into the write-up, so results cannot be reproduced.
```

**7. Which decisions in this workflow must always remain human-controlled?**
```
1. The area of interest and the dates. The agent asks for them and never guesses.
2. Which scene to use when several are available, if the choice is not obvious from cloud cover.
3. Whether a generated product is good enough for the scientist's purpose. The agent reports the comparison; the use decision is theirs.
4. Any conclusion that goes beyond the data, such as flood impact, damage or risk.
5. Whether to spend a long generation run, since each job takes minutes on the shared endpoint.
```

**8. How will users know the agent is successful? What does success look like?**
```
1. The scientist gets land cover, radar and elevation layers for their area and date without touching a GPU, a catalogue or a data format.
2. Every layer comes with its comparison against a reference, so they can see how well the model did on this scene, not just that it ran.
3. For two dates, the change is shown with the numbers behind it, and an independent check from the observed imagery.
4. Every number in the report can be traced to a tool result, and the scene, job, settings and references are all recorded, so another scientist can reproduce the run.
5. The agent says what it could not do, such as no cloud-free scene, rather than filling the gap.
```

At the end of the stage it shows a summary and a self-review and asks you to confirm:
```
confirm
```

---

## Stage 2.3: Tools

**1. What actions need dedicated tools?**
```
Tools:

1. geocode and reverse_geocode: place to area, coordinates to place.
2. search_scenes: find Sentinel-2 scenes.
3. generate and get_generation: run TerraMind and poll.
4. compare_maps: check one generation against the references.
5. compare_runs: compare two generations of the same area.
6. search_gdacs_events: find a current disaster when the user asks about one.
```

**2. For the main tool, what are the exact inputs and outputs?**
```
Inputs

aoi: bounding box [west, south, east, north] in WGS-84 degrees, or a GeoJSON polygon. Must sit inside a single Sentinel-2 tile and cover at most 4 tiles of 2.24 km on CPU, 16 on GPU.
start_date, end_date: ISO dates; the service picks the clearest scene in the range.
item_id (optional): a Sentinel-2 item id to force a specific scene, used when search_scenes or pick_scene already chose one.
outputs: subset of S1GRD, DEM, LULC, NDVI; the agent requests LULC, S1GRD, DEM and never NDVI, which is computed from the observed bands instead.
timesteps: integer 1 to 25, default 10, the diffusion steps for the continuous layers.

Outputs, one stable shape; the agent reads status, never the shape:

job_id, status in queued, starting, running, succeeded, failed; while not done also retry_after_s and an optional message. The agent polls get_generation with the job_id.
On succeeded: scene with item_id and datetime; tile with bbox and tile_count; seed and timings for provenance; outputs keyed by product, each with stats (land-cover class shares, min, max, mean for the continuous layers) and a cog_url to the GeoTIFF; input with the Sentinel-2 cog_url and observed_ndvi measured from the bands; preview images attached as tool images.
On failed: error in plain language, final, no retry. Causes: area too large, area crosses a tile border, no suitable scene, job failure.
```

**3. What errors are common, and what should the tool tell the agent when one occurs?**
```
Common errors: area too large or crossing a tile border, scene too cloudy or not covering the area, no scene in the date range, unknown job or scene id, service down or slow to start.

The tool returns a plain-language error naming the cause and the fix, never an exception. Async jobs return status: failed, final. Empty results are empty lists, not errors. The agent repeats the error, tries the one named fix once, then reports. No loops, no guesses.
```

Confirm the stage:
```
confirm
```

---

## Stage 3.1: Reasoning

**1. When the agent receives a typical request, how should it break the work into steps?**
```
Steps: resolve the place and state the area back; find the clearest scene in the date range, or two for a change study; run generate and poll; run compare_maps on every finished job; for two dates run compare_runs; report with scene, job, reference ids and the numbers.
```

**2. When should the agent ask the user clarifying questions instead of guessing?**
```
Ask instead of guessing: when the place is ambiguous, when no area or date was given, when several scenes are equally clear, and before any run that takes minutes.
```

**3. How should the agent behave when it is unsure about an answer?**
```
When unsure: say "cannot tell" and why, show the numbers that exist, never fill a gap with an estimate, never present a generated layer as an observation.
```

**4. In what situations must the agent stop and escalate to a human?**
```
Stop and escalate: any conclusion about impact, damage or risk; any statement about people or facilities; a product the comparison marks poor; a tool error with no named fix.
```

Confirm the stage:
```
confirm
```

---

## Stage 4.1: agents.md

No questions. When it asks whether to build `agents.md`:
```
Yes
```

That is the whole run. Download your design from the artifact pane if you want to keep it.
