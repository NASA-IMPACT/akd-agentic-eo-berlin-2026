"""Chat with an agent built from a CARE artifact and MCP tools.

    pip install -r requirements.txt
    python app.py                      # http://127.0.0.1:7870

Keys come from the fields on the page, or from BLABLADOR_API_KEY / OPENAI_API_KEY in .env next to this file.
Keys typed on the page stay in this browser session only; nothing is written to disk.
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile

import gradio as gr
from dotenv import load_dotenv

from harness import McpServer, Settings, artifact_summary, run_turn

HERE = pathlib.Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

DEFAULT_ARTIFACT = os.environ.get("HARNESS_ARTIFACT", str(HERE.parent / "Artifacts" / "terramind-eo-inference-agent"))
DEFAULT_SERVERS = os.environ.get("HARNESS_MCP_SERVERS", "http://127.0.0.1:8000/mcp")
MODELS = ["blablador:alias-eve", "blablador:alias-large", "openai:gpt-5.2", "openai:gpt-5-mini"]
IMAGE_DIR = pathlib.Path(tempfile.mkdtemp(prefix="harness-images-"))


def parse_servers(text: str) -> list[McpServer]:
    """One server per line: `URL` or `URL TOKEN`. Blank lines and lines starting with # are skipped."""
    servers = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            url, _, token = line.partition(" ")
            servers.append(McpServer(url=url.strip(), token=token.strip()))
    return servers


def describe_artifact(artifact_dir: str) -> str:
    info = artifact_summary(artifact_dir)
    if "error" in info:
        return f"**{info['error']}**"
    return f"**{info['name']}**: {info['description']}  \n{len(info['files'])} files, starting with `agents.md`."


def save_image(data: bytes, media_type: str) -> str:
    suffix = "." + media_type.split("/")[-1].split("+")[0]
    path = IMAGE_DIR / f"{len(list(IMAGE_DIR.iterdir())):04d}{suffix}"
    path.write_bytes(data)
    return str(path)


async def respond(message, chat, history, artifact_dir, servers_text, model, blablador_key, openai_key):
    if not message.strip():
        yield chat, history, ""
        return
    chat = chat + [gr.ChatMessage(role="user", content=message)]
    yield chat, history, ""
    settings = Settings(
        artifact_dir=artifact_dir,
        model=model,
        blablador_key=blablador_key.strip() or os.environ.get("BLABLADOR_API_KEY", ""),
        openai_key=openai_key.strip() or os.environ.get("OPENAI_API_KEY", ""),
        servers=parse_servers(servers_text),
    )
    async for event in run_turn(settings, message, history):
        kind = event["kind"]
        if kind == "note":
            chat.append(gr.ChatMessage(role="assistant", content=event["text"], metadata={"title": "Thinking"}))
        elif kind == "tool_call":
            args = event["args"] if isinstance(event["args"], str) else json.dumps(event["args"], indent=1)
            chat.append(gr.ChatMessage(role="assistant", content=f"```json\n{args}\n```",
                                       metadata={"title": f"Calling {event['name']}"}))
        elif kind == "tool_result":
            chat.append(gr.ChatMessage(role="assistant", content=f"```\n{event['text']}\n```",
                                       metadata={"title": f"{event['name']} answered"}))
        elif kind == "image":
            chat.append(gr.ChatMessage(role="assistant",
                                       content=gr.Image(save_image(event["data"], event["media_type"]),
                                                        label=event["caption"])))
        elif kind == "answer":
            chat.append(gr.ChatMessage(role="assistant", content=event["text"] or "*(no answer)*"))
            history = event["history"]
        elif kind == "error":
            chat.append(gr.ChatMessage(role="assistant", content=f"**Error:** {event['text']}"))
            history = event["history"]
        yield chat, history, ""


def key_hint(var: str) -> str:
    return f"Using {var} from .env" if os.environ.get(var) else "Paste your key"


# ── look ─────────────────────────────────────────────────────────────────────
# NASA colours: NASA blue for actions and links, NASA red as a small highlight, on a cool grey page with
# white cards. Light in both colour modes.

ACCENT, ACCENT_DARK, ACCENT_SOFT = "#0B3D91", "#082C6C", "#E8EEF8"   # NASA blue
RED = "#FC3D21"                                                     # NASA red
PAGE, FIELD = "#F2F4F7", "#F6F7F9"
INK, INK_2, INK_3 = "#0F172A", "#334155", "#64748B"

