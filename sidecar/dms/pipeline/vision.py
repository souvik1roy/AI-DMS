from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from dms.config import OPENAI_TEXT_MODEL, OPENAI_VISION_MODEL
from dms.llm.openai_client import chat
from dms.llm.prompts import (
    TEXT_SYSTEM,
    TEXT_USER_TEMPLATE,
    VISION_SYSTEM,
    VISION_USER_TEMPLATE,
)
from dms.pipeline.extractors import ExtractedInput

log = logging.getLogger("dms.vision")


class PageMetadata(BaseModel):
    document_type: str | None = None
    version: str | None = None
    date: str | None = None
    person_name: str | None = None
    entity_name: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    m = _JSON_RE.search(text)
    if not m:
        raise ValueError("no JSON object found in model output")
    return json.loads(m.group(0))


def _call_vision(image_url: str) -> PageMetadata:
    """Send one page image to OpenAI Vision. Retries once on JSON-parse failure."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": VISION_SYSTEM},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": VISION_USER_TEMPLATE},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]
    for attempt in range(2):
        content = chat(
            model=OPENAI_VISION_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        try:
            obj = _extract_json(content)
            return PageMetadata(**obj)
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            log.warning("vision JSON parse failed (attempt %s): %s", attempt + 1, e)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Return ONLY the JSON object. No prose. "
                            "No Markdown. No comments."
                        ),
                    }
                )
                continue
            raise
    raise RuntimeError("vision call exhausted retries without returning")


def _call_text(content: str) -> PageMetadata:
    """Send extracted text / transcript to OpenAI chat (no image)."""
    user_prompt = TEXT_USER_TEMPLATE.format(content=content or "(empty)")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": TEXT_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    for attempt in range(2):
        out = chat(
            model=OPENAI_TEXT_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        try:
            obj = _extract_json(out)
            return PageMetadata(**obj)
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            log.warning("text classify parse failed (attempt %s): %s", attempt + 1, e)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Return ONLY the JSON object. No prose. "
                            "No Markdown. No comments."
                        ),
                    }
                )
                continue
            raise
    raise RuntimeError("text-classify call exhausted retries without returning")


def _merge(first: PageMetadata, last: PageMetadata | None) -> dict[str, Any]:
    if last is None:
        return first.model_dump()
    merged = first.model_dump()
    other = last.model_dump()
    for key in ("document_type", "version", "date", "person_name", "entity_name"):
        if merged.get(key) in (None, "", "null") and other.get(key) not in (None, "", "null"):
            merged[key] = other[key]
    merged["confidence"] = max(first.confidence, last.confidence)
    if (
        first.document_type
        and last.document_type
        and first.document_type.strip().lower() != last.document_type.strip().lower()
    ):
        merged["candidates"] = sorted({first.document_type, last.document_type})
    return merged


def parse_doc(parse_input: ExtractedInput) -> dict[str, Any]:
    """Dispatch to vision or text classifier based on `parse_input.modality`.

    Returns the merged metadata dict used by the filer.
    """
    if parse_input.modality == "image":
        urls = parse_input.image_urls
        if not urls:
            raise ValueError("image-mode input had no image URLs")
        first_md = _call_vision(urls[0])
        last_md = _call_vision(urls[1]) if len(urls) > 1 else None
        return _merge(first_md, last_md)
    # text mode
    return _call_text(parse_input.text_excerpt).model_dump()
