"""Run a CARE artifact as an agent: its agents.md as the instructions, MCP tool servers, a model on your key.

    from harness import Settings, run_turn
    async for event in run_turn(Settings(...), "Is Conselice flooded on 23 May 2023?", history=[]):
        ...

Events are dicts: {"kind": "note" | "tool_call" | "tool_result" | "image" | "answer" | "error", ...}. The last
one carries the new message history for the next turn.
"""

from __future__ import annotations

import pathlib
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

import eve_compat

BLABLADOR_URL = "https://api.blablador.fz-juelich.de/v1"
QWEN_ALIASES = {"alias-code", "alias-large"}      # Qwen thinks before every answer unless told not to
MAX_FILE_CHARS = 60_000                           # one artifact file handed to the model
MAX_RESULT_CHARS = 1_500                          # one tool result shown in the chat


@dataclass
class McpServer:
    url: str
    token: str = ""


@dataclass
class Settings:
    artifact_dir: str
    model: str                                    # "blablador:alias-eve", "openai:gpt-5.2", ...
    blablador_key: str = ""
    openai_key: str = ""
    servers: list[McpServer] = field(default_factory=list)


# ── the artifact ────────────────────────────────────────────────────────────


def artifact_files(root: pathlib.Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and not p.name.startswith("."))


def artifact_summary(artifact_dir: str) -> dict:
    """Name and description from agents.md's front matter, and the file list, or an error."""
    root = pathlib.Path(artifact_dir).expanduser()
    agents = root / "agents.md"
    if not agents.is_file():
        return {"error": f"No agents.md in {root}. Point this at a CARE artifact folder."}
    text = agents.read_text(encoding="utf-8")
    meta = dict(re.findall(r"^(name|description):\s*(.+)$", text.split("\n---", 1)[0], flags=re.MULTILINE))
    return {"name": meta.get("name", root.name), "description": meta.get("description", ""),
            "files": artifact_files(root)}


def instructions(root: pathlib.Path) -> str:
    """agents.md, the list of artifact files the agent may read, and today's date."""
    files = "\n".join(f"- {f}" for f in artifact_files(root))
    return (f"{(root / 'agents.md').read_text(encoding='utf-8')}\n\n"
            f"## Artifact files\n\nThe design files behind these instructions. Read one with "
            f"`read_artifact_file` when you need its detail.\n\n{files}\n\n"
            f"The current date and time is {datetime.now(UTC):%A, %d %B %Y %H:%M} UTC.")


def artifact_toolset(root: pathlib.Path):
    from pydantic_ai import FunctionToolset

    tools = FunctionToolset()

    @tools.tool_plain
    def read_artifact_file(path: str) -> str:
        """Read one file of the agent's design artifact, by its path in the artifact file list."""
        target = (root / path).resolve()
        if root.resolve() not in target.parents or not target.is_file():
            return f"No artifact file {path!r}. Use a path from the artifact file list."
        return target.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_CHARS]

    return tools


# ── the model ───────────────────────────────────────────────────────────────


