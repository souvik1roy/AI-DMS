"""Single point of contact with the OpenAI Chat Completions API.

Both the vision (page metadata) and reasoner (filing plan) pipeline stages
go through this module. We keep them on the OpenAI-compatible message shape
the old llama.cpp engines used, so the call sites in vision.py / thinker.py
stayed almost identical when we ripped out the local subprocess runtime.
"""
from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from dms.config import OPENAI_API_KEY

log = logging.getLogger("dms.llm")


_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Lazily construct a single shared OpenAI client. Exposed for callers
    that need direct access (e.g., audio.transcriptions in transcribe.py).
    """
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY must be set")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def chat(
    *,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    response_format: dict[str, str] | None = None,
) -> str:
    """Call the chat-completions API and return the assistant message string."""
    client = get_client()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""
