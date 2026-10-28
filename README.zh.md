# Trifecta Checker

[English](README.md) · [日本語](README.ja.md) · **中文** · [हिन्दी](README.hi.md) · [Español](README.es.md)

**针对 AI 智能体的起飞前安全检查。** 描述一下你的智能体能做什么——
Trifecta Checker 会告诉你这种能力组合是否安全、为什么安全或不安全，
以及如果不安全，应该如何拆分。

为 Meta Global AI Developer Hackathon（2026 年 10 月–11 月）打造。

**在线演示：** https://meta-global-ai-hackathon-trifecta-c.vercel.app/


## 使用体验

你与 **Trafica** 这个友好的检查角色对话——不需要填表，也不需要
安全词汇：

1. **用你自己的话描述你的智能体。** 直接输入，点击 🎤 说话，或
   点击 + 并加载文件：纯文本描述，或 **MCP
   配置 JSON**——其中的 servers 会被总结成一段描述，
   并按原样检查（可以试试 `fixtures/sample_mcp_config.json`）。
2. **用通俗易懂的话得到一个判定**——Low、Risky 或 Lethal——以及
   背后的能力组合，还有用日常语言解释的可能出什么问题
   和如何修复。
3. **如果某个细节可能改变判定，Trafica 会反问你一个问题**
   而不是猜测。用点选或打字回答即可。
4. **继续对话。** 问“如果我拆分会怎样？”，Trafica 会展示拆分方案——
   一个只读的 Reader 和一个只发送经批准内容的 Sender——并给出
   每一半新的判定。

整个对话支持五种语言：英语、日语、中文、
印地语和西班牙语。

## 核心想法：致命三要素

当三种能力集中在一处时，智能体会变得危险：

1. **它读取隐私数据**（你的邮件、文件、日历……）
2. **它读取不可信内容**（正文、网页、上传文件——攻击者
   可以在这些地方植入指令）
3. **它可以向外发送数据**（发邮件、发消息、调用外部 API）

三者齐备时，一条被污染的消息就能诱使智能体泄露
你的数据：这就是 Simon Willison 所说的 *lethal trifecta* 模式。Meta 的
“Agents Rule of Two” 从平台角度讲了同样的道理：在一个会话中
最多同时持有三者中的两者。

Trifecta Checker 会给智能体画像打分：

| 判定 | 含义 |
|---|---|
| **Lethal** | 三个要素齐备 |
| **Risky** | 有两个要素，或有一个要素外加一个风险放大器 |
| **Low** | 只有一个或零个要素，且没有放大器 |

放大器：**无人审批就行动**、**自动执行代码**和
**写入长期记忆**。

## 工作原理

```
description ──▶ extraction ──▶ rule engine ──▶ explanation
               (Muse Spark)    (deterministic)  (Muse Spark)
```

- **判定结果永远不是来自 LLM。** 一个小型的确定性规则引擎
  （`trifecta_checker.py`）负责执行评分规则，所以同样的画像
  永远得到同样的判定。这种可复现性正是关键所在。
- **Muse Spark 的工作是转换**：把自由文本描述转成
  引擎用的结构化画像，把判定结果转回五种语言的通俗
  语言（各附一个具体的攻击场景和一个修复办法），
  并在判定之后继续进行后续对话。
- **提取结果会经过校验。** 引擎使用封闭词汇表。如果
  模型编造了一个词，输出会被连同允许的
  词汇表退回一次（一次 *repair call*）；如果仍然不符合，
  提取会明确报错，而不是猜测。描述中没有讲清楚的地方
  会被报告回来，界面会追问其中可能改变判定的
  那一个。

每个判定都附带证据（是哪个能力产生了哪个
要素）和一个**拆分方案**：拆成一个只读的 Reader 和一个
只向允许名单发送经人工批准文本的 Sender。示例中
包含拆分后的“之后”状态，你可以重新运行检查，看着一个 Lethal
配置变成两个更安全的部分。

## 快速上手

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

## 示例

| 案例 | 配置 | 预期判定 |
|---|---|---|
| A `case_a.txt` | 本地备忘录总结工具，无网络 | Low |
| B `case_b.txt` | 读取邮件 + 网页，不能发送 | Risky |
| C `case_c.txt` | 自行发送邮件并运行脚本的邮件智能体 | Lethal |
| D `case_d.txt` | 发送聊天消息的日常助手 | Lethal |
| C-fixed `case_c_fixed_reader.txt` | 拆分之后：Reader | Risky |
| C-fixed `case_c_fixed_sender.txt` | 拆分之后：经批准的 Sender | Low |

清单见 `fixtures/fixtures.json`。

## 坦诚的局限

- 评分是一种**启发式方法**，不是标准。目前还没有经过验证的
  智能体配置评分公式；三要素计数是必要的
  检查，但不是充分的检查。
- 三要素模式主要针对**数据窃取**。智能体还可能
  以其他方式不安全（有问题的工具、不够强的沙箱、过于宽泛的审批），
  这些都不在本检查范围内——更全的图景见 OWASP Top 10 for Agentic Applications。
- 提取质量取决于描述。模糊的描述会产生
  模糊的画像；检查器会追问那些关键的缺失信息，但
  诚实、具体的描述仍然能给出最可靠的判定。

## 参考资料

- Simon Willison, *The lethal trifecta for AI agents* (2025-06-16) —
  https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Meta, *Agents Rule of Two* (2025-10-31) —
  https://ai.meta.com/blog/practical-ai-agent-security/
- OWASP, *Top 10 for Agentic Applications for 2026* —
  https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

## 构建技术

- **Muse Spark**（Meta Model API），用于提取和解释说明
- 确定性 Python 规则引擎（本仓库，在活动期间编写）
- 同一作者的先前作品，作为背景引用：`ai-governance-control`
  （针对*开发*环境的治理——审批关卡和
  fail-closed 设计）。Trifecta Checker 是互补的运行时一侧：
  它诊断一个已经存在的智能体配置。
