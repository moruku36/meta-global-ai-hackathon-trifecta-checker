"""Shared request guards for the public demo API.

Two layers, both applied before any LLM call:

1. Hard caps (reliable on serverless): request-body size and per-field
   text length. Oversized requests are rejected without calling the LLM,
   which stops giant-payload abuse and most scripted credit burn.

2. Best-effort per-IP rate limiting: an in-process counter. Serverless
   instances are stateless, so this does NOT guarantee a global limit —
   it only blunts naive request loops that land on the same instance.
   A hard global limit would need a shared store (e.g. Vercel KV).
"""
from __future__ import annotations

import json
import time

MAX_BODY_BYTES = 65536        # 64 KB request body, hard cap
MAX_TEXT_CHARS = 8000         # /api/check "text"
MAX_MESSAGE_CHARS = 4000      # /api/followup "message"
MAX_PAYLOAD_CHARS = 16000     # serialized profile / verdict payloads
RATE_LIMIT = 60               # requests per window per IP (best effort)
RATE_WINDOW = 60.0            # seconds

_hits: dict[str, list[float]] = {}


class GuardError(ValueError):
    """A request exceeded a guard; the message is user-facing."""


def check_body_size(content_length: int) -> None:
    if content_length > MAX_BODY_BYTES:
        raise GuardError(
            "That request is too large — please shorten the text a little "
            "and try again.")


def check_text(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    if len(text) > limit:
        raise GuardError(
            "That text is a bit too long — please shorten it and try again.")
    return text


def check_payload(obj) -> None:
    if obj is None:
        return
    if len(json.dumps(obj, ensure_ascii=False)) > MAX_PAYLOAD_CHARS:
        raise GuardError(
            "That request is too large — please start a new check and "
            "try again.")


def client_ip(headers) -> str:
    xff = headers.get("x-forwarded-for") or ""
    if xff:
        return xff.split(",")[0].strip()
    return headers.get("x-real-ip") or "unknown"


def check_rate(headers) -> None:
    ip = client_ip(headers)
    now = time.monotonic()
    recent = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
    if len(recent) >= RATE_LIMIT:
        _hits[ip] = recent
        raise GuardError(
            "Lots of requests in a row — please wait a moment and "
            "try again.")
    recent.append(now)
    _hits[ip] = recent
