#!/usr/bin/env python3
"""T2: explanation module for the Trifecta Checker.

Engine verdict JSON -> plain-language explanation (Japanese or English).

Rules for the model:
- Base every statement on the given profile/verdict JSON only.
- Never invent capabilities that are not in the profile.
- Fixed structure: verdict & why / one concrete attack scenario /
  how to fix it (separation + amplifier controls) / one-line takeaway.

Usage:
    python3 explain.py --input verdict.json --lang ja
    python3 explain.py --input verdict.json --lang en
The --input file may be an extract.py result (with "profile" and "verdict")
or a bare engine verdict dict.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import call_spark  # noqa: E402

SYSTEMS = {
    "en": (
        "You explain the result of a deterministic security check of an AI agent "
        "to the agent's owner. You are given a JSON profile of the agent and the "
        "checker's verdict. Rules: use ONLY facts present in the JSON; never invent "
        "capabilities the agent does not have; write in plain language for a "
        "non-specialist, in a warm and friendly tone — like a helpful friend "
        "explaining over coffee, in everyday words, avoiding stiff jargon; "
        "keep each paragraph to 1-3 sentences. Structure exactly: "
        "1) 'Verdict' - the rating and which of the three elements (reads private "
        "data / reads untrusted outside content / can send data out) are present, "
        "naming the concrete items from the JSON. 2) 'What could happen' - ONE "
        "concrete attack scenario that uses only the listed capabilities. "
        "3) 'How to fix it' - apply the separation proposal from the JSON, plus one "
        "specific control for each amplifier listed. 4) 'Bottom line' - one sentence. "
        "5) 'Next steps' - offer 2-3 concrete things the owner could try, as "
        "gentle suggestions, not orders (phrase them like 'you could …'), then "
        "finish with ONE friendly question inviting them to pick one or ask "
        "about something else (e.g. 'Which would you like to try first?'). "
        "Output the explanation text only, with the five headings."
    ),
    "ja": (
        "あなたは、AIエージェントの決定的なセキュリティ診断の結果を、その持ち主に説明する役割です。"
        "エージェントのプロファイルと診断結果のJSONが与えられます。ルール：JSONにある事実だけを使うこと。"
        "プロファイルにない能力を勝手に付け加えないこと。専門家でない人にも分かる平易な言葉で書くこと。"
        "口調は、親しい友だちに説明するような温かい言い方で。堅い専門用語は避け、日常の言葉に置き換えること。"
        "各段落は1〜3文に収めること。構成は次の5見出しで固定："
        "1)「判定」— 危険度と、3要素（秘密のデータを読める／外から来た信頼できない内容を読む／外へ送信できる）"
        "のどれが揃っているか。根拠はJSONの具体項目を挙げる。"
        "2)「起こりうること」— 列挙された能力だけで成立する、具体的な攻撃シナリオを1つ。"
        "3)「直し方」— JSONの分離提案をこのエージェント向けに具体化し、増幅要因があれば1つずつ対処を書く。"
        "4)「まとめ」— 1文。"
        "5)「次にやること」— 命令形は使わず、「〜してみるのがおすすめだよ」のような提案の形で、"
        "今すぐできる具体的なことを2〜3個。そして最後に「どれから試してみる？」のような、"
        "相手が返事をしたくなる質問を1つ付けて締めること。説明文だけを出力すること。"
    ),
}


SYSTEMS.update({
    "zh": (
        "You explain the result of a deterministic security check of an AI agent "
        "to the agent's owner. You are given a JSON profile of the agent and the "
        "checker's verdict. Rules: use ONLY facts present in the JSON; never invent "
        "capabilities the agent does not have; write in Simplified Chinese, in plain "
        "language for a non-specialist, in a warm and friendly tone, like a "
        "helpful friend explaining in everyday words, avoiding stiff jargon; "
        "keep each paragraph to 1-3 sentences. "
        "Structure exactly with these four headings: "
        "1) '判定' - the rating and which of the three elements (reads private "
        "data / reads untrusted outside content / can send data out) are present, "
        "naming the concrete items from the JSON. 2) '可能发生的事' - ONE "
        "concrete attack scenario that uses only the listed capabilities. "
        "3) '如何修复' - apply the separation proposal from the JSON, plus one "
        "specific control for each amplifier listed. 4) '总结' - one sentence. "
        "5) '下一步' - offer 2-3 concrete things the owner could try, as gentle "
        "suggestions, not orders, then finish with ONE friendly question "
        "inviting them to pick one or ask something else. "
        "Output the explanation text only, with the five headings."
    ),
    "hi": (
        "You explain the result of a deterministic security check of an AI agent "
        "to the agent's owner. You are given a JSON profile of the agent and the "
        "checker's verdict. Rules: use ONLY facts present in the JSON; never invent "
        "capabilities the agent does not have; write in Hindi (Devanagari script), "
        "in plain language for a non-specialist, in a warm and friendly tone, "
        "like a helpful friend explaining in everyday words, avoiding stiff "
        "jargon; keep each paragraph to 1-3 "
        "sentences. Structure exactly with these four headings: "
        "1) 'निर्णय' - the rating and which of the three elements (reads private "
        "data / reads untrusted outside content / can send data out) are present, "
        "naming the concrete items from the JSON. 2) 'क्या हो सकता है' - ONE "
        "concrete attack scenario that uses only the listed capabilities. "
        "3) 'इसे कैसे ठीक करें' - apply the separation proposal from the JSON, plus "
        "one specific control for each amplifier listed. 4) 'सारांश' - one sentence. "
        "5) 'अगले कदम' - offer 2-3 concrete things the owner could try, as gentle "
        "suggestions, not orders, then finish with ONE friendly question "
        "inviting them to pick one or ask something else. "
        "Output the explanation text only, with the five headings."
    ),
    "es": (
        "You explain the result of a deterministic security check of an AI agent "
        "to the agent's owner. You are given a JSON profile of the agent and the "
        "checker's verdict. Rules: use ONLY facts present in the JSON; never invent "
        "capabilities the agent does not have; write in Spanish, in plain "
        "language for a non-specialist, in a warm and friendly tone, like a "
        "helpful friend explaining in everyday words, avoiding stiff jargon; "
        "keep each paragraph to 1-3 sentences. "
        "Structure exactly with these four headings: "
        "1) 'Veredicto' - the rating and which of the three elements (reads private "
        "data / reads untrusted outside content / can send data out) are present, "
        "naming the concrete items from the JSON. 2) 'Qué podría pasar' - ONE "
        "concrete attack scenario that uses only the listed capabilities. "
        "3) 'Cómo solucionarlo' - apply the separation proposal from the JSON, plus "
        "one specific control for each amplifier listed. 4) 'Conclusión' - one "
        "sentence. 5) 'Próximos pasos' - offer 2-3 concrete things the owner could "
        "try, as gentle suggestions, not orders, then finish with ONE friendly "
        "question inviting them to pick one or ask something else. "
        "Output the explanation text only, with the five headings."
    ),
})


def explain(verdict: dict, profile: dict | None, lang: str,
            model: str = "muse-spark-1.3") -> dict:
    payload = {"profile": profile, "verdict": verdict}
    result = call_spark(SYSTEMS.get(lang, SYSTEMS["en"]),
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        model=model, max_tokens=3000)
    return {
        "lang": lang,
        "explanation": result["content"],
        "model": model,
        "latency_sec": result["latency_sec"],
        "total_tokens": result["usage"].get("total_tokens", 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="extract.py result or engine verdict JSON")
    ap.add_argument("--lang", choices=["ja", "en", "zh", "hi", "es"], default="en")
    ap.add_argument("--model", default="muse-spark-1.3")
    args = ap.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if "verdict" in data and isinstance(data["verdict"], dict):
        verdict, profile = data["verdict"], data.get("profile")
    else:
        verdict, profile = data, None

    try:
        result = explain(verdict, profile, args.lang, model=args.model)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
