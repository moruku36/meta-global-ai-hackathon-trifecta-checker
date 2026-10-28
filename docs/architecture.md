# Trifecta Checker — Overall Design

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
  voice input (Web Speech API), text-file attachment, and the ask-back
  logic described below.

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
- **Free-credit caveat.** While partner free credits are in use, submitted
  content may be used for product improvement — the UI's audience is
  expected to test with sample descriptions, and this is noted for UAT.
- **Scope honesty.** The rating is a heuristic, not a standard; the
  trifecta mainly covers data theft, not every agent risk (OWASP Agentic
  Top 10 is referenced for the wider map).

## 6. Verification

- Six fixture cases (incl. the split "after" states) with expected
  verdicts; extraction verified 4/4 on the text fixtures plus a
  repair-path probe.
- Production smoke tests after each deploy: /api/check, /api/explain,
  /api/followup.
- Project rule: personal-development verification stays within ~10 runs
  per task (representative + boundary cases, not commercial-scale
  regression).

## 7. Limitations and future work

- Extraction quality depends on description quality; ask-back mitigates
  but does not eliminate this.
- No direct import of real agent configs yet (MCP manifests, assistant
  settings exports) — the natural next step.
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
