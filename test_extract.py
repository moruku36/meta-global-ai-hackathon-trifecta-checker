#!/usr/bin/env python3
"""End-to-end test for T1: fixture texts -> extraction -> engine verdict.

Expected verdicts mirror the engine fixtures (trifecta_checker.FIXTURES):
A Low / B Risky / C Lethal / D Lethal.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import extract  # noqa: E402

CASES = [
    ("case_a.txt", "Low"),
    ("case_b.txt", "Risky"),
    ("case_c.txt", "Lethal"),
    ("case_d.txt", "Lethal"),
]


def main() -> int:
    fixtures = Path(__file__).resolve().parent / "fixtures"
    failures = 0
    for filename, expected in CASES:
        text = (fixtures / filename).read_text(encoding="utf-8")
        try:
            result = extract(text)
            verdict = result["verdict"]["verdict"]
            meta = result["extraction"]
            status = "PASS" if verdict == expected else "FAIL"
            if verdict != expected:
                failures += 1
            print(f"{status} {filename}: verdict={verdict} (expected {expected}) "
                  f"elements={result['verdict']['element_count']} "
                  f"repaired={meta['repaired']} calls={meta['calls']} "
                  f"tokens={meta['total_tokens']} latency={meta['latency_sec']}s")
            print(f"     profile={result['profile']}")
        except Exception as exc:
            failures += 1
            print(f"ERROR {filename}: {exc}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
