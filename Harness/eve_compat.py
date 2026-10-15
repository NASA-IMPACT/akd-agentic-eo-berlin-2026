"""What a model on Blablador (ESA's EVE-Instruct and the other aliases) needs that OpenAI does not.

Each fix answers one behaviour seen with EVE; harness.py applies them only to `blablador:` models.

- Blablador rejects a request whose tool-call JSON the model wrote badly (400 "Expecting ',' delimiter");
  the same request usually parses on the next try: `retry_unparsed_transport` re-sends it.
- EVE sometimes answers with nothing. pydantic-ai then asks again as a user message straight after the tool
  results, which Blablador's Mistral template rejects: `drop_empty_turns` re-sends the conversation instead.
- EVE is text-only and rejects image parts: `text_only_tool_hook` keeps tool images for the chat and gives
  the model a text marker. It also repairs the area of interest EVE writes in odd shapes (`normalize_aoi`)
  and hides signed download links it would otherwise paste into the answer (`redact_signed_urls`).
- EVE sometimes wraps the whole answer in a code fence or writes notes about images: `clean_answer`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

import httpx

MODEL_SETTINGS = {"temperature": 0.2}  # keeps EVE on the report format

_UNPARSED = re.compile(r"Expecting .* delimiter|Expecting value|Extra data|Unterminated string|Invalid control character")


def unparsed_tool_call(status_code: int, body: str) -> bool:
    """A 400 from Blablador's tool-call parser (the model wrote invalid JSON), not a bad request."""
    return status_code == 400 and bool(_UNPARSED.search(body or ""))


class RetryUnparsedToolCalls(httpx.AsyncBaseTransport):
    """Re-sends a request Blablador rejected only because the model's tool-call JSON did not parse."""

    def __init__(self, attempts: int = 3) -> None:
        self._inner = httpx.AsyncHTTPTransport()
        self._attempts = attempts

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        attempt = 1
        while True:
            response = await self._inner.handle_async_request(request)
            if response.status_code != 400 or attempt == self._attempts:
                return response
            body = await response.aread()
            await response.aclose()
            if not unparsed_tool_call(response.status_code, body.decode("utf-8", "replace")):
                # `aread` decoded the body, so drop the encoding and length headers it no longer matches.
                headers = [(k, v) for k, v in response.headers.multi_items()
                           if k.lower() not in ("content-encoding", "content-length")]
                return httpx.Response(response.status_code, headers=headers, content=body, request=request)
            attempt += 1

    async def aclose(self) -> None:
        await self._inner.aclose()


def retry_unparsed_transport() -> RetryUnparsedToolCalls:
    return RetryUnparsedToolCalls()


def _is_empty(response) -> bool:
    from pydantic_ai.messages import TextPart, ThinkingPart

    return all(isinstance(p, ThinkingPart) or (isinstance(p, TextPart) and not p.content.strip())
               for p in response.parts)


def drop_empty_turns(messages: list) -> list:
    """History processor: drop an empty model answer and pydantic-ai's "please answer" retry prompt that
    follows it, so the same conversation is sent again (it still counts against the output retries)."""
    from pydantic_ai.messages import ModelRequest, ModelResponse, RetryPromptPart

    out: list = []
    i = 0
    while i < len(messages):
        m, nxt = messages[i], messages[i + 1] if i + 1 < len(messages) else None
        if (isinstance(m, ModelResponse) and _is_empty(m) and isinstance(nxt, ModelRequest) and nxt.parts
                and all(isinstance(p, RetryPromptPart) and p.tool_name is None for p in nxt.parts)):
            i += 2
            continue
        out.append(m)
        i += 1
    return out


_CORNERS = {
    "west": ("west", "min_lon", "lon_min", "minlon", "min_x", "x_min", "minx", "xmin", "left"),
    "south": ("south", "min_lat", "lat_min", "minlat", "min_y", "y_min", "miny", "ymin", "bottom"),
    "east": ("east", "max_lon", "lon_max", "maxlon", "max_x", "x_max", "maxx", "xmax", "right"),
    "north": ("north", "max_lat", "lat_max", "maxlat", "max_y", "y_max", "maxy", "ymax", "top"),
}


