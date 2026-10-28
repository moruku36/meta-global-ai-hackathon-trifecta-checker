# Trifecta Checker — Overall Design

**English** · [日本語](architecture.ja.md) · [中文](architecture.zh.md) · [हिन्दी](architecture.hi.md) · [Español](architecture.es.md)

Status: as built and deployed, 2026-10-28.
Live demo: https://meta-global-ai-hackathon-trifecta-c.vercel.app/
Repo: https://github.com/moruku36/meta-global-ai-hackathon-trifecta-checker

## 1. Purpose

A pre-flight safety check for AI agents, aimed at non-specialists. The user
describes what their agent can do, in their own words; the checker rates
whether that combination of powers is the "lethal trifecta" (Simon
Willison) — private-data access × untrusted-content exposure × external
communication — and explains the result in plain language, with a concrete
fix (split the agent, gate the sending).

Positioning: design-time diagnosis. It complements runtime enforcement
tools (e.g. NVIDIA OpenShell) and the author's prior work
`ai-governance-control` (governance for the *development* environment).
Meta's "Agents Rule of Two" is the closest published relative of the
rating logic.

## 2. Architecture

```
Browser (single static page, chat UI)
   │  HTTPS / JSON
   ▼
Vercel serverless functions (Python, stdlib only)
   ├── POST /api/check          text ─▶ profile + verdict (+ unclear list)
   ├── POST /api/check-profile  profile ─▶ verdict        (0 LLM calls)
   ├── POST /api/explain        verdict ─▶ plain-language explanation
   └── POST /api/followup       message ─▶ conversational reply (+ action)
   │
   ▼
Meta Model API — Muse Spark 1.3 (api.meta.ai, OpenAI-compatible)
   used ONLY for: extraction, explanation, follow-up conversation
```

No database, no build step, no server-side session: the client carries the
current profile/verdict in page state and re-sends it with each call.

## 3. Components

- **`trifecta_checker.py` — deterministic rule engine.** The verdict never
  comes from an LLM. Closed capability vocabulary:
  - DATA_ACCESS {gmail_read, email_read, calendar_read, local_files,
    drive_read, contacts_read, message_read}
  - UNTRUSTED {web_browse, email_body, uploaded_files, webhook, chat_input}
  - OUTBOUND {email_send, chat_post, http_post, message_send,
    code_execute_outbound}
  - AMPLIFIERS {no_human_approval, auto_execute_code,
    long_term_memory_write}
  - Rule: 3 elements = **Lethal**; 2 elements, or 1 + amplifier =
    **Risky**; otherwise **Low**. Every verdict carries evidence (which
    token produced which element) and a separation proposal (read-only
    Reader + approval-gated Sender with an allowlist).
- **`extract.py` — Spark extraction with guardrails.** Free text → profile
  JSON restricted to the closed vocabulary. Invalid tokens trigger ONE
  repair call that shows the model the allowed vocabulary; if the output
  still doesn't fit, extraction fails loudly (no guessing). The result
  also lists `unclear` aspects — a sanitized subset of {reads_private,
  reads_untrusted, sends_out, human_approval} — naming what the
  description leaves open.
- **`explain.py` — verdict → friendly explanation.** Fixed headings in
  five languages (en/ja/zh/hi/es): Verdict / What could happen / How to
  fix it / Bottom line / Next steps. Warm, everyday-words tone; "Next
  steps" are gentle suggestions ending with ONE inviting question.
- **`check.py` — pipeline + follow-up conversation.** Splits the flow into
  `extract_and_judge` (1 LLM call), `judge_profile` (0 calls),
  `explain_result` (1 call, failure non-fatal) and `followup` (Spark
  replies in the UI language, plain words only, never raw tokens; the
  model can end with `[[SPLIT]]` to trigger the split view, or answer
  `[[NEW]]` when the user describes a different agent).
- **`llm.py` — shared Spark caller.** Hosted: `META_API_KEY` env var →
  direct call to api.meta.ai. Local dev: falls back to a vault-held key
  via a helper subprocess (the key never appears in code or logs).
- **`app.py` — the web client generator.** One static HTML page: chat-only
  UI with a mascot (Trafica), language picker driving the whole UI,
  voice input (Web Speech API), file attachment, and the ask-back logic
  described below. Attaching an MCP configuration JSON (e.g. a Claude
  Desktop / MCP client config) is summarized client-side into a plain
  description of its servers, which then goes through the normal
  extraction — so a real agent config can be checked as-is
  (`fixtures/sample_mcp_config.json`). The page footer carries the
  heuristic disclaimer and a privacy note about the demo running on
  partner credits.

## 4. Conversation design

1. **Greeting.** Trafica introduces itself: what it checks, and how to
   start (with an example sentence). Re-renders in the picked language
   until the conversation starts.
2. **Verdict in words first.** The verdict bubble leads with a spoken
   sentence ("I took a look — the verdict is Risky"), then the badge,
   friendly element chips, and a "n of 3 powers" count.
