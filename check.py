#!/usr/bin/env python3
"""Pipeline: agent description text -> extraction -> verdict -> explanation.

Used by the CLI here and by app.py (the web UI).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trifecta_checker as engine  # noqa: E402
from extract import extract  # noqa: E402
from explain import explain  # noqa: E402


def check_text(text: str, lang: str = "en", model: str = "muse-spark-1.3") -> dict:
    extracted = extract(text, model=model)
    exp = explain(extracted["verdict"], extracted["profile"], lang, model=model)
    return {
        "mode": "text",
        "profile": extracted["profile"],
        "verdict": extracted["verdict"],
        "explanation": exp["explanation"],
        "meta": {"extraction": extracted["extraction"], "explanation_tokens": exp["total_tokens"]},
    }


def check_profile(raw_profile: dict, lang: str = "en", model: str = "muse-spark-1.3") -> dict:
    profile = engine.AgentProfile.from_raw(raw_profile)
    verdict = engine.evaluate(profile)
    profile_dict = {
        "name": profile.name,
        "data_access": profile.data_access,
        "untrusted_inputs": profile.untrusted_inputs,
        "outbound": profile.outbound,
        "amplifiers": profile.amplifiers,
    }
    exp = explain(verdict, profile_dict, lang, model=model)
    return {
        "mode": "form",
        "profile": profile_dict,
        "verdict": verdict,
        "explanation": exp["explanation"],
        "meta": {"explanation_tokens": exp["total_tokens"]},
    }


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--lang", choices=["ja", "en"], default="en")
    args = ap.parse_args()
    text = Path(args.file).read_text(encoding="utf-8")
    print(json.dumps(check_text(text, lang=args.lang), ensure_ascii=False, indent=2))
