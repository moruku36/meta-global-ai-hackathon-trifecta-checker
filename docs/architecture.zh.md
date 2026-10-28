# Trifecta Checker — 总体设计

[English](architecture.md) · [日本語](architecture.ja.md) · **中文** · [हिन्दी](architecture.hi.md) · [Español](architecture.es.md)

状态：按 2026-10-28 实际构建和部署情况编写。
在线演示：https://meta-global-ai-hackathon-trifecta-c.vercel.app/
代码仓库：https://github.com/moruku36/meta-global-ai-hackathon-trifecta-checker

## 1. 目的

面向非专业人士的 AI 智能体起飞前安全检查。用户用自己的话描述自己的智能体能做什么；检查器评估这种能力组合是否为“lethal trifecta”（Simon Willison 提出）——私有数据访问 × 不可信内容接触 × 对外通信——并用通俗语言解释结果，同时给出具体的修复办法（拆分智能体、对发送动作加审批）。

定位：设计时诊断。它与运行时强制执行工具（例如 NVIDIA OpenShell）互补，也与作者之前的工作 `ai-governance-control`（针对*开发*环境的治理）互补。Meta 的“Agents Rule of Two”与本评分逻辑最为接近，是已公开发表过的最相关的参照。

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

无数据库、无构建步骤、无服务端会话：客户端在页面状态中携带当前的 profile / verdict，并在每次调用时重新发送。

## 3. 组件

- **`trifecta_checker.py` —— 确定性规则引擎。**  verdict 永远不来自 LLM。封闭的能力词汇表：
  - DATA_ACCESS {gmail_read, email_read, calendar_read, local_files,
    drive_read, contacts_read, message_read}
  - UNTRUSTED {web_browse, email_body, uploaded_files, webhook, chat_input}
  - OUTBOUND {email_send, chat_post, http_post, message_send,
    code_execute_outbound}
  - AMPLIFIERS {no_human_approval, auto_execute_code,
    long_term_memory_write}
  - 规则：3 个要素 = **Lethal**；2 个要素，或 1 个要素 + 放大器 =
    **Risky**；其他为 **Low**。每个 verdict 都附带证据（哪个 token 产生了哪个要素）和拆分方案（只读的 Reader + 带 allowlist 的审批 gated Sender）。
- **`extract.py` —— 带护栏的 Spark 抽取。** 自由文本 → 限定在封闭词汇表内的 profile JSON。无效 token 只触发一次修复调用，在调用中向模型展示允许的词汇表；如果输出仍然不符合，抽取会明确报错失败（不猜测）。结果中还会列出 `unclear` 方面——{reads_private,
  reads_untrusted, sends_out, human_approval} 的脱敏子集——指出描述中哪些内容没有说清楚。
- **`explain.py` —— verdict → 友好解释。** 五种语言（en/ja/zh/hi/es）的固定标题：Verdict / What could happen / How to
  fix it / Bottom line / Next steps。语气亲切，用日常词汇；“Next
  steps”是温和的建议，最后以一个邀请式问题结尾，且只提一个问题。
- **`check.py` —— 流水线 + 后续对话。** 将流程拆分为 `extract_and_judge`（1 次 LLM 调用）、`judge_profile`（0 次调用）、`explain_result`（1 次调用，失败不致命）和 `followup`（Spark 以界面语言回复，只用通俗词汇，绝不直接使用原始 token；模型可在结尾输出 `[[SPLIT]]` 以触发拆分视图，或在用户描述另一个智能体时回答 `[[NEW]]`）。
- **`llm.py` —— 共用的 Spark 调用器。** 线上托管：`META_API_KEY` 环境变量 →
  直接调用 api.meta.ai。本地开发：通过辅助子进程回退到 vault 中保存的密钥（密钥绝不会出现在代码或日志中）。
- **`app.py` —— 网页客户端生成器。** 单个静态 HTML 页面：纯聊天 UI，带吉祥物（Trafica）、驱动整个 UI 的语言选择器、语音输入（Web Speech API）、文件附件，以及下文所述的追问逻辑。附加 MCP 配置 JSON（例如 Claude
  Desktop / MCP 客户端配置）会在客户端被汇总为对其 servers 的通俗描述，再进入常规抽取流程——因此真实的智能体配置可原样检查（`fixtures/sample_mcp_config.json`）。页面页脚带有启发式声明，以及关于演示版运行在合作方赠送额度上的隐私说明。

## 4. 对话设计

1. **问候语。** Trafica 自我介绍：它检查什么，以及如何开始（附例句）。在对话开始前，会按所选语言重新渲染。
2. **先用文字给出 verdict。** verdict 气泡先用一口语化句子开头（“我看了一下——verdict 是 Risky”），然后是徽章、友好的要素标签，以及“3 种能力中的 n 种”计数。
3. **追问，最多一个问题。** 客户端在本地对照引擎规则，只有当某个 `unclear` 方面确实可能改变 verdict 时才追问。回答为 Yes / No / Not sure 选项（也可打字）。回答后会应用一个代表性修改，并经由
   /api/check-profile 重新判定。直接打字会打断提问，并根据合并后的文本重新抽取。