FONT_HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Serif:wght@600&display=swap" rel="stylesheet">
"""

HEADER = f"""
<div id="hdr">
  <div class="toprow">
    <span class="eyebrow">Agentic AI for EO · Berlin Workshop</span>
    <a class="chip" href="https://github.com/NASA-IMPACT/AKD-CARE" target="_blank">Built with CARE · NASA-IMPACT/AKD-CARE ↗</a>
    <a class="toplink" href="https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base" target="_blank">TerraMind ↗</a>
  </div>
  <h1>CARE Artifact Harness</h1>
  <p class="lead">The CARE Artifact Harness turns a CARE design into a running agent. Point it at an artifact
  folder: its <code>agents.md</code> becomes the agent's instructions, and the rest of the design (scope, tool
  specifications, reasoning strategy, output format, guardrails) stays available for the agent to read while it
  works. Attach the MCP servers that hold the agent's tools, choose a model, and ask it a question.</p>
  <p>It runs on your own key: ESA's EVE-Instruct and other open models through Helmholtz's Blablador, or an
  OpenAI model. Every tool call and its result appear in the chat as they happen, so you can see what the agent
  did before you read its answer. The example loaded below is the <b>Earth Observation FM Inference Agent</b>,
  which runs the TerraMind foundation model over an area and checks what it generated against independent
  observations.</p>
  <div class="steps">
    <div><span>01</span>Choose an artifact folder: the one in this repository, or your own from the Co-Design Studio.</div>
    <div><span>02</span>Attach MCP servers: run this repository's tools locally, or use your own FastMCP Cloud URL.</div>
    <div><span>03</span>Pick a model and ask. Keys stay in this browser session and are never stored.</div>
  </div>
  <p class="note">A workshop tool for trying agent designs, not a production service. Answers depend on the model
  and on the tools you attach: check the tool results before you rely on an answer.</p>
</div>
"""

EMPTY_CHAT = f"""
<div style="text-align:center; max-width:560px; margin:0 auto;">
  <div style="font-family:'IBM Plex Serif',serif; font-size:22px; color:{INK}; margin-bottom:10px;">Ask the agent</div>
  <div style="font-size:14.5px; line-height:1.7; color:{INK_2};">For example: <i>Find the clearest Sentinel-2
  scene over Conselice, Italy, after the flood of 16 May 2023.</i></div>
</div>
"""

EXAMPLES = [
    "Find the clearest Sentinel-2 scene over Conselice, Italy, after the flood of 16 May 2023.",
    "Which disasters are active worldwide right now?",
    "What does this agent refuse to do, and why?",
]

CSS = f"""
html, body, gradio-app, .gradio-container {{ background: {PAGE} !important; }}
.gradio-container {{ max-width: 1120px !important; width: 100% !important; min-width: 0 !important; margin: 0 auto !important;
  font-family: 'IBM Plex Sans', sans-serif !important; color: {INK}; }}
footer {{ display: none !important; }}
.gradio-container .html-container {{ padding: 0 !important; }}

#hdr {{ padding: 18px 2px 6px; }}
#hdr .toprow {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }}
#hdr .eyebrow {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; letter-spacing: .16em;
  text-transform: uppercase; color: {RED}; }}
#hdr .chip {{ font-family: 'IBM Plex Mono', monospace; font-size: 11.5px; color: {ACCENT}; background: {ACCENT_SOFT};
  border: 1px solid rgba(11,61,145,.25); padding: 4px 11px; border-radius: 20px; text-decoration: none; }}
#hdr .toplink {{ margin-left: auto; font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; color: {ACCENT};
  text-decoration: none; }}
#hdr h1 {{ border-left: 4px solid {ACCENT}; padding-left: 12px; }}
#hdr h1 {{ font-family: 'IBM Plex Serif', serif; font-size: 32px; font-weight: 600; letter-spacing: -.015em;
  margin: 0 0 10px; color: {INK}; }}
#hdr p {{ font-size: 15px; line-height: 1.7; color: {INK_2}; max-width: 860px; margin: 0 0 12px; }}
#hdr p.lead {{ color: {INK}; }}
#hdr p.note {{ font-size: 13.5px; color: {INK_3}; margin: 4px 0 0; }}
#hdr .steps {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin: 6px 0 10px;
  max-width: 1000px; }}
