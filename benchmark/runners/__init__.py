"""Pluggable redaction runners for the benchmark.

A runner is anything with a `name: str` attribute and a `predict(text)
-> list[PredSpan]` method. We keep this protocol-shaped (rather than
inheriting an ABC) so external systems — e.g. a HuggingFace pipeline,
a third-party API, a hand-rolled regex baseline — can plug in without
having to import benchmark internals.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schema import PredSpan


@runtime_checkable
class RunnerProtocol(Protocol):
    name: str

    def predict(self, text: str) -> list[PredSpan]: ...


__all__ = ["RunnerProtocol"]
