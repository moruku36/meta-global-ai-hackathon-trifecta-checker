# Trifecta Checker — 总体设计

[English](architecture.md) · [日本語](architecture.ja.md) · **中文** · [हिन्दी](architecture.hi.md) · [Español](architecture.es.md)

状态：按 2026-10-28 已构建并部署的版本。
在线演示：https://meta-global-ai-hackathon-trifecta-c.vercel.app/
代码仓库：https://github.com/moruku36/meta-global-ai-hackathon-trifecta-checker

## 1. 目的

面向非专业人士的 AI 智能体起飞前安全检查。用户用自己的话描述其智能体能做什么；检查器评估该能力组合是否为“lethal trifecta”（Simon Willison 提出）——私有数据访问 × 不可信内容接触 × 外部通信——并用通俗语言解释结果，同时给出具体的修复办法（拆分智能体、对发送动作加关卡）。

定位：设计时诊断。它与运行时强制执行工具（例如 NVIDIA OpenShell）互补，也与作者此前的作品 `ai-governance-control`（针对*开发*环境的治理）互补。Meta 的“Agents Rule of Two”与本评分逻辑最为接近，是已公开发表的参照。

## 2. 架构

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

无数据库、无构建步骤、无服务端会话：客户端在页面状态中携带当前的 profile/verdict，并在每次调用时重新发送。

## 3. 组件

- **`trifecta_checker.py` —— 确定性规则引擎。** verdict 永远不来自 LLM。封闭的能力词汇表：
  - DATA_ACCESS {gmail_read, email_read, calendar_read, local_files,
    drive_read, contacts_read, message_read}
  - UNTRUSTED {web_browse, email_body, uploaded_files, webhook, chat_input}
  - OUTBOUND {email_send, chat_post, http_post, message_send,
    code_execute_outbound}
  - AMPLIFIERS {no_human_approval, auto_execute_code,
    long_term_memory_write}
  - 规则：集齐 3 类要素 = **Lethal**（致命）；2 类要素，或 1 类要素 + 放大器 = **Risky**（有风险）；其他情况为 **Low**（低风险）。每个 verdict 都附带证据（哪个 token 产生了哪个要素）以及分离方案（只读的 Reader + 带 allowlist 的、需审批的 Sender）。
- **`extract.py` —— 带护栏的 Spark 抽取。** 自由文本 → 限定在封闭词汇表内的 profile JSON。无效 token 只触发一次 repair 调用，向模型展示允许的词汇表；如果输出仍然不符合，则大声报错、抽取失败（不猜测）。结果中还列出 `unclear` 方面——经处理的 {reads_private,
  reads_untrusted, sends_out, human_approval} 子集——指出描述中哪些内容没有说清楚。
- **`explain.py` —— verdict → 友好的解释。** 五种语言（en/ja/zh/hi/es）的固定标题：Verdict / What could happen / How to
  fix it / Bottom line / Next steps。语气亲切，用日常词汇；“Next
  steps”是温和的建议，最后以一个邀请式的提问结尾，全程仅一个问题。
- **`check.py` —— 流水线 + 后续对话。** 将流程拆分为 `extract_and_judge`（1 次 LLM 调用）、`judge_profile`（0 次调用）、`explain_result`（1 次调用，失败不致命）和 `followup`（Spark 以界面语言回复，只用通俗词汇，绝不出现原始 token；模型可通过在结尾输出 `[[SPLIT]]` 触发拆分视图，或在用户描述另一个不同智能体时回答 `[[NEW]]`）。
- **`llm.py` —— 共用的 Spark 调用器。** 线上托管：`META_API_KEY` 环境变量 → 直接调用 api.meta.ai。本地开发：通过辅助子进程回退到 vault 中保存的 key（key 从不出现在代码或日志中）。
- **`app.py` —— 网页客户端生成器。** 单个静态 HTML 页面：纯聊天 UI，带吉祥物（Trafica）、驱动整个 UI 的语言选择器、语音输入（Web Speech API）、文件附件，以及下文所述的追问逻辑。附加 MCP 配置 JSON（例如 Claude
  Desktop / MCP 客户端配置）会在客户端被汇总为对其 servers 的 plain 描述，再走常规抽取流程——因此真实的智能体配置可原样检查（`fixtures/sample_mcp_config.json`）。页面页脚带有启发式声明，以及关于演示版运行在使用合作方 credits 的隐私说明。

## 4. 对话设计