3. **Ask-back, at most ONE question.** The client mirrors the engine rule
   locally and asks only when an `unclear` aspect could actually change
   the verdict. Answers are Yes / No / Not sure chips (typing also works).
   Answering applies a representative edit and re-judges via
   /api/check-profile. Typing instead interrupts the question and
   re-extracts from the combined text.
4. **Conversation after the verdict.** Follow-ups go to Spark via
   /api/followup; "what if I split it?" shows the Reader/Sender halves
   with fresh verdicts — the demo arc Lethal → Risky + Low.

## 5. Key decisions and trade-offs

- **Determinism over cleverness.** The rating is reproducible: same
  profile, same verdict. The LLM is treated as a translator, never a
  judge. This is the product's main trust claim.
- **Loud failure over silent guessing** in extraction (repair once, then
  fail visibly).
- **Stateless hosting.** Vercel free tier, stdlib-only Python; no user
  data is stored anywhere. Descriptions go to the Meta Model API only.
- **Public-demo API guards.** All four endpoints share `api_guard.py`:
  hard caps on request-body size (64 KB) and per-field text length,
  enforced before any LLM call, plus a best-effort per-IP rate limit
  (in-process counter — stateless instances mean it blunts naive loops
  rather than guaranteeing a global limit; a hard limit would need a
  shared store such as Vercel KV). Added 2026-10-28 before opening the
  demo to public UAT.
- **Free-credit caveat.** While partner free credits are in use, submitted
  content may be used for product improvement — the UI's audience is
  expected to test with sample descriptions, and this is noted for UAT.
- **Scope honesty.** The rating is a heuristic, not a standard; the
  trifecta mainly covers data theft, not every agent risk (OWASP Agentic
  Top 10 is referenced for the wider map).

## 6. Verification

- **Engine reproducibility (no LLM):** `tests/test_engine.py` judges the six
  canonical profiles plus two boundary cases (one element + amplifier;
  no powers), each twice — 8/8 pass, byte-identical verdicts across runs.
- **Extraction:** verified 4/4 on the text fixtures (Low / Risky /
  Lethal / Lethal) against the engine's expected verdicts. A repair-path
  probe (a description that first produced an invented token) confirmed
  the repair call normalizes it into the closed vocabulary and still
  reaches the correct verdict; a profile that cannot be repaired fails
  loudly by design.
- **Open-weights path:** extraction and explanation were also run
  end-to-end on Muse Spark Open (`meta-models/muse-spark-open-1026` via
  Baseten) on 2026-10-27 — Case C extraction returned the correct
  profile, and explanations generated correctly in Japanese and English.
- Production smoke tests after each deploy: /api/check, /api/explain,
  /api/followup.

## 7. Limitations and future work

- Extraction quality depends on description quality; ask-back mitigates
  but does not eliminate this.
- Real-config import is basic: MCP configuration JSON is summarized
  client-side (server names, commands, URLs). Other export formats
  (assistant settings, agent framework configs) are not parsed yet.
- No shareable verdict card / team view yet.
- Voice input depends on browser SpeechRecognition support.
- Languages beyond the current five are future work.

## 8. Hackathon rubric mapping (self-assessment)

- **Impact (30%)**: targets the growing population of non-specialist
  agent builders; a 30-second check before an agent is wired up.
- **Meta tooling (25%)**: built on Muse Spark via the Meta Model API for
  extraction, explanation and conversation; design keeps an open-weights
  path (Muse Spark Open verified for extraction/explanation in tests).
- **Technical depth (20%)**: deterministic engine + validated extraction
  with repair, verdict-changing ask-back logic, action protocol for
  follow-ups.
- **Demo (25%)**: 3-minute arc — Lethal email agent → ask-back → split
  into Risky + Low → voice + Japanese UI.

## 9. Design grounding

The pattern above — deterministic checks own the decision, an LLM only
where judgment is needed, human approval as a gate — follows the same
pattern Meta's own hackathon workshop taught for agent design:
"Agents 102: Best Practices for Verifiable Agents Pt. 2" (Meta Global
AI Developer Hackathon live session; Yash Khare, Meta partner
engineer).

Three alignments:

- **Verification is built in, not optional.** The workshop's rule:
  verification lives inside the tool, never as a separate step the
  agent can skip. Here, the verdict is computed by
  `trifecta_checker.py` on every check — no LLM path can bypass or
  override it.
- **Deterministic first, LLM-as-judge second.** In the workshop,
  completeness and format checks are plain code; the LLM judges only
  whether a claim is actually supported. Here, the rule engine owns
  the verdict; Muse Spark only extracts the profile and explains the
  result in plain language.
- **Human approval is a gate.** The workshop ends in a human sign-off
  even after every check passes. Here, acting with no human approval
  (`no_human_approval`) is a risk amplifier in the rating itself.

The workshop's demo is also a cautionary example: the memo built in
the previous session failed verification — unsupported claims and a
broken rule. Unverified agent output ships mistakes. Trifecta Checker
applies the same lesson one step earlier: check the configuration
before the agent runs, not only the output afterwards.
