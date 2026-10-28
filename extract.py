#!/usr/bin/env python3
"""T1: extraction module for the Trifecta Checker.

Free-text agent description -> validated AgentProfile JSON -> engine verdict.

Design (fixed at the 2026-10-28 lead decision):
- The LLM (Muse Spark 1.3 via the Meta Model API) only extracts.
- The verdict comes from the deterministic engine (trifecta_checker.py).
- Extraction output is validated against the engine's closed vocabulary.
  Unknown or misplaced tokens trigger ONE repair call that shows the model
  the allowed vocabulary; if the output is still invalid, extraction fails
  loudly so the caller can fall back to structured (form) input.

Usage:
    python3 extract.py --file fixtures/case_c.txt
    python3 extract.py --text "Agent that reads my Gmail and ..."
    python3 extract.py --file ... --model muse-spark-1.3
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trifecta_checker as engine  # noqa: E402

META_HELPER = "/home/hatch/workspace/custom-connectors/custom.meta-model-api/bin/meta_chat.py"

SYSTEM = (
    "You convert a free-text description of an AI agent's configuration into a "
    "strict JSON profile. Output JSON only, no commentary. Schema: "
    '{"name": string, '
    '"data_access": [..], "untrusted_inputs": [..], "outbound": [..], "amplifiers": [..]}. '
    "Use short snake_case tokens. data_access = private data the agent can read "
    "(e.g. gmail_read, email_read, calendar_read, local_files). "
    "untrusted_inputs = channels where outside parties can place content the agent "
    "will read (e.g. web_browse, email_body, uploaded_files). "
    "outbound = ways the agent can send data or messages out (e.g. email_send, "
    "message_send, http_post). "
    "amplifiers = risk multipliers (e.g. no_human_approval, auto_execute_code, "
    "long_term_memory_write). Include a category only when the description supports it."
)

VOCAB = {
    "data_access": engine.DATA_ACCESS,
    "untrusted_inputs": engine.UNTRUSTED_INPUTS,
    "outbound": engine.OUTBOUND,
    "amplifiers": engine.AMPLIFIERS,
}


def call_llm(system: str, prompt: str, model: str, max_tokens: int = 4096) -> dict:
    cmd = [
        sys.executable, META_HELPER,
        "--model", model,
        "--system", system,
        "--prompt", prompt,
        "--reasoning-effort", "low",
        "--max-tokens", str(max_tokens),
    ]
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    latency = time.time() - start
    if proc.returncode != 0:
        raise RuntimeError(f"LLM helper failed rc={proc.returncode}: {proc.stderr.strip()[:400]}")
    envelope = json.loads(proc.stdout)
    if not envelope.get("ok"):
        raise RuntimeError(f"LLM call not ok: {json.dumps(envelope)[:400]}")
    return {
        "content": envelope.get("content", ""),
        "usage": envelope.get("usage", {}),
        "latency_sec": round(latency, 1),
    }


def parse_profile_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def find_invalid_tokens(raw: dict) -> dict:
    """Return {field: [tokens]} that the engine would silently drop or that
    sit in the wrong field. Mirrors trifecta_checker._canon normalisation."""
    invalid = {}
    for field_name, allowed in VOCAB.items():
        bad = []
        for token in raw.get(field_name) or []:
            key = str(token).strip().lower().replace(" ", "_").replace("-", "_")
            key = engine._SYNONYMS.get(key, key)
            if key not in allowed:
                bad.append(str(token))
        if bad:
            invalid[field_name] = bad
    return invalid


def extract(text: str, model: str = "muse-spark-1.3") -> dict:
    calls = []
    first = call_llm(SYSTEM, text, model)
    calls.append(first)
    raw = parse_profile_json(first["content"])
    invalid = find_invalid_tokens(raw)

    repaired = False
    if invalid:
        vocab_text = "; ".join(
            f"{field}: {', '.join(sorted(tokens))}" for field, tokens in VOCAB.items()
        )
        repair_prompt = (
            f"Agent description:\n{text}\n\n"
            f"Your previous JSON output was:\n{json.dumps(raw, ensure_ascii=False)}\n\n"
            f"These tokens are outside the allowed vocabulary or in the wrong "
            f"field: {json.dumps(invalid, ensure_ascii=False)}.\n"
            f"Allowed vocabulary — {vocab_text}.\n"
            "Map each capability to the closest allowed token, drop anything "
            "that has no allowed equivalent, and output the corrected JSON only."
        )
        second = call_llm(SYSTEM, repair_prompt, model)
        calls.append(second)
        raw = parse_profile_json(second["content"])
        invalid = find_invalid_tokens(raw)
        repaired = True
        if invalid:
            raise ValueError(f"extraction still invalid after repair: {invalid}")

    profile = engine.AgentProfile.from_raw(raw)
    verdict = engine.evaluate(profile)
    return {
        "profile": {
            "name": profile.name,
            "data_access": profile.data_access,
            "untrusted_inputs": profile.untrusted_inputs,
            "outbound": profile.outbound,
            "amplifiers": profile.amplifiers,
        },
        "verdict": verdict,
        "extraction": {
            "model": model,
            "repaired": repaired,
            "calls": len(calls),
            "latency_sec": sum(c["latency_sec"] for c in calls),
            "total_tokens": sum(c["usage"].get("total_tokens", 0) for c in calls),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="path to a text file with the agent description")
    ap.add_argument("--text", help="agent description text")
    ap.add_argument("--model", default="muse-spark-1.3")
    args = ap.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        ap.error("either --file or --text is required")

    try:
        result = extract(text, model=args.model)
    except Exception as exc:  # surfaced to the caller for form fallback
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
