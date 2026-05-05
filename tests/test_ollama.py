"""Tests for the Ollama-backed LLM client.

Written test-first — at the time of this commit `jude.llm.ollama_client`
does not exist; these tests must fail (red). The next commit makes them
green.

Concept being specified
-----------------------

Ollama is a local LLM runtime (https://ollama.ai). When `OllamaClient` is
the active LLM backend, prompts and responses never leave the user's
machine. This is a stronger privacy posture than even contractually-zero-
retention APIs and is intended for matters where the user needs an
absolute "no third party touched this" guarantee.

Two consequences flow from "local by construction":

  1. Smart mode does not require a zero-retention attestation. The
     model running locally IS structurally zero-retention. The base
     class's `_enforce_mode` must therefore consult a new class
     attribute `inherently_zero_retention` and skip the attestation
     check when the subclass declares itself local.

  2. There is no API key to manage. The client only needs a base URL
     (default `http://localhost:11434`) and a model name (e.g.
     `llama3.3:70b`, `qwen3:32b`).
"""

from __future__ import annotations

import pytest

from jude.llm.base import LLMClient
from jude.llm.ollama_client import OllamaClient
from jude.types import Mode


class FakeHttpClient:
    """In-memory test double for the urllib-backed default client."""

    def __init__(self, responses: dict[str, dict] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, payload: dict) -> dict:
        self.calls.append((url, payload))
        return self.responses.get(url, {})


def _ok_response(text: str = "Hello back") -> dict:
    return {
        "model": "llama3.3:70b",
        "message": {"role": "assistant", "content": text},
        "prompt_eval_count": 10,
        "eval_count": 20,
    }


# ---------- construction ----------


def test_default_base_url_points_at_local_ollama():
    c = OllamaClient(model="llama3.3", http_client=FakeHttpClient())
    assert c.base_url == "http://localhost:11434"


def test_constructor_accepts_explicit_base_url():
    c = OllamaClient(
        model="qwen3:32b",
        base_url="http://192.168.1.10:11434",
        http_client=FakeHttpClient(),
    )
    assert c.base_url == "http://192.168.1.10:11434"
    assert c.model == "qwen3:32b"


def test_ollama_client_is_a_llmclient_subclass():
    assert issubclass(OllamaClient, LLMClient)


# ---------- the privacy posture ----------


def test_class_declares_inherent_zero_retention():
    """OllamaClient.inherently_zero_retention must be True at the class level
    so callers (and the base class's `_enforce_mode`) can rely on it."""

    assert OllamaClient.inherently_zero_retention is True


def test_smart_mode_works_without_zr_attestation():
    fake = FakeHttpClient(
        responses={"http://localhost:11434/api/chat": _ok_response()}
    )
    c = OllamaClient(model="llama3.3", http_client=fake)
    response = c.complete_chat(
        system="",
        messages=[{"role": "user", "content": "Test"}],
        mode=Mode.SMART,
        zero_retention_attested=False,  # crucially: still works
    )
    assert response.text == "Hello back"


# ---------- request shape ----------


def test_complete_chat_posts_to_chat_endpoint():
    fake = FakeHttpClient(
        responses={"http://localhost:11434/api/chat": _ok_response()}
    )
    c = OllamaClient(model="llama3.3:70b", http_client=fake)
    c.complete_chat(
        system="",
        messages=[{"role": "user", "content": "Hi"}],
        mode=Mode.STRICT,
        zero_retention_attested=False,
    )
    [(url, payload)] = fake.calls
    assert url == "http://localhost:11434/api/chat"
    assert payload["model"] == "llama3.3:70b"
    assert payload["stream"] is False


def test_jude_system_prompt_is_prepended_as_first_message():
    """The Jude system prompt explains the pseudonym convention to the LLM
    and must always be first. Ollama's `/api/chat` accepts a system message
    by setting role='system' on the first item in `messages`."""

    fake = FakeHttpClient(
        responses={"http://localhost:11434/api/chat": _ok_response()}
    )
    c = OllamaClient(model="llama3.3", http_client=fake)
    c.complete_chat(
        system="",
        messages=[{"role": "user", "content": "Hi"}],
        mode=Mode.STRICT,
        zero_retention_attested=False,
    )
    payload = fake.calls[0][1]
    assert payload["messages"][0]["role"] == "system"
    assert "pseudonym" in payload["messages"][0]["content"].lower()
    assert payload["messages"][1] == {"role": "user", "content": "Hi"}


