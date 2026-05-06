from __future__ import annotations

import os

from ..types import Mode
from .base import JUDE_SYSTEM_PROMPT, LLMClient, LLMResponse


class AnthropicClient(LLMClient):
    """Anthropic Messages API client.

    Anthropic's API is zero-retention by default for non-flagged content,
    but this is a contractual property of *your* account configuration —
    Jude does not verify it. The user must attest it per matter.
    """

    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5",
        max_tokens: int = 4096,
    ):
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key or _resolve_api_key())
        self.model = model
        self.max_tokens = max_tokens

    def complete_chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        mode: Mode,
        zero_retention_attested: bool,
    ) -> LLMResponse:
        self._enforce_mode(mode, zero_retention_attested)
        full_system = JUDE_SYSTEM_PROMPT + "\n\n" + system if system else JUDE_SYSTEM_PROMPT
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=full_system,
            messages=messages,
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        )
        return LLMResponse(
            text=text,
            model=msg.model,
            input_tokens=getattr(msg.usage, "input_tokens", None),
            output_tokens=getattr(msg.usage, "output_tokens", None),
        )

    def stream_chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        mode: Mode,
        zero_retention_attested: bool,
    ):
        """Stream text deltas from the Anthropic API as they arrive."""

        self._enforce_mode(mode, zero_retention_attested)
        full_system = JUDE_SYSTEM_PROMPT + "\n\n" + system if system else JUDE_SYSTEM_PROMPT
        with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=full_system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield text


def _resolve_api_key() -> str | None:
    """Read ANTHROPIC_API_KEY from env, falling back to macOS launchctl.

    On macOS, GUI-launched apps (Claude Code, Streamlit launched from a
    terminal-less context) often don't inherit shell env. `launchctl
    setenv` is the right place to set durable user-session env vars; this
    helper transparently bridges that gap.
    """

    val = os.environ.get("ANTHROPIC_API_KEY")
    if val:
        return val

    import shutil
    import subprocess

    if shutil.which("launchctl") is None:
        return None
    try:
        result = subprocess.run(
            ["launchctl", "getenv", "ANTHROPIC_API_KEY"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        candidate = result.stdout.strip()
        return candidate or None
    except (subprocess.SubprocessError, OSError):
        return None