#hdr .steps div {{ background: #fff; border: 1px solid rgba(15,23,42,.1); border-radius: 12px; padding: 12px 14px;
  font-size: 13.5px; line-height: 1.55; color: {INK_2}; }}
#hdr .steps span {{ display: block; font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600;
  color: {ACCENT}; margin-bottom: 4px; }}
#hdr code {{ font-family: 'IBM Plex Mono', monospace; font-size: 13px; background: {ACCENT_SOFT}; color: {ACCENT_DARK};
  padding: 1px 6px; border-radius: 6px; }}

#setup, #chatcard {{ background: #fff !important; border: 1px solid rgba(15,23,42,.1) !important;
  border-radius: 16px !important; padding: 16px 18px !important; box-shadow: none !important; }}
#setup .block, #chatcard .block, #setup .form, #chatcard .form {{ background: transparent !important;
  border: none !important; box-shadow: none !important; }}
#setup label > span, #setup .block-label, #setup [data-testid="block-title"], #setup [data-testid="block-label"] {{
  background: transparent !important; border: none !important; padding-left: 0 !important;
  color: {INK} !important; font-weight: 600 !important; font-size: 13.5px !important; }}
#setup [data-testid="block-info"], #setup .block-info {{ color: {INK_3} !important; font-weight: 400 !important;
  font-size: 12.5px !important; }}
#setup input, #setup textarea, #composer textarea {{ background: {FIELD} !important;
  border: 1px solid rgba(15,23,42,.14) !important; border-radius: 10px !important; color: {INK} !important;
  font-family: 'IBM Plex Mono', monospace !important; font-size: 13.5px !important; }}
#setup .wrap:has(> .wrap-inner) {{ background: {FIELD} !important; border: 1px solid rgba(15,23,42,.14) !important;
  border-radius: 10px !important; }}
#setup .wrap-inner input {{ background: transparent !important; border: none !important; }}
#artifact-info, #artifact-info .prose {{ background: {ACCENT_SOFT} !important; border-radius: 10px;
  font-size: 14px; color: {INK_2} !important; line-height: 1.6; }}
#artifact-info {{ padding: 10px 14px !important; }}
#artifact-info strong {{ color: {ACCENT_DARK} !important; }}
#artifact-info code {{ background: #fff !important; color: {ACCENT_DARK} !important; border-radius: 6px;
  padding: 1px 6px; font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; }}
.sectionlabel {{ font-family: 'IBM Plex Mono', monospace; font-size: 11.5px; letter-spacing: .12em;
  text-transform: uppercase; color: {INK_3}; margin: 2px 0 4px; }}

#chatcard .bubble-wrap {{ background: #fff !important; }}
#chatcard .message-row.user-row .message, #chatcard .user-row .bubble {{ background: {ACCENT} !important;
  color: #fff !important; border: none !important; border-radius: 14px 14px 4px 14px !important; }}
#chatcard .user-row .bubble *, #chatcard .message-row.user-row .message * {{ color: #fff !important; }}
#chatcard .message-row.bot-row .message, #chatcard .bot-row .bubble {{ background: transparent !important;
  border: none !important; box-shadow: none !important; color: {INK_2} !important; }}
#chatcard .bot-row code {{ background: {ACCENT_SOFT} !important; color: {ACCENT_DARK} !important;
  border-radius: 6px !important; padding: 1px 6px !important; font-family: 'IBM Plex Mono', monospace !important;
  font-size: 12.5px !important; }}
#chatcard .bot-row pre, #chatcard .bot-row pre code {{ background: {FIELD} !important; color: {INK} !important;
  border-radius: 10px !important; font-size: 12px !important; white-space: pre-wrap !important;
  overflow-wrap: anywhere !important; }}
#chatcard .thought-group, #chatcard .message-wrap .thought {{ border-color: rgba(11,61,145,.25) !important; }}

#composer {{ gap: 8px !important; align-items: center !important; }}
#composer button {{ height: 40px !important; min-height: 40px !important; max-height: 40px !important;
  padding: 0 16px !important; font-size: 14px !important; border-radius: 10px !important; flex-grow: 0 !important; }}