4. **verdict 之后的对话。** 后续问题经由 /api/followup 发给 Spark；“如果我拆分会怎样？”会展示 Reader / Sender 两半及各自的新 verdict——演示弧线为 Lethal → Risky + Low。

## 5. 关键决策与权衡

- **确定性优先于聪明。** 评分可复现：相同的 profile，相同的 verdict。LLM 被视为翻译器，绝不做裁判。这是本产品的主要信任主张。
- **抽取中宁可明确失败，也不静默猜测**（修复一次，然后可见地失败）。
- **无状态托管。** Vercel 免费套餐、仅用 Python 标准库；用户数据不在任何地方存储。描述只发送给 Meta Model API。
- **公开演示的 API 防护。** 四个端点共用 `api_guard.py`：
  对请求体大小（64 KB）和每个字段的文本长度设硬上限，在任何 LLM 调用之前强制执行，另加尽力而为的按 IP 限流（进程内计数器——由于实例无状态，它只能减缓简单的循环请求，不能保证全局限流；硬性全局限流需要共享存储，例如 Vercel KV）。在向公众开放演示 UAT 之前的 2026-10-28 添加。
- **免费额度说明。** 在使用合作方免费额度期间，提交的内容可能被用于产品改进——UI 的受众应在测试中使用示例描述，这一点已在 UAT 中说明。
- **范围诚实。** 评分是启发式方法，不是标准；trifecta 主要覆盖数据盗窃，并不覆盖智能体的所有风险（更广的风险图谱可参考 OWASP Agentic
  Top 10）。

## 6. 验证

- **引擎可复现性（无 LLM）：** `tests/test_engine.py` 判定六个典型 profile 加两个边界情况（一个要素 + 放大器；无能力），每个跑两次——8/8 通过，各次运行的 verdict 字节级一致。
- **抽取：** 在文本 fixtures 上 4/4 验证通过（Low / Risky /
  Lethal / Lethal），与引擎的预期 verdict 一致。一次修复路径探测（某描述首次产生了虚构的 token）确认修复调用可将其规范化到封闭词汇表中，并仍得出正确的 verdict；无法修复的 profile 按设计会明确报错失败。
- **开源权重路径：** 抽取和解释也已在 Muse Spark Open（2026-10-27 经由 Baseten 的 `meta-models/muse-spark-open-1026`）上端到端运行——Case C 抽取返回了正确的 profile，日文和英文解释均正常生成。
- 每次部署后生产冒烟测试：/api/check、/api/explain、/api/followup。

## 7. 局限与未来工作

- 抽取质量取决于描述质量；追问能缓解，但不能消除这一点。
- 真实配置导入还比较基础：MCP 配置 JSON 在客户端汇总（server 名称、命令、URL）。其他导出格式（助手设置、智能体框架配置）暂未解析。
- 暂无可分享的 verdict 卡片 / 团队视图。
- 语音输入依赖浏览器的 SpeechRecognition 支持。
- 当前五种语言之外的语言是未来工作。

## 8. Hackathon 评分映射（自评）

- **影响力（30%）**：面向不断增长的非专业智能体搭建者群体；在智能体接线之前，花 30 秒检查一次。
- **Meta 工具（25%）**：基于 Meta Model API 的 Muse Spark 构建，用于抽取、解释和对话；设计保留开源权重路径（已在测试中验证 Muse Spark Open 可做抽取/解释）。
- **技术深度（20%）**：确定性引擎 + 带修复的校验抽取、可改变 verdict 的追问逻辑、后续对话的动作协议。
- **演示（25%）**：3 分钟弧线——Lethal 邮件智能体 → 追问 → 拆分为 Risky + Low → 语音 + 日文界面。

## 9. 设计依据

上述模式——确定性检查掌握决策权、只在需要判断的地方用 LLM、人类审批作为关卡——与 Meta 自己的 hackathon 工作坊所教的智能体设计模式一致：“Agents 102: Best Practices for Verifiable Agents Pt. 2”（Meta Global
AI Developer Hackathon 直播课程；Yash Khare，Meta 合作伙伴工程师）。

三处对应：

- **验证内建，而非可选。** 工作坊的规则是：验证存在于工具内部，绝不能成为智能体可以跳过的单独步骤。在这里，每次检查都由 `trifecta_checker.py` 计算 verdict——任何 LLM 路径都无法绕过或覆盖它。
- **确定性优先，LLM 做裁判在后。** 在工作坊中，完整性和格式检查是普通代码；LLM 只判断某个主张是否真正有依据。在这里，规则引擎掌握 verdict；Muse Spark 只抽取 profile 并用通俗语言解释结果。
- **人类审批是一道关卡。** 工作坊以人工签核收尾，即使所有检查都已通过。在这里，无人类审批行动（`no_human_approval`）本身就是评分中的一个风险放大器。

工作坊的演示也是一个警示案例：上一次课程中构建的备忘录没能通过验证——存在无依据的主张和坏掉的规则。未经验证的智能体输出会把错误发出去。Trifecta Checker 把同样的教训再往前推一步：在智能体运行之前先检查配置，而不只在之后检查输出。