def build_model(settings: Settings):
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient
    from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider

    provider_name, _, name = settings.model.partition(":")
    if provider_name == "blablador":
        if not settings.blablador_key:
            raise ValueError("This model runs on Blablador: add your Blablador API key.")
        client = AsyncOpenAI(base_url=BLABLADOR_URL, api_key=settings.blablador_key,
                             http_client=DefaultAsyncHttpxClient(transport=eve_compat.retry_unparsed_transport()))
        provider = OpenAIProvider(openai_client=client)
        # Blablador's chat templates accept one system message, first; this merges the leading ones.
        profile = {**(provider.model_profile(name) or {}), "openai_chat_supports_multiple_system_messages": False}
        model_settings = ({"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
                          if name in QWEN_ALIASES else None)
        return OpenAIChatModel(name, provider=provider, profile=profile, settings=model_settings)
    if provider_name == "openai":
        if not settings.openai_key:
            raise ValueError("This model runs on OpenAI: add your OpenAI API key.")
        return OpenAIResponsesModel(name, provider=OpenAIProvider(api_key=settings.openai_key))
    raise ValueError(f"Unknown model {settings.model!r}: use blablador:<alias> or openai:<model>.")


# ── one turn ────────────────────────────────────────────────────────────────


def image_copier(on_image):
    """`process_tool_call` for a model that reads images: tool images also go to the chat, unchanged."""
    from pydantic_ai.messages import BinaryContent

    async def hook(ctx, call_tool, name: str, args: dict):
        result = await call_tool(name, args)
        for item in result if isinstance(result, list) else [result]:
            if isinstance(item, BinaryContent) and str(item.media_type).startswith("image/"):
                on_image(name, item.data, str(item.media_type))
        return result

    return hook


def _text(content) -> str:
    if isinstance(content, str):
        return content
    try:
        import json

        return json.dumps(content, default=str)[:20_000]
    except (TypeError, ValueError):
        return str(content)


async def run_turn(settings: Settings, prompt: str, history: list) -> AsyncIterator[dict]:
    """Run one user turn and yield what happens, in order. Model requests are never streamed: Blablador's
    streamed tool calls arrive garbled, and the answer is shown whole."""
    from pydantic_ai import Agent
    from pydantic_ai.capabilities import ProcessHistory
    from pydantic_ai.mcp import MCPToolset
    from pydantic_ai.messages import FunctionToolCallEvent, FunctionToolResultEvent, TextPart, ToolCallPart

    root = pathlib.Path(settings.artifact_dir).expanduser()
    if not (root / "agents.md").is_file():
        yield {"kind": "error", "text": f"No agents.md in {root}.", "history": history}
        return
    try:
        model = build_model(settings)
    except ValueError as e:
        yield {"kind": "error", "text": str(e), "history": history}
        return

    blablador = settings.model.startswith("blablador:")
    images: list[tuple[str, bytes, str]] = []
    keep = lambda caption, data, media_type: images.append((caption, data, media_type))  # noqa: E731
    hook = eve_compat.text_only_tool_hook(keep) if blablador else image_copier(keep)
    toolsets = [artifact_toolset(root)]
    for server in settings.servers:
        toolsets.append(MCPToolset(
            server.url,
            headers={"Authorization": f"Bearer {server.token}"} if server.token else None,
            include_instructions=True,
            init_timeout=30,                          # serverless MCP hosts take seconds to wake up
            process_tool_call=hook,
            # A tool's refusal is information for the model, not a retry to count.
            tool_error_behavior="failed",
        ))
    agent = Agent(
        model,
        instructions=instructions(root),
        toolsets=toolsets,
        model_settings=eve_compat.MODEL_SETTINGS if blablador else None,
        capabilities=[ProcessHistory(eve_compat.drop_empty_turns)] if blablador else [],
        retries={"tools": 2, "output": 4},
    )

    try:
        async with agent:
            async with agent.iter(prompt, message_history=history) as run:
                async for node in run:
                    if not Agent.is_call_tools_node(node):
                        continue
                    parts = node.model_response.parts
                    if any(isinstance(p, ToolCallPart) for p in parts):
                        for p in parts:
                            if isinstance(p, TextPart) and p.content.strip():
                                yield {"kind": "note", "text": p.content.strip()}
                    async with node.stream(run.ctx) as events:
                        async for ev in events:
                            if isinstance(ev, FunctionToolCallEvent):
                                yield {"kind": "tool_call", "name": ev.part.tool_name, "args": ev.part.args}
                            elif isinstance(ev, FunctionToolResultEvent):
                                text = _text(getattr(ev.part, "content", ""))
                                yield {"kind": "tool_result", "name": getattr(ev.part, "tool_name", ""),
                                       "text": text[:MAX_RESULT_CHARS] + ("…" if len(text) > MAX_RESULT_CHARS else "")}
                                while images:
                                    caption, data, media_type = images.pop(0)
                                    yield {"kind": "image", "caption": caption, "data": data, "media_type": media_type}
            answer = str(run.result.output or "")
            yield {"kind": "answer", "text": eve_compat.clean_answer(answer) if blablador else answer,
                   "history": run.result.all_messages()}
    except Exception as e:  # shown in the chat; the conversation so far is kept
        yield {"kind": "error", "text": f"{type(e).__name__}: {e}", "history": history}