def test_user_supplied_system_prompt_is_appended_after_jude_prompt():
    fake = FakeHttpClient(
        responses={"http://localhost:11434/api/chat": _ok_response()}
    )
    c = OllamaClient(model="llama3.3", http_client=fake)
    c.complete_chat(
        system="Matter-specific instructions: focus on antitrust.",
        messages=[{"role": "user", "content": "Q"}],
        mode=Mode.STRICT,
        zero_retention_attested=False,
    )
    sys_content = fake.calls[0][1]["messages"][0]["content"]
    assert "pseudonym" in sys_content.lower()
    assert "antitrust" in sys_content
    assert sys_content.index("pseudonym") < sys_content.index("antitrust")


def test_full_message_history_is_forwarded_in_order():
    fake = FakeHttpClient(
        responses={"http://localhost:11434/api/chat": _ok_response()}
    )
    c = OllamaClient(model="llama3.3", http_client=fake)
    c.complete_chat(
        system="",
        messages=[
            {"role": "user", "content": "First Q"},
            {"role": "assistant", "content": "First A"},
            {"role": "user", "content": "Second Q"},
        ],
        mode=Mode.STRICT,
        zero_retention_attested=False,
    )
    msgs = fake.calls[0][1]["messages"]
    # 1 system + 3 forwarded = 4
    assert len(msgs) == 4
    assert msgs[1]["content"] == "First Q"
    assert msgs[2]["content"] == "First A"
    assert msgs[3]["content"] == "Second Q"


# ---------- response shape ----------


def test_response_extracts_text_and_token_counts():
    fake = FakeHttpClient(
        responses={
            "http://localhost:11434/api/chat": {
                "model": "llama3.3:70b",
                "message": {
                    "role": "assistant",
                    "content": "Reasoned reply about Org1.",
                },
                "prompt_eval_count": 142,
                "eval_count": 87,
            }
        }
    )
    c = OllamaClient(model="llama3.3:70b", http_client=fake)
    response = c.complete_chat(
        system="",
        messages=[{"role": "user", "content": "Q"}],
        mode=Mode.STRICT,
        zero_retention_attested=False,
    )
    assert response.text == "Reasoned reply about Org1."
    assert response.model == "llama3.3:70b"
    assert response.input_tokens == 142
    assert response.output_tokens == 87


def test_response_handles_missing_token_counts():
    fake = FakeHttpClient(
        responses={
            "http://localhost:11434/api/chat": {
                "message": {"role": "assistant", "content": "ok"}
            }
        }
    )
    c = OllamaClient(model="llama3.3", http_client=fake)
    response = c.complete_chat(
        "", [{"role": "user", "content": "Q"}], Mode.STRICT, False
    )
    assert response.text == "ok"
    assert response.input_tokens is None
    assert response.output_tokens is None


# ---------- error handling ----------


def test_connection_refused_raises_actionable_error():
    """When Ollama isn't running on the configured base_url, the client must
    surface a clear, actionable error instructing the user to start Ollama
    rather than the bare urllib/socket error."""

    class Failing:
        def post(self, url, payload):
            raise ConnectionRefusedError(61)

    c = OllamaClient(model="llama3.3", http_client=Failing())
    with pytest.raises(RuntimeError, match=r"(?i)ollama"):
        c.complete_chat(
            "", [{"role": "user", "content": "Q"}], Mode.STRICT, False
        )


def test_404_for_missing_model_raises_actionable_error():
    """When the requested model isn't pulled locally, Ollama returns 404. The
    client must turn that into a clear "model not pulled" error that names
    the model, not a generic HTTP error."""

    class Returns404:
        def post(self, url, payload):
            raise FileNotFoundError("model 'qwen3:9999b' not found")

    c = OllamaClient(model="qwen3:9999b", http_client=Returns404())
    with pytest.raises(RuntimeError, match="qwen3:9999b"):
        c.complete_chat(
            "", [{"role": "user", "content": "Q"}], Mode.STRICT, False
        )
