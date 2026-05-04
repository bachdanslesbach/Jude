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

    Implementations MUST refuse to send any prompt unless
    `zero_retention_attested` is True when the matter is in SMART mode.
    """

    name: str = "abstract"

    @abstractmethod
    def complete(
        self,
        system: str,
        user_message: str,
        mode: Mode,
        zero_retention_attested: bool,
    ) -> LLMResponse: ...

    @staticmethod
    def _enforce_mode(mode: Mode, zero_retention_attested: bool) -> None:
        if mode == Mode.SMART and not zero_retention_attested:
            raise PermissionError(
                "Refusing to send: smart mode requires explicit "
                "zero-retention attestation for this LLM endpoint."
            )


JUDE_SYSTEM_PROMPT = """\
You are a legal research and analysis assistant working under \
professional-secrecy constraints.

The user's input has been anonymized before reaching you. Real party names, \
client names, and other identifiers have been replaced by stable pseudonyms \
of the form `Person_NNN`, `Org_NNN`, `Loc_NNN`, `Email_NNN`, `Phone_NNN`, \
`Iban_NNN`, `Case_NNN`, `Url_NNN`. When the matter is in "smart" mode, the \
*first* mention of an entity may be followed by a parenthetical containing \
publicly known facts about that entity (e.g. "Org_001 (a DMA-designated \
gatekeeper, marketplace and cloud business)"). Treat this parenthetical as \
ground truth.

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
