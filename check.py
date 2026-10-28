#!/usr/bin/env python3
"""Pipeline pieces for the Trifecta Checker.

Split into three steps so a web host can call them separately (each step is
short; hosted function time limits are tight):
  1. extract_and_judge(text)   -> profile + verdict   (1 LLM call)
  2. judge_profile(raw)        -> profile + verdict   (no LLM call)
  3. explain_result(verdict, profile, lang) -> plain-language text (1 LLM call)

check_text / check_profile compose all steps for CLI/local use.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trifecta_checker as engine  # noqa: E402
from extract import extract  # noqa: E402
from explain import explain  # noqa: E402


def extract_and_judge(text: str, model: str = "muse-spark-1.3") -> dict:
    extracted = extract(text, model=model)
    return {
        "mode": "text",
        "profile": extracted["profile"],
        "verdict": extracted["verdict"],
        "unclear": extracted.get("unclear", []),
        "meta": {"extraction": extracted["extraction"]},
    }


def judge_profile(raw_profile: dict) -> dict:
    profile = engine.AgentProfile.from_raw(raw_profile)
    verdict = engine.evaluate(profile)
    profile_dict = {
        "name": profile.name,
        "data_access": profile.data_access,
        "untrusted_inputs": profile.untrusted_inputs,
        "outbound": profile.outbound,
        "amplifiers": profile.amplifiers,
    }
    return {"mode": "form", "profile": profile_dict, "verdict": verdict, "meta": {}}


def explain_result(verdict: dict, profile: dict | None, lang: str = "en",
                   model: str = "muse-spark-1.3") -> dict:
    """The verdict is the product; an explanation failure must not sink it."""
    try:
        exp = explain(verdict, profile, lang, model=model)
        return {"explanation": exp["explanation"], "explanation_tokens": exp["total_tokens"]}
    except Exception as exc:
        return {"explanation": f"(Plain-language explanation is unavailable right now: {exc})",
                "explanation_tokens": 0}


FOLLOWUP_SYSTEM = (
    "You are the friendly mascot of Trifecta Checker, chatting with the owner "
    "of an AI agent you just checked. You are given the agent's profile JSON, "
    "the verdict JSON, and the user's follow-up message. Reply in the language "
    "named in the request, in a warm, friendly, spoken style, in 1-3 short "
    "sentences, using only facts from the JSON. Refer to capabilities in "
    "plain everyday words, never as raw tokens (say 'can read your Gmail', "
    "not 'gmail_read'). End with a question when it "
    "fits, so the chat keeps going. Two special actions: if the user asks to "
    "see what happens when the powers are split across two agents, or agrees "
    "to an offer to show that, end your reply with the exact token [[SPLIT]]. "
    "If the user's message actually describes a (new) agent to check — what it "
    "can read, what reaches it, what it can send — reply with ONLY the exact "
    "token [[NEW]]. Otherwise no token."
)

LANG_NAMES = {"en": "English", "ja": "Japanese", "zh": "Simplified Chinese",
              "hi": "Hindi", "es": "Spanish"}


def followup(message: str, profile: dict | None, verdict: dict | None,
             lang: str = "en", model: str = "muse-spark-1.3") -> dict:
    """Conversational reply after a verdict. Returns {reply, action} where
    action is None | 'split' | 'new'."""
    from llm import call_spark
    payload = {
        "language": LANG_NAMES.get(lang, "English"),
        "profile": profile,
        "verdict": verdict,
        "user_message": message,
    }
    result = call_spark(FOLLOWUP_SYSTEM, json.dumps(payload, ensure_ascii=False),
                        model=model, max_tokens=1200)
    text = (result["content"] or "").strip()
    action = None
    if "[[NEW]]" in text:
        action = "new"
        text = text.replace("[[NEW]]", "").strip()
    elif "[[SPLIT]]" in text:
        action = "split"
        text = text.replace("[[SPLIT]]", "").strip()
    return {"reply": text, "action": action}


def check_text(text: str, lang: str = "en", model: str = "muse-spark-1.3") -> dict:
    result = extract_and_judge(text, model=model)
    exp = explain_result(result["verdict"], result["profile"], lang, model=model)
    return {**result, "explanation": exp["explanation"],
            "meta": {**result["meta"], "explanation_tokens": exp["explanation_tokens"]}}


def check_profile(raw_profile: dict, lang: str = "en", model: str = "muse-spark-1.3") -> dict:
    result = judge_profile(raw_profile)
    exp = explain_result(result["verdict"], result["profile"], lang, model=model)
    return {**result, "explanation": exp["explanation"],
            "meta": {"explanation_tokens": exp["explanation_tokens"]}}


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--lang", choices=["ja", "en"], default="en")
    args = ap.parse_args()
    text = Path(args.file).read_text(encoding="utf-8")
    print(json.dumps(check_text(text, lang=args.lang), ensure_ascii=False, indent=2))
