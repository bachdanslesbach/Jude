"""Ollama-backed LLM client — runs entirely on the user's machine.

When `OllamaClient` is the active backend, prompts and responses never
leave localhost. This is the strongest privacy posture Jude offers and
is intended for matters where even a contractually zero-retention
remote API is unacceptable (e.g. Belgian Art. 458 Code pénal where the
absolute interpretation requires no third party to touch client data,
period).

The trade-off is model quality: today's strongest local-runnable models
(Llama 3.3 70B, Qwen3 32B, Mistral Large) are competent but not on par
with frontier cloud models for nuanced legal reasoning. Choose this
backend when the privacy gain outweighs the analytical loss.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable

from ..types import Mode
from .base import JUDE_SYSTEM_PROMPT, LLMClient, LLMResponse


@runtime_checkable
class OllamaHttpProtocol(Protocol):
    """Minimal client interface — POST a JSON body, return parsed JSON.

    On connection refused, must raise ConnectionRefusedError.
    On 404 (model not found), must raise FileNotFoundError.
    Other errors propagate; the OllamaClient catches and rewraps them.
    """

    def post(self, url: str, payload: dict) -> dict: ...


class _UrllibClient:
    """Default HTTP client using urllib (stdlib, no extra dependencies)."""

    def post(self, url: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                detail = ""
                try:
                    detail = e.read().decode("utf-8")
                except Exception:  # noqa: BLE001
                    pass
                raise FileNotFoundError(detail or "model not found") from e
            raise
        except urllib.error.URLError as e:
            if isinstance(e.reason, ConnectionRefusedError):
                raise e.reason from e
            raise


class OllamaClient(LLMClient):
    """Talk to a local Ollama daemon over HTTP."""

    name = "ollama"
    inherently_zero_retention = True

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        http_client: OllamaHttpProtocol | None = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.http: OllamaHttpProtocol = http_client or _UrllibClient()

    def complete_chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        mode: Mode,
        zero_retention_attested: bool,
    ) -> LLMResponse:
        self._enforce_mode(mode, zero_retention_attested)

        full_system = (
            JUDE_SYSTEM_PROMPT + "\n\n" + system if system else JUDE_SYSTEM_PROMPT
        )
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": full_system}, *messages],
        }
        url = f"{self.base_url}/api/chat"

        try:
            data = self.http.post(url, payload)
        except ConnectionRefusedError as e:
            raise RuntimeError(
                f"Could not reach Ollama at {self.base_url}. Make sure the "
                f"Ollama daemon is running (`ollama serve`) and accessible "
                f"from this machine."
            ) from e
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Ollama reports the model '{self.model}' is not available "
                f"locally. Pull it with `ollama pull {self.model}` or pick a "
                f"different model in the matter settings."
            ) from e

        message = (data or {}).get("message", {}) or {}
        text = message.get("content", "") or ""
        model = (data or {}).get("model", self.model)
        return LLMResponse(
            text=text,
            model=model,
            input_tokens=_optional_int(data, "prompt_eval_count"),
            output_tokens=_optional_int(data, "eval_count"),
        )


    def stream_chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        mode: Mode,
        zero_retention_attested: bool,
    ):
        """Stream chunks from Ollama's NDJSON /api/chat endpoint."""

        self._enforce_mode(mode, zero_retention_attested)
        full_system = (
            JUDE_SYSTEM_PROMPT + "\n\n" + system if system else JUDE_SYSTEM_PROMPT
        )
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "system", "content": full_system}, *messages],
        }
        url = f"{self.base_url}/api/chat"

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=300)
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, ConnectionRefusedError):
                raise RuntimeError(
                    f"Could not reach Ollama at {self.base_url}. Make sure "
                    f"the Ollama daemon is running (`ollama serve`)."
                ) from e
            raise RuntimeError(f"Ollama stream failed: {reason}") from e
        try:
            for raw_line in resp:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = (obj.get("message") or {}).get("content") or ""
                if content:
                    yield content
                if obj.get("done"):
                    break
        finally:
            resp.close()


def _optional_int(d: dict | None, key: str) -> int | None:
    if not d or key not in d:
        return None
    val = d[key]
    return int(val) if isinstance(val, (int, float)) else None
