"""
Trifecta Checker — deterministic rule-engine core.

Checks an AI agent configuration against the "lethal trifecta"
(Simon Willison): the combination of
  (1) access to sensitive data
  (2) exposure to untrusted content
  (3) outbound / external-send capability
is what makes prompt injection catastrophic instead of merely possible.

Verdicts:
  - Lethal: all 3 elements present
  - Risky:  2 elements present, OR 1 element + an amplifier
            (no_human_approval, auto_execute_code, long_term_memory_write)
  - Low:    1 element or fewer, with no amplifier

The engine is deliberately independent of any LLM: same input, same
verdict, every time. An LLM layer (Muse Spark) is used only to extract
an AgentProfile from pasted free-text configs and to explain verdicts
in plain language — never to decide the verdict itself.

Built for the Meta Global AI Developer Hackathon (Oct-Nov 2026).
Run this file directly to execute the built-in fixture self-test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# Canonical token sets. Synonyms are normalised to these on input.
DATA_ACCESS = {
    "gmail_read", "email_read", "calendar_read", "local_files",
    "drive_read", "contacts_read", "message_read",
}
UNTRUSTED_INPUTS = {
    "web_browse", "email_body", "uploaded_files", "webhook", "chat_input",
}
OUTBOUND = {
    "email_send", "chat_post", "http_post", "message_send", "code_execute_outbound",
}
AMPLIFIERS = {
    "no_human_approval", "auto_execute_code", "long_term_memory_write",
}

_SYNONYMS = {
    # data access
    "gmail": "gmail_read", "mail_read": "email_read", "calendar": "calendar_read",
    "files": "local_files", "local_file_read": "local_files",
    # untrusted
    "web": "web_browse", "email": "email_body", "uploads": "uploaded_files",
    # outbound
    "send_email": "email_send", "send_message": "message_send",
    "post": "chat_post", "http": "http_post",
    # amplifiers
    "auto_run": "auto_execute_code", "no_approval": "no_human_approval",
    "persistent_memory": "long_term_memory_write",
}


def _canon(tokens, allowed) -> List[str]:
    out = []
    for t in tokens or []:
        key = str(t).strip().lower().replace(" ", "_").replace("-", "_")
        key = _SYNONYMS.get(key, key)
        if key in allowed and key not in out:
            out.append(key)
    return sorted(out)


@dataclass
class AgentProfile:
    name: str = ""
    data_access: List[str] = field(default_factory=list)
    untrusted_inputs: List[str] = field(default_factory=list)
    outbound: List[str] = field(default_factory=list)
    amplifiers: List[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Dict) -> "AgentProfile":
        return cls(
            name=str(raw.get("name", "")),
            data_access=_canon(raw.get("data_access"), DATA_ACCESS),
            untrusted_inputs=_canon(raw.get("untrusted_inputs"), UNTRUSTED_INPUTS),
            outbound=_canon(raw.get("outbound"), OUTBOUND),
            amplifiers=_canon(raw.get("amplifiers"), AMPLIFIERS),
        )


def evaluate(profile: AgentProfile) -> Dict:
    elements = {
        "data_access": bool(profile.data_access),
        "untrusted_input": bool(profile.untrusted_inputs),
        "outbound": bool(profile.outbound),
    }
    count = sum(elements.values())
    if count == 3:
        verdict = "Lethal"
    elif count == 2 or (count == 1 and profile.amplifiers):
        verdict = "Risky"
    else:
        verdict = "Low"

    proposal = []
    if verdict in ("Lethal", "Risky"):
        proposal = [
            "Split into a read-only Reader (data + untrusted input, no outbound)",
            "and a Sender that only sends after human approval, with an allowlist",
            "of destinations. Never let one agent hold all three elements.",
        ]
    return {
        "name": profile.name,
        "verdict": verdict,
        "elements": elements,
        "element_count": count,
        "amplifiers": profile.amplifiers,
        "evidence": {
            "data_access": profile.data_access,
            "untrusted_inputs": profile.untrusted_inputs,
            "outbound": profile.outbound,
        },
        "separation_proposal": proposal,
    }


# Demo fixtures from build-prep-20261027.md §6.
FIXTURES = {
    "Case A (Low)": {
        "name": "local memo summariser",
        "data_access": ["local_files"],
        "untrusted_inputs": [],
        "outbound": [],
        "amplifiers": [],
    },
    "Case B (Risky)": {
        "name": "web researcher with mail read",
        "data_access": ["email_read"],
        "untrusted_inputs": ["web_browse", "email_body"],
        "outbound": [],
        "amplifiers": [],
    },
    "Case C (Lethal)": {
        "name": "all-in-one mail agent",
        "data_access": ["gmail_read"],
        "untrusted_inputs": ["web_browse", "email_body"],
        "outbound": ["email_send"],
        "amplifiers": ["no_human_approval"],
    },
    "Case D (Lethal, everyday)": {
        "name": "personal assistant",
        "data_access": ["calendar_read", "email_read"],
        "untrusted_inputs": ["email_body"],
        "outbound": ["message_send"],
        "amplifiers": [],
    },
}

EXPECTED = {
    "Case A (Low)": "Low",
    "Case B (Risky)": "Risky",
    "Case C (Lethal)": "Lethal",
    "Case D (Lethal, everyday)": "Lethal",
}


if __name__ == "__main__":
    import json

    for label, raw in FIXTURES.items():
        result = evaluate(AgentProfile.from_raw(raw))
        assert result["verdict"] == EXPECTED[label], (label, result)
        print(f"{label}: {result['verdict']} "
              f"(elements={result['element_count']}, "
              f"amplifiers={result['amplifiers'] or 'none'})")
    print("All 4 fixtures pass. JSON example (Case C):")
    print(json.dumps(evaluate(AgentProfile.from_raw(FIXTURES["Case C (Lethal)"])),
                     ensure_ascii=False, indent=2))
