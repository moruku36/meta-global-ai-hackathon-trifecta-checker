"""Reproducibility and correctness tests for the deterministic engine.

No LLM calls: this tests `trifecta_checker.evaluate` only.
Claims verified:
  1. Every canonical case gets its expected verdict.
  2. Reproducibility: judging the same profile twice yields identical
     output (the verdict never depends on an LLM or on call order).
  3. Boundary rules: 1 element + amplifier = Risky; 1 element alone = Low;
     0 elements = Low; the split "after" states rate safer than Case C.

Run: python3 tests/test_engine.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import trifecta_checker as engine

CASES = [
    ("A: local memo summariser",
     {"name": "case_a", "data_access": ["local_files"],
      "untrusted_inputs": [], "outbound": [], "amplifiers": []},
     "Low"),
    ("B: mail + web reader, cannot send",
     {"name": "case_b", "data_access": ["email_read"],
      "untrusted_inputs": ["web_browse"], "outbound": [], "amplifiers": []},
     "Risky"),
    ("C: mail agent that sends on its own",
     {"name": "case_c", "data_access": ["email_read"],
      "untrusted_inputs": ["email_body"], "outbound": ["email_send"],
      "amplifiers": ["no_human_approval"]},
     "Lethal"),
    ("D: everyday assistant that sends chat messages",
     {"name": "case_d", "data_access": ["message_read"],
      "untrusted_inputs": ["chat_input"], "outbound": ["message_send"],
      "amplifiers": []},
     "Lethal"),
    ("C-fixed reader (after the split)",
     {"name": "case_c_fixed_reader", "data_access": ["email_read"],
      "untrusted_inputs": ["email_body"], "outbound": [], "amplifiers": []},
     "Risky"),
    ("C-fixed sender (after the split, approval-gated)",
     {"name": "case_c_fixed_sender", "data_access": [],
      "untrusted_inputs": [], "outbound": ["email_send"], "amplifiers": []},
     "Low"),
    ("Boundary: one element + amplifier",
     {"name": "edge_amp", "data_access": ["drive_read"],
      "untrusted_inputs": [], "outbound": [],
      "amplifiers": ["auto_execute_code"]},
     "Risky"),
    ("Boundary: no powers at all",
     {"name": "edge_none", "data_access": [], "untrusted_inputs": [],
      "outbound": [], "amplifiers": []},
     "Low"),
]


def main() -> int:
    failures = 0
    for label, raw, expected in CASES:
        profile = engine.AgentProfile.from_raw(raw)
        first = engine.evaluate(profile)
        second = engine.evaluate(profile)
        stable = json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
        ok = first["verdict"] == expected and stable
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {label}: verdict={first['verdict']} "
              f"(expected {expected}), reproducible={stable}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
