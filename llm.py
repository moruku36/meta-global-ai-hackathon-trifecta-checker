#!/usr/bin/env python3
"""Shared Muse Spark caller for the Trifecta Checker.

Two routes, chosen by environment:
- META_API_KEY set (e.g. a Hugging Face Space Secret): call the Meta Model
  API directly at https://api.meta.ai/v1 (OpenAI-compatible).
- Otherwise (local development): go through the Muse-side connector helper,
  which reads the key from the secure vault.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

HELPER = "/home/hatch/workspace/custom-connectors/custom.meta-model-api/bin/meta_chat.py"
BASE = os.environ.get("META_API_BASE", "https://api.meta.ai/v1")


def call_spark(system: str, prompt: str, model: str = "muse-spark-1.3",
               max_tokens: int = 4096, reasoning_effort: str = "low") -> dict:
    key = os.environ.get("META_API_KEY")
    if key:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "reasoning_effort": reasoning_effort,
            "max_tokens": max_tokens,
        }
        req = urllib.request.Request(
            BASE + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}"},
        )
        start = time.time()
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.load(resp)
        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "latency_sec": round(time.time() - start, 1),
        }

    cmd = [
        sys.executable, HELPER,
        "--model", model,
        "--system", system,
        "--prompt", prompt,
        "--reasoning-effort", reasoning_effort,
        "--max-tokens", str(max_tokens),
    ]
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    latency = round(time.time() - start, 1)
    if proc.returncode != 0:
        raise RuntimeError(f"LLM helper failed rc={proc.returncode}: {proc.stderr.strip()[:400]}")
    envelope = json.loads(proc.stdout)
    if not envelope.get("ok"):
        raise RuntimeError(f"LLM call not ok: {json.dumps(envelope)[:400]}")
    return {
        "content": envelope.get("content", ""),
        "usage": envelope.get("usage", {}),
        "latency_sec": latency,
    }
