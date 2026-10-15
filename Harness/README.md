# Harness

A small chat app that runs an agent from a CARE artifact. Point it at an artifact folder, the MCP servers that
hold its tools, and a model on your own key, and chat with it.

- **Instructions:** the artifact's `agents.md`, plus the list of its other files, which the agent can read
  with a `read_artifact_file` tool when it needs a detail.
- **Tools:** any MCP servers you list, for example `../Tools/terramind-eo` running on your laptop or on FastMCP Cloud.
- **Model:** ESA's EVE-Instruct or another Blablador model (`blablador:alias-eve`, `blablador:alias-large`) on your
  Blablador key, or an OpenAI model on your OpenAI key.
- **The chat** shows each tool call and its answer as it happens, images from tools, then the agent's answer.

## Run it

Python 3.10 or later (tested with 3.12).

```bash
cd Harness
pip install -r requirements.txt
cp .env.template .env            # optional: put your keys here instead of pasting them on the page
python app.py                    # http://127.0.0.1:7870
```

With the tools running (`cd ../Tools/terramind-eo && python server.py`), the defaults on the page already
point at this repository's artifact and at `http://127.0.0.1:8000/mcp`. Add a token after a server's URL,
separated by a space, if the server needs one.

Try: *Find the clearest Sentinel-2 scene over Conselice, Italy, after the flood of 16 May 2023.*

## EVE on Blablador

EVE-Instruct is text-only and Blablador's endpoint has a few quirks, so for `blablador:` models the harness:
re-sends a request Blablador rejected because of badly formed tool-call JSON; re-sends the conversation after an
empty answer; keeps tool images for the chat and gives the model a text note instead; repairs an area of interest
written in an unusual shape; and hides signed download links. See `eve_compat.py`. Model requests are not streamed,
so the answer appears in one piece after the tool calls.

Keys typed on the page stay in that browser session. Nothing is stored.
