# AKD Agentic EO · Berlin 2026

Materials for **From Vibe Coding to Verifiable Scientific Discovery: Agentic Workflows for Earth Observation**,
the Agentic AI for EO Berlin Workshop, 21 October 2026 (Track 2), by NASA IMPACT.

The workshop builds an Earth-observation agent with [CARE](https://github.com/NASA-IMPACT/AKD-CARE)
(Collaborative Agent Reasoning Engineering), NASA IMPACT's methodology for engineering LLM agents through
structured, reusable design artifacts. The agent runs the TerraMind
foundation model over an area and dates, checks what the model generated against independent observations,
and reports the result with its evidence. This repository holds the agent's design, its tools, an app to run
it, and the slides.

| Folder | What is in it |
| --- | --- |
| [`Artifacts/`](Artifacts/) | The agent's CARE design: what it is for, its tools, how it reasons, what it reports, its guardrails |
| [`Tools/`](Tools/) | The agent's seven tools as one MCP server, to run locally or on FastMCP Cloud |
| [`Harness/`](Harness/) | The CARE Artifact Harness: a chat app that runs any CARE artifact with MCP tools on your own model key |
| [`Hands-on/`](Hands-on/) | Setup from sign-up to a running agent, and the answers to copy into the CARE interview, for pairs and for solo runs |
| [`Slides/`](Slides/) | Oral talk, hands-on and demo slides |

## Quick start

You need Python 3.10 or later (tested with 3.12) and a [Blablador](https://sdlaml.pages.jsc.fz-juelich.de/ai/guides/blablador_api_access/)
API key for ESA's EVE-Instruct, or an OpenAI key.

**1. Start the tools** (in one terminal):

```bash
cd Tools/terramind-eo
pip install -r requirements.txt
python server.py                  # MCP server at http://127.0.0.1:8000/mcp
```

**2. Start the harness** (in another):

```bash
cd Harness
pip install -r requirements.txt
cp .env.template .env             # put your Blablador key in .env, or paste it on the page
python app.py                     # http://127.0.0.1:7870
```

**3. Ask the agent.** The page opens with this repository's artifact and the local tools
(`http://127.0.0.1:8000/mcp`) already filled in, so the harness is attached to your tools with no extra setup.
Try *Find the clearest Sentinel-2 scene over Conselice, Italy, after the flood of 16 May 2023.* Each tool call
and its result appear in the chat before the answer.

To host the tools on FastMCP Cloud instead of your laptop, follow [`Tools/README.md`](Tools/README.md).

## The agent's design

[`Artifacts/terramind-eo-inference-agent/`](Artifacts/terramind-eo-inference-agent/) is the CARE artifact of
the *Earth Observation FM Inference Agent*. Start with `agents.md`: it is the agent's full instructions, built
from the rest of the design.

| File | Holds |
| --- | --- |
| `agents.md` | The agent's instructions |
| `scope.md` | What the agent is for, who uses it, what is out of scope |
| `contexts/` | Background the design relies on: data sources, the TerraMind service, how outputs are read |
| `tools/` | One specification per tool: inputs, outputs, when not to call it |
| `reasoning.md` | The order of steps and how the agent decides |
| `output.md` | The report format |
| `guardrails/` | Rules for safety and scope, and how each is enforced |

To run it elsewhere, give any agent host that speaks MCP the `agents.md` as its system prompt, the tools' MCP
URL, and a model. In the AKD Agent Co-Design Studio, upload [`Artifacts/terramind-eo-inference-agent.zip`](Artifacts/terramind-eo-inference-agent.zip) (the same folder, zipped) and attach it to an agent.

## The tools

One MCP server, [`Tools/terramind-eo/`](Tools/terramind-eo/), laid out like a server in ESA's
[EVE tool registry](https://github.com/eve-esa/mcp-tool-registry).

| Tool | Does | Needs |
| --- | --- | --- |
| `geocode`, `reverse_geocode` | Place name to an area, coordinates to a place name (OpenStreetMap) | nothing |
| `search_gdacs_events` | Live and recent disasters worldwide (GDACS, from ESA's registry) | nothing |
| `pick_scene` | The clearest Sentinel-2 scene near a date that fully covers the area | nothing |
| `run_area` | Runs TerraMind over the area: land cover, radar and elevation layers | a TerraMind service |
| `compare_area` | Checks each generated layer against an independent reference | a TerraMind service |
| `compare_dates` | Before versus after, with a Yes / No / Cannot tell answer by fixed rules | a TerraMind service |

The TerraMind tools need a TerraMind inference service that you run yourself (`TM_API_URL`); this repository
ships no endpoint. See [`Tools/README.md`](Tools/README.md).

## The harness

[`Harness/`](Harness/) turns a CARE artifact into a running agent: `agents.md` becomes the instructions, the
other design files stay readable to the agent, the MCP servers you list become its tools, and it runs on your
own key (EVE-Instruct or another Blablador model, or an OpenAI model). Keys stay in the browser session. Point
it at your own artifact folder to run your own design. Details in [`Harness/README.md`](Harness/README.md).

## Links

- CARE: https://github.com/NASA-IMPACT/AKD-CARE
- NASA IMPACT: https://www.earthdata.nasa.gov/about/impact
- TerraMind 1.0: https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base
- ESA EVE MCP tool registry: https://github.com/eve-esa/mcp-tool-registry
- Blablador: https://sdlaml.pages.jsc.fz-juelich.de/ai/guides/blablador_api_access/
- FastMCP Cloud: https://horizon.prefect.io

## Credits

`search_gdacs_events` comes from ESA's EVE MCP tool registry (Apache-2.0, ESA Φ-lab); see
[`Tools/terramind-eo/esa/NOTICE.md`](Tools/terramind-eo/esa/NOTICE.md). TerraMind is an Earth-observation
foundation model by IBM and ESA (Apache-2.0). EVE-Instruct is ESA's Earth-observation language model, served by
Helmholtz's Blablador.