#composer textarea {{ min-height: 40px !important; }}
#composer button.primary {{ background: {ACCENT} !important; border: none !important; }}
#composer button.primary:hover {{ background: {ACCENT_DARK} !important; }}
.examples-row button {{ font-size: 13px !important; border-radius: 999px !important;
  border: 1px solid rgba(11,61,145,.3) !important; background: #fff !important; color: {ACCENT_DARK} !important; }}
.examples-row button:hover {{ border-color: {ACCENT} !important; background: {ACCENT_SOFT} !important; }}
"""


def light_theme():
    t = gr.themes.Soft(primary_hue="blue", neutral_hue="slate",
                       font=[gr.themes.GoogleFont("IBM Plex Sans"), "sans-serif"],
                       font_mono=[gr.themes.GoogleFont("IBM Plex Mono"), "monospace"])
    colours = {
        "body_background_fill": PAGE, "background_fill_primary": "#ffffff",
        "background_fill_secondary": FIELD, "block_background_fill": "#ffffff",
        "body_text_color": INK, "body_text_color_subdued": INK_2, "input_background_fill": FIELD,
        "border_color_primary": "rgba(15,23,42,.12)", "link_text_color": ACCENT,
        "button_primary_background_fill": ACCENT, "button_primary_background_fill_hover": ACCENT_DARK,
        "button_primary_text_color": "#ffffff", "button_secondary_background_fill": "#ffffff",
        "button_secondary_text_color": INK_2, "color_accent_soft": ACCENT_SOFT,
        "block_label_background_fill": "#ffffff", "block_label_text_color": INK, "block_title_text_color": INK,
        "code_background_fill": ACCENT_SOFT,
    }
    # The same colours in dark mode, so the page never flips to a dark palette it was not designed for.
    return t.set(**colours, **{f"{k}_dark": v for k, v in colours.items()})


with gr.Blocks(title="CARE Artifact Harness") as demo:
    history = gr.State([])
    gr.HTML(HEADER)
    with gr.Column(elem_id="setup"):
        gr.HTML('<div class="sectionlabel">Agent setup</div>')
        with gr.Row():
            artifact_dir = gr.Textbox(DEFAULT_ARTIFACT, label="Artifact folder", info="The folder that holds agents.md",
                                      scale=3)
            model = gr.Dropdown(MODELS, value=MODELS[0], label="Model", allow_custom_value=True,
                                info="blablador:<alias> or openai:<model>", scale=1, min_width=230)
        artifact_info = gr.Markdown(describe_artifact(DEFAULT_ARTIFACT), elem_id="artifact-info")
        servers = gr.Textbox(DEFAULT_SERVERS, lines=2, label="MCP servers",
                             info="One per line: URL, or URL then a space and its token")
        with gr.Row():
            blablador_key = gr.Textbox("", type="password", label="Blablador API key",
                                       placeholder=key_hint("BLABLADOR_API_KEY"),
                                       info="Used only for this session, never stored")
            openai_key = gr.Textbox("", type="password", label="OpenAI API key", placeholder=key_hint("OPENAI_API_KEY"),
                                    info="Only for openai: models")
    with gr.Column(elem_id="chatcard"):
        chat = gr.Chatbot(height=560, show_label=False, placeholder=EMPTY_CHAT, group_consecutive_messages=False)
        with gr.Row(elem_classes="examples-row"):
            example_buttons = [gr.Button(text, size="sm") for text in EXAMPLES]
        with gr.Row(elem_id="composer"):
            message = gr.Textbox(placeholder="Ask the agent", show_label=False, lines=1, scale=1)
            send = gr.Button("Send", variant="primary", scale=0, min_width=80)
            clear = gr.Button("New chat", scale=0, min_width=96)

    inputs = [message, chat, history, artifact_dir, servers, model, blablador_key, openai_key]
    outputs = [chat, history, message]
    artifact_dir.change(describe_artifact, artifact_dir, artifact_info)
    message.submit(respond, inputs, outputs)
    send.click(respond, inputs, outputs)
    clear.click(lambda: ([], [], ""), None, outputs)
    for button, text in zip(example_buttons, EXAMPLES):
        button.click(lambda t=text: t, None, message)

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=4).launch(
        server_name="127.0.0.1", server_port=int(os.environ.get("PORT", "7870")),
        theme=light_theme(), css=CSS, head=FONT_HEAD,
    )
