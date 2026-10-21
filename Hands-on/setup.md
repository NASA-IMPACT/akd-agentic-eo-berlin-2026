# Hands-on setup: from sign-up to a running agent

Everything happens in the browser on the workshop Studio: **https://workshop.akd.odsi.io**. Nothing to
install, no API key needed. If you have your own Blablador key you may add it later from the sidebar, but
the workshop key covers you.

## 1. Sign up (2 minutes)

1. Open the join link, which carries the workshop key: **https://workshop.akd.odsi.io/waitlist?key=J6QS-Q9D3-Z99Z-PRBE**
2. Full name, email, password. The key is already filled in; if it is not, it is `J6QS-Q9D3-Z99Z-PRBE`.
3. You land in the workshop project straight away; no approval wait.

## 2. Part 1: design the agent with Mini CARE (20 minutes)

CARE is an interview. You answer, it writes the design files. The workshop runs four stages: scope, tool
design, reasoning strategy, and the final `agents.md`.

**In pairs** (recommended). One of you is the **Scientist** and leads, the other is the **Developer**.

1. Scientist: **Designs → New design** from the workshop template. Name `Earth Observation FM Inference Agent`, description
   `Checks whether a named place flooded between two dates, with TerraMind over Sentinel-2, and reports the
   evidence.`, model `DeepSeek-V4.1-Flash (fast, HZDR)`, left as is if already selected; if it errors during the session, switch the design to `DeepSeek-V4.1-Flash (JUWELS)` or `Qwen3.8-Flash-Next`. In the design
   header, **assign** your Developer by the email they signed up with; they must sign up first.
2. Developer: open the design from your list.
3. Both: open the interview and type `start`. Answer from your role's file:
   [`care-process-small-pair-scientist.md`](care-process-small-pair-scientist.md) or
   [`care-process-small-pair-developer.md`](care-process-small-pair-developer.md). You answer at the same time, in your own copy.
4. When a stage ends with "Confirm these requirements", reply `Yes.` Open items in its self-review are fine.
5. After both of you finish Stage 4.1, the Scientist opens **Reconcile**, sends the two messages at the end
   of the Scientist file, then **Publish** to both. You now share one agreed design.

**On your own.** Same, without assigning anyone, following [`care-process-small-solo.md`](care-process-small-solo.md).
No Reconcile; the `agents.md` from Stage 4.1 is yours.

**If it stalls.** A red "status_code: 400" from Blablador means the model service hiccupped: send the same
message again, or switch the design's model to Qwen3.8-Flash-Next. "Too vague" means CARE wants one concrete
example.

## 3. Part 2: wire and run the agent (instructor)

Part 2 uses the complete artifact in this repository, not the one from Part 1, so everyone starts from the
same agent. The artifact is [`../Artifacts/terramind-eo-inference-agent.zip`](../Artifacts/terramind-eo-inference-agent.zip).

1. **Agents → New Agent.** Executor: `pydantic_ai`. Model: `blablador:alias-eve` (EVE-Instruct). Attach the
   artifact zip; `agents.md` becomes the instructions and the other files stay readable to the agent.
2. **Enable MCP server**, twice, one entry per server:

   | Server | URL | Token | Tools to allow |
   | --- | --- | --- | --- |
   | TerraMind service | `https://vaan0aamql.execute-api.us-west-2.amazonaws.com/mcp` | none | `search_scenes`, `generate`, `get_generation` |
   | EO tools (FastMCP Cloud) | `https://eo-mcp-tools.fastmcp.app/mcp` | `fmcp_cPvkskn9JpMakmxBOx5Wqj1mTkY-x0OjPcHin8twrhk` | `geocode`, `reverse_geocode`, `search_gdacs_events`, `pick_scene`, `run_area`, `compare_area`, `compare_dates` |

   The EO tools token is deleted on Saturday 25 October; after that, redeploy the tools from
   [`../Tools/README.md`](../Tools/README.md) and use your own.
3. **Guardrails.** Input guardrail and output guardrail off for the first run; switch them on for the trap
   prompt only.
4. **New chat** and ask:
   - *Was Conselice, Italy flooded between 23 April and 23 May 2023?*  (expect: Yes, water 0 to 16 percent)
   - *Was Vlochos, Greece flooded between 22 July and 10 September 2023?*  (expect: Cannot tell from the
     generated land cover; the observed NDVI drop shows it)
   Each tool call and its result appear in the chat before the answer. A full run takes two to five minutes;
   the first run of the day a little longer while the GPU warms.
5. **Trap prompt**, with guardrails on: ask about a refugee camp or casualties. The input guardrail blocks it.

## 4. What participants take home

- Their own Mini CARE design, downloadable as a zip from the design's artifact pane.
- This repository: the complete artifact, the tools as an MCP server, and the harness to run any CARE
  artifact on their own Blablador key, laptop only.

## Where things are

| Need | Where |
| --- | --- |
| The Studio | https://workshop.akd.odsi.io |
| Join link with the workshop key | https://workshop.akd.odsi.io/waitlist?key=J6QS-Q9D3-Z99Z-PRBE |
| TerraMind MCP server | https://vaan0aamql.execute-api.us-west-2.amazonaws.com/mcp |
| EO tools MCP server | https://eo-mcp-tools.fastmcp.app/mcp (token above, valid until 25 October) |
| Interview answers, pairs | [`care-process-small-pair-scientist.md`](care-process-small-pair-scientist.md) and [`care-process-small-pair-developer.md`](care-process-small-pair-developer.md) |
| Interview answers, solo | [`care-process-small-solo.md`](care-process-small-solo.md) |
| The complete artifact | [`../Artifacts/terramind-eo-inference-agent.zip`](../Artifacts/terramind-eo-inference-agent.zip) |
| The tools' source | [`../Tools/terramind-eo/`](../Tools/terramind-eo/) |
| Run it at home | [`../Harness/`](../Harness/) |
