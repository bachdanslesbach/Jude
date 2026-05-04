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
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
    ):
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.max_tokens = max_tokens

    def complete(
        self,
        system: str,
        user_message: str,
        mode: Mode,
        zero_retention_attested: bool,
    ) -> LLMResponse:
        self._enforce_mode(mode, zero_retention_attested)
        full_system = JUDE_SYSTEM_PROMPT + "\n\n" + system if system else JUDE_SYSTEM_PROMPT
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=full_system,
            messages=[{"role": "user", "content": user_message}],
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
