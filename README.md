# Trifecta Checker

**A pre-flight safety check for AI agents.** Describe what your agent can do —
Trifecta Checker tells you whether that combination of powers is safe, why,
and how to split it up if it is not.

Built for the Meta Global AI Developer Hackathon (Oct–Nov 2026).

**Live demo:** https://meta-global-ai-hackathon-trifecta-c.vercel.app/

**Read this in your language:** [English](#trifecta-checker) · [日本語](#日本語) · [中文](#中文) · [हिन्दी](#हिन्दी) · [Español](#español)

---

### 日本語

Trifecta Checker は AIエージェントのための離陸前チェックです。Trafica に話しかけるだけで使えて、フォームも専門用語もいりません。エージェントの内容を自分の言葉で伝えるだけ（テキスト入力、マイク、ファイル読み込みに対応。テキストの説明文でも、MCP 設定の JSON でも、そのまま要約して判定します）。結果は Low・Risky・Lethal の3段階で、根拠になった「できること」と、何が起きうるか・どう直すかをやさしい言葉で教えてくれます。判定を左右しそうな点があれば当てずっぽうで決めず、Trafica がひとつだけ聞き返します。「分割したら？」と聞けば、読み取り専用 Reader と承認付き Sender に分けた案を、それぞれの判定付きで見せてくれます。

カギは、3つの力が1か所に集まると危険になるという考え方です。(1) プライベートなデータを読む（メール・ファイル・予定など）、(2) 信頼できない情報を読む（メッセージ本文・Webページ・添付など、攻撃者が罠を仕込める場所）、(3) 外に送り出せる（メール送信・投稿・外部APIなど）。3つそろうと、1通の毒入りメッセージにだまされて情報を漏らしかねません。判定は LLM ではなく小さな決定論的ルールエンジンが行うため、同じ条件ならいつも同じ結果になります。Muse Spark は翻訳役だけです — 説明文を構造化プロフィールに、判定結果をやさしい言葉に変えます。

- Lethal（致命的）: 3つすべて該当
- Risky（要注意）: 2つ該当、または1つ＋増幅要素あり（人の承認なし、コード自動実行、長期メモリへの書き込みなど）
- Low（低リスク）: 1つ以下で、増幅要素なし

Live demo: https://meta-global-ai-hackathon-trifecta-c.vercel.app/

### 中文

Trifecta Checker 是 AI 智能体的起飞前安全检查。不用填表，也不用懂安全术语，直接和 Trafica 聊天就行。用自己的话描述你的智能体：打字、语音输入，或上传文件（纯文本描述，或 MCP 配置 JSON，其中的 servers 会原样汇总并检查）。你会得到通俗易懂的结论 —— Low、Risky 或 Lethal，并附上它拥有的能力、用大白话讲清哪里可能出问题、该怎么修。如果某个细节会影响结论，Trafica 会追问一句，而不会瞎猜。你还可以继续聊，比如问“拆开会怎样？”，Trafica 会给出拆分方案——只读的 Reader 和需审批的 Sender——并分别给出新的结论。

核心理念是 lethal trifecta：当三种能力集中在一个智能体身上时就会很危险——（1）读隐私数据（邮件、文件、日历），（2）读不可信内容（消息正文、网页、上传文件，攻击者可在其中植入指令），（3）能向外发数据（发邮件、发消息、调用外部 API）。三者齐全时，一条恶意消息就能骗智能体泄露你的数据。结论判定不靠 LLM：小型确定性规则引擎负责套用规则，同一画像结论永远一致。Muse Spark 只负责翻译——把描述转成结构化画像，再把结论翻回大白话。

- **Lethal（致命）**：三项全占。
- **Risky（高风险）**：占两项，或一项加风险放大器（无需人工确认、自动执行代码、写入长期记忆）。
- **Low（低风险）**：至多一项，且无放大器。

Live demo: https://meta-global-ai-hackathon-trifecta-c.vercel.app/

### हिन्दी

Trifecta Checker AI एजेंट्स के लिए उड़ान से पहले की सुरक्षा जांच है। आप Trafica से बात करते हैं, एक दोस्ताना चेकर — कोई फॉर्म नहीं, कोई सुरक्षा शब्दावली नहीं चाहिए। अपने एजेंट को अपने शब्दों में बताइए (टाइप करें, माइक से बोलें, या फाइल लोड करें: सादा टेक्स्ट विवरण, या MCP कॉन्फ़िगरेशन JSON, जिसके सर्वर ज्यों के त्यों सारांशित और जांचे जाते हैं)। आपको सीधी भाषा में फैसला मिलता है — Low, Risky या Lethal — उसके पीछे की शक्तियों के साथ, और आम भाषा में व्याख्या कि क्या गलत हो सकता है और इसे कैसे ठीक करें। अगर कोई जानकारी फैसला बदल सकती है, तो Trafica अंदाजा लगाने के बजाय एक सवाल पूछता है। आप बात जारी रख सकते हैं: पूछिए "अगर मैं इसे बांट दूं तो?" और Trafica बंटवारा दिखाता है — सिर्फ पढ़ने वाला Reader और मंजूरी वाला Sender — हर आधे हिस्से के नए फैसले के साथ।

इसके पीछे lethal trifecta का आइडिया है: एजेंट खतरनाक हो जाता है जब तीन शक्तियां एक जगह मिल जाती हैं — (1) वह निजी डेटा पढ़ता है (मेल, फाइल, कैलेंडर), (2) वह अविश्वसनीय कंटेंट पढ़ता है (मैसेज, वेब पेज, अपलोड, जहां हमलावर निर्देश छिपा सकता है), और (3) वह डेटा बाहर भेज सकता है (मेल भेजना, मैसेज पोस्ट करना, बाहरी API कॉल करना)। तीनों के साथ, एक जहरीला मैसेज एजेंट को बहकाकर आपका डेटा लीक करा सकता है। फैसला कभी LLM से नहीं आता: एक छोटा तय नियम-इंजन नियम लागू करता है, इसलिए एक ही प्रोफाइल को हमेशा एक ही फैसला मिलता है। Muse Spark सिर्फ अनुवाद करता है — विवरण को व्यवस्थित प्रोफाइल में, और फैसले को वापस सरल भाषा में।

- **Lethal (घातक)** — तीनों तत्व मौजूद।
- **Risky (जोखिम-भरा)** — दो तत्व, या एक तत्व साथ में रिस्क बढ़ाने वाला कारण (बिना इंसानी मंजूरी, खुद चलने वाला कोड, लंबी याददाश्त में लिखना)।
- **Low (कम)** — एक या उससे कम तत्व, कोई बढ़ाने वाला कारण नहीं।

Live demo: https://meta-global-ai-hackathon-trifecta-c.vercel.app/

### Español

Trifecta Checker es una revisión de seguridad previa al vuelo para agentes de IA. Hablas con Trafica, un personaje amable que te guía — sin formularios ni vocabulario de seguridad. Describe tu agente con tus palabras (escríbelo, dilo con el micrófono o carga un archivo: una descripción en texto plano o un JSON de configuración MCP, cuyos servidores se resumen y analizan tal cual). Recibes un veredicto en lenguaje claro — Low, Risky o Lethal — con los poderes detectados y una explicación sencilla de qué podría salir mal y cómo arreglarlo. Si un detalle puede cambiar el veredicto, Trafica te hace una pregunta en vez de adivinar. Puedes seguir conversando: pregunta «¿y si lo divido?» y Trafica te muestra la división — un Reader de solo lectura y un Sender con aprobación — con veredictos nuevos para cada parte.

La idea es la trifecta letal: un agente se vuelve peligroso cuando reúne tres poderes en un mismo lugar — (1) lee datos privados (correo, archivos, calendario), (2) lee contenido no confiable (mensajes, páginas web, archivos subidos, donde un atacante puede plantar instrucciones) y (3) puede enviar datos hacia afuera (enviar correos, publicar mensajes, llamar a APIs externas). Con los tres, un solo mensaje envenenado puede convencer al agente de filtrar tus datos. El veredicto no lo decide un LLM: un pequeño motor de reglas determinista aplica las reglas, así el mismo perfil siempre recibe el mismo veredicto. Muse Spark solo traduce — la descripción a un perfil estructurado, y el veredicto de vuelta a lenguaje claro.

- **Lethal (letal):** reúne los tres poderes.
- **Risky (riesgoso):** reúne dos poderes, o un poder más un amplificador (sin aprobación humana, código que se autoejecuta, escritura en memoria permanente).
- **Low (bajo):** un poder o menos, sin amplificadores.

Demo en vivo: https://meta-global-ai-hackathon-trifecta-c.vercel.app/

---

## What it is like to use

You chat with **Trafica**, a friendly checker character — no forms, no
security vocabulary needed:

1. **Describe your agent in your own words.** Type it, tap 🎤 and talk, or
   tap + and load a file: a plain text description, or an **MCP
   configuration JSON** — its servers are summarized into a description
   and checked as-is (try `fixtures/sample_mcp_config.json`).
2. **Get a verdict in plain words** — Low, Risky or Lethal — with the powers
   behind it and an everyday-language explanation of what could go wrong
   and how to fix it.
3. **If a detail could change the verdict, Trafica asks one question back**
   instead of guessing. Answer with a tap or by typing.
4. **Keep talking.** Ask "what if I split it?" and Trafica shows the split —
   a read-only Reader and an approval-gated Sender — with fresh verdicts for
   each half.

The whole conversation works in five languages: English, Japanese, Chinese,
Hindi and Spanish.

## The idea: the lethal trifecta

An agent becomes dangerous when three powers meet in one place:

1. **It reads private data** (your mail, files, calendar…)
2. **It reads untrusted content** (message bodies, web pages, uploads — places
   where an attacker can plant instructions)
3. **It can send data out** (send mail, post messages, call external APIs)

With all three, a single poisoned message can talk the agent into leaking
your data: the pattern Simon Willison named the *lethal trifecta*. Meta's
"Agents Rule of Two" makes the same point from the platform side: hold at
most two of the three in one session.

Trifecta Checker rates an agent profile:

| Verdict | Meaning |
|---|---|
| **Lethal** | All three elements are present |
| **Risky** | Two elements, or one element plus a risk amplifier |
| **Low** | One element or fewer, no amplifiers |

Amplifiers: acting with **no human approval**, **auto-executing code**, and
**writing to long-term memory**.

## How it works

```
description ──▶ extraction ──▶ rule engine ──▶ explanation
               (Muse Spark)    (deterministic)  (Muse Spark)
```

- **The verdict never comes from an LLM.** A small deterministic rule engine
  (`trifecta_checker.py`) applies the rating rules, so the same profile
  always gets the same verdict. That reproducibility is the point.
- **Muse Spark's job is translation**: turning a free-text description into
  the engine's structured profile, turning the verdict back into plain
  language in five languages with one concrete attack scenario and a fix,
  and carrying the follow-up conversation after the verdict.
- **Extraction is validated.** The engine has a closed vocabulary. If the
  model invents a token, the output is sent back once with the allowed
  vocabulary (a *repair call*); if it still does not fit, extraction fails
  loudly instead of guessing. Aspects the description leaves open are
  reported back, and the UI asks about the one that could change the
  verdict.

Every verdict ships with its evidence (which capability produced which
element) and a **separation proposal**: split into a read-only Reader and a
Sender that only sends human-approved text to an allowlist. The samples
include the "after" state, so you can re-run the check and watch a Lethal
setup become two safer halves.

## Quickstart

```bash
# The engine alone — no API key needed
python3 trifecta_checker.py
python3 test_engine.py   # reproducibility + boundary tests (8 cases, no LLM)

# Full pipeline (needs access to the Meta Model API)
python3 extract.py --file fixtures/case_c.txt     # description -> verdict
python3 check.py   --file fixtures/case_c.txt --lang en

# Web UI (stdlib only)
python3 app.py 8765   # http://127.0.0.1:8765/
```

## Samples

| Case | Setup | Expected |
|---|---|---|
| A `case_a.txt` | Local memo summariser, no network | Low |
| B `case_b.txt` | Reads mail + web, cannot send | Risky |
| C `case_c.txt` | Mail agent that sends on its own and runs scripts | Lethal |
| D `case_d.txt` | Everyday assistant that sends chat messages | Lethal |
| C-fixed `case_c_fixed_reader.txt` | After the split: the Reader | Risky |
| C-fixed `case_c_fixed_sender.txt` | After the split: the approved Sender | Low |

See `fixtures/fixtures.json` for the manifest.

## Honest limitations

- The rating is a **heuristic**, not a standard. No validated scoring formula
  for agent configurations exists yet; the trifecta count is a necessary
  check, not a sufficient one.
- The trifecta pattern is mainly about **data theft**. Agents can be unsafe
  in other ways (bad tools, weak sandboxes, over-broad approvals) that this
  check does not cover — see the OWASP Top 10 for Agentic Applications for
  the wider map.
- Extraction quality depends on the description. Vague descriptions produce
  vague profiles; the checker asks back about the gaps that matter, but an
  honest, specific description still gives the most reliable verdict.

## References

- Simon Willison, *The lethal trifecta for AI agents* (2025-06-16) —
  https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Meta, *Agents Rule of Two* (2025-10-31) —
  https://ai.meta.com/blog/practical-ai-agent-security/
- OWASP, *Top 10 for Agentic Applications for 2026* —
  https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

## Built with

- **Muse Spark** (Meta Model API) for extraction and explanation
- A deterministic Python rule engine (this repo, written during the event)
- Prior work by the same author, cited as background: `ai-governance-control`
  (governance for the *development* environment — approval gates and
  fail-closed design). Trifecta Checker is the complementary runtime side:
  it diagnoses an agent configuration that already exists.
