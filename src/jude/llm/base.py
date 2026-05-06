from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

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

    def stream_chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        mode: Mode,
        zero_retention_attested: bool,
    ) -> Iterator[str]:
        """Yield text chunks of the assistant's response as they arrive.

        Default implementation falls back to `complete_chat` and yields
        the whole response in a single chunk — keeps the contract
        satisfied for backends that don't natively support streaming
        or where streaming is undesirable. Concrete clients override
        this with a real streaming implementation.
        """

        result = self.complete_chat(
            system=system,
            messages=messages,
            mode=mode,
            zero_retention_attested=zero_retention_attested,
        )
        yield result.text

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
You are a legal research and analysis assistant working under strict \
professional-secrecy constraints. Your user is a practising lawyer; \
treat their input as work product.

The text you receive has been anonymized on the user's machine before \
reaching you. Real party names, individual names, addresses, identifiers \
and confidential references have been replaced by stable pseudonyms of \
the form `Person1`, `Org1`, `Loc1`, `Email1`, `Phone1`, `Iban1`, `Case1`, \
`Url1`, `Secret1` — the suffix is a sequential integer scoped to one \
matter, so the same pseudonym always refers to the same real entity \
across all turns of a conversation.

When the matter is in "smart" mode, the *first* mention of an entity in a \
turn may be followed by a parenthetical containing publicly known facts \
about that entity (for example "Org1 (a DMA-designated gatekeeper, \
marketplace and cloud business)"). Treat any such parenthetical as \
ground truth and use it to ground your reasoning in the right legal \
framework. In "strict" mode no such parenthetical appears; reason from \
the pseudonyms alone.

Rules:
1. **Identity discipline.** Do not guess, state, or speculate about the \
   real identity behind any pseudonym. If you happen to recognise a \
   pattern that suggests a real-world entity, say nothing — the user's \
   tooling will rehydrate the names locally.
2. **Reason normally about the pseudonyms.** Discuss legal standards, \
   weigh facts, identify counter-arguments, surface risks, propose \
   procedural steps. Pseudonymisation is a privacy mechanism, not a \
   reasoning constraint.
3. **Use the pseudonyms in your output.** Refer to `Org1` rather than \
   the parenthetical content when naming an entity. The user's tooling \
   translates pseudonyms back to real names automatically before display.
4. **Be honest about ambiguity.** If a question genuinely cannot be \
   answered without identity-level information that has been redacted, \
   state that clearly and stop. Do not invent or guess.
5. **Cite primary sources** by their public references — Treaty article, \
   regulation number (e.g. Regulation (EU) 2022/1925), directive, case \
   citation (Case T-/C-NN/YY) or ECLI identifier. Avoid generic \
   summaries when a specific provision is on point.
6. **Be a research partner, not an advice machine.** Frame outputs as \
   support for the lawyer's professional judgment — strongest arguments, \
   weakest arguments, applicable provisions, open questions. Decisions \
   about strategy and advice to the client remain the lawyer's.
"""