def _bbox_from_corners(obj: dict) -> list | None:
    keys = {str(k).strip().lower(): v for k, v in obj.items()}
    out = []
    for names in _CORNERS.values():
        found = [keys[n] for n in names if n in keys]
        if len(found) != 1 or not isinstance(found[0], (int, float)) or isinstance(found[0], bool):
            return None
        out.append(float(found[0]))
    return out


def normalize_aoi(args: dict) -> dict:
    """An `aoi` written as a quoted JSON string, an object with `bbox`, or named corners becomes the
    4-number list tools expect. Anything else is passed on unchanged, so the tool's own error reaches the model."""
    aoi = args.get("aoi") if isinstance(args, dict) else None
    if aoi is None:
        return args
    fixed = aoi
    if isinstance(aoi, str):
        try:
            fixed = json.loads(aoi)
        except ValueError:
            nums = re.findall(r"-?\d+(?:\.\d+)?", aoi)
            fixed = [float(n) for n in nums] if len(nums) == 4 else aoi
        if not isinstance(fixed, (list, dict)):
            fixed = aoi
    if isinstance(fixed, dict) and "type" not in fixed:
        bbox = fixed.get("bbox")
        fixed = bbox if isinstance(bbox, list) and len(bbox) == 4 else (_bbox_from_corners(fixed) or fixed)
    return args if fixed is aoi else {**args, "aoi": fixed}


SIGNED_URL_RE = re.compile(r"https?://[^\s\"'()<>]+\?[^\s\"'()<>]*X-Amz-(?:Signature|Credential)=[^\s\"'()<>]*")


def redact_signed_urls(obj):
    """Signed download links anywhere in a tool result become a placeholder the model cannot paste."""
    if isinstance(obj, str):
        return SIGNED_URL_RE.sub("[file link held by the host]", obj)
    if isinstance(obj, list):
        return [redact_signed_urls(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact_signed_urls(v) for k, v in obj.items()}
    return obj


def divert_images(result, name: str, on_image: Callable[[str, bytes, str], None]):
    """Images in a tool result go to `on_image(caption, data, media_type)` for the chat; the model gets a
    text marker in their place. A text item `preview: <caption>` just before an image names it."""
    from pydantic_ai.messages import BinaryContent

    items = result if isinstance(result, list) else [result]
    out, caption, changed = [], name, False
    for item in items:
        if isinstance(item, str) and item.startswith("preview:"):
            caption, changed = item.split(":", 1)[1].strip() or name, True
            continue
        if isinstance(item, BinaryContent) and str(item.media_type).startswith("image/"):
            on_image(caption, item.data, str(item.media_type))
            out.append(f"[image '{caption}' shown to the user]")
            changed = True
            continue
        out.append(item)
    if not changed:
        return result
    return out if isinstance(result, list) else (out[0] if len(out) == 1 else out)


def text_only_tool_hook(on_image: Callable[[str, bytes, str], None]):
    """`process_tool_call` for a text-only model: repaired arguments in, images out, signed links hidden."""

    async def hook(ctx, call_tool, name: str, args: dict):
        result = await call_tool(name, normalize_aoi(args))
        return redact_signed_urls(divert_images(result, name, on_image))

    return hook


def clean_answer(text: str) -> str:
    """Unwrap an answer fenced whole as markdown, and drop image links and image notes a text-only model
    cannot back (it has no image files). Fences naming a programming language are code and stay."""
    fenced = re.fullmatch(r"\s*```(?:markdown|md)?[ \t]*\n(.*)\n```\s*", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced and "```" not in fenced.group(1):
        text = fenced.group(1)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(
        r"^[ \t]*(?:\[[^\]\n]*\bimages?\b[^\]\n]*\]|\*[^*\n]*\bimages?\b[^*\n]*\*|_[^_\n]*\bimages?\b[^_\n]*_)[ \t]*$",
        "", text, flags=re.IGNORECASE | re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
