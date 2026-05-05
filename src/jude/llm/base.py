from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from ..types import Mode


class LLMResponse(BaseModel):
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMClient(ABC):
    """Pluggable LLM backend.

    Implementations MUST refuse to send any prompt unless either:
      * the matter is in STRICT mode, or
      * the user has attested the endpoint is zero-retention, or
      * the backend is `inherently_zero_retention` (i.e. the model runs
        on the user's machine and no third party touches the prompt).
    """

    name: str = "abstract"
    # Set to True by subclasses whose endpoint is structurally zero-
    # retention (e.g. local Ollama). The base class's _enforce_mode then
    # skips the attestation check.
    inherently_zero_retention: bool = False

    @abstractmethod
    def complete_chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        mode: Mode,
        zero_retention_attested: bool,
    ) -> LLMResponse:
        """Multi-turn completion. `messages` is a list of {role, content} dicts."""

    def complete(
        self,
        system: str,
        user_message: str,
        mode: Mode,
        zero_retention_attested: bool,
    ) -> LLMResponse:
        """Single-turn convenience wrapper around `complete_chat`."""

        return self.complete_chat(
            system=system,
            messages=[{"role": "user", "content": user_message}],
            mode=mode,
            zero_retention_attested=zero_retention_attested,
        )

    def _enforce_mode(self, mode: Mode, zero_retention_attested: bool) -> None:
        if mode != Mode.SMART:
            return
        if zero_retention_attested or self.inherently_zero_retention:
            return
        raise PermissionError(
            "Refusing to send: smart mode requires either explicit "
            "zero-retention attestation or a backend that is structurally "
            "local (e.g. Ollama)."
        )


JUDE_SYSTEM_PROMPT = """\
You are a legal research and analysis assistant working under \
professional-secrecy constraints.

The user's input has been anonymized before reaching you. Real party names, \
client names, and other identifiers have been replaced by stable pseudonyms \
of the form `Person1`, `Org1`, `Loc1`, `Email1`, `Phone1`, `Iban1`, \
`Case1`, `Url1`, `Secret1` (the suffix is a sequential integer per type \
per matter). \
When the matter is in "smart" mode, the *first* mention of an entity may \
be followed by a parenthetical containing publicly known facts about that \
entity (e.g. "Org1 (a DMA-designated gatekeeper, marketplace and cloud \
business)"). Treat this parenthetical as ground truth.

Rules:
1. Do not attempt to guess the real identity behind any pseudonym, and do \
   not state or speculate about it.
2. Reason about the pseudonyms exactly as you would reason about real names: \
   discuss legal standards, weigh facts, identify counter-arguments.
3. Use the pseudonyms (not the parentheticals) when referring to entities \
   in your output. The user's tooling will translate them back automatically.
4. If a question genuinely cannot be answered without knowing the real \
   identity, say so explicitly and stop.
5. Cite legal sources by their public references (regulation numbers, case \
   citations, ECLI numbers) when possible.
"""