1. **问候。** Trafica 自我介绍：它检查什么、如何开始（附例句）。在对话开始前，会按所选语言重新渲染。
2. **先用语言给出 verdict。** verdict 气泡先用一句口语开头（“我看了一下——verdict 是 Risky”），然后是徽章、友好的要素 chips，以及“n of 3 powers”计数。
3. **追问，最多一个问题。** 客户端在本地对照引擎规则，只有当某个 `unclear` 方面确实可能改变 verdict 时才追问。回答为 Yes / No / Not sure chips（也可直接输入）。回答后会应用一个代表性修改，并经由
   /api/check-profile 重新判定。直接输入文字则会打断提问，并根据合并后的文本重新抽取。
4. **verdict 之后的对话。** 后续问题经由 /api/followup 发给 Spark；“如果我拆开会怎样？”会展示 Reader/Sender 两半及各自的新 verdict——演示弧线为 Lethal → Risky + Low。

## 5. 关键决策与权衡

- **确定性优先于小聪明。** 评分可复现：相同的 profile，相同的 verdict。LLM 被视为翻译器，绝不做裁判。这是本产品主要的信任主张。
- **抽取中大声失败，而非悄悄猜测**（repair 一次，之后则 visibly 失败）。
- **无状态托管。** Vercel 免费套餐、仅用标准库的 Python；用户数据不存储在任何地方。描述文本只发送给 Meta Model API。
- **公开演示版的 API 防护。** 四个端点共用 `api_guard.py`：对请求体大小（64 KB）和每个字段的文本长度设硬上限，在任何 LLM 调用之前强制执行；另加尽力而为的按 IP 限流（进程内计数器——由于实例无状态，它只能迟滞简单的循环刷请求，不能保证全局限流；硬性限流需要 Vercel KV 之类的共享存储）。在向公众开放演示版 UAT 之前的 2026-10-28 添加。
- **免费 credits 说明。** 在使用合作方免费 credits 期间，提交的内容可能被用于产品改进——UI 的受众预期会用示例描述进行测试，这一点已向 UAT 说明。
- **范围诚实。** 评分是启发式方法，不是标准；trifecta 主要覆盖数据窃取，不覆盖所有智能体风险（引用 OWASP Agentic
  Top 10 作为更-wide 的风险地图）。

## 6. 验证

- **引擎可复现性（无 LLM）：** `tests/test_engine.py` 判定六个标准 profile 加两个边界情况（一个要素 + 放大器；无能力），每个跑两遍——8/8 通过，多次运行 verdict 字节级一致。
- **抽取：** 在文本 fixtures 上 4/4 验证通过（Low / Risky /
  Lethal / Lethal），与引擎预期 verdict 一致。一次 repair 路径探测（某描述首次产生了自创 token）确认 repair 调用将其规范化到封闭词汇表内，并仍然得到正确 verdict；无法 repair 的 profile 按设计大声失败。
- **开源权重路径：** 2026-10-27 在 Muse Spark Open（经由
  Baseten 的 `meta-models/muse-spark-open-1026`）上端到端运行了抽取和解释——Case C 抽取返回了正确的
  profile，日语和英语解释均正常生成。
- 每次部署后做生产冒烟测试：/api/check、/api/explain、
  /api/followup。

## 7. 局限与未来工作

- 抽取质量取决于描述质量；追问能缓解，但不能消除这一点。
- 真实配置导入还比较基础：MCP 配置 JSON 在客户端汇总（server 名称、命令、URL）。其他导出格式（助手设置、智能体框架配置）尚不能解析。
- 尚无可分享的 verdict 卡片 / 团队视图。
- 语音输入依赖浏览器的 SpeechRecognition 支持。
- 当前五种语言之外的语言是未来工作。

## 8. 黑客松评分映射（自评）

- **影响力（30%）**：面向日益增长的非专业智能体搭建人群；在智能体接线之前做一次 30 秒检查。
- **Meta 工具（25%）**：基于经由 Meta Model API 的 Muse Spark 构建，用于抽取、解释和对话；设计保留开源权重路径（已在测试中验证 Muse Spark Open 可做抽取/解释）。
- **技术深度（20%）**：确定性引擎 + 带 repair 的 validated 抽取、可改变 verdict 的追问逻辑、后续对话的 action 协议。
- **演示（25%）**：3 分钟弧线——Lethal 邮件智能体 → 追问 → 拆分为 Risky + Low → 语音 + 日语 UI。
