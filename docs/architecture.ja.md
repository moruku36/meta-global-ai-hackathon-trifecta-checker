# Trifecta Checker — 全体設計

[English](architecture.md) · **日本語** · [中文](architecture.zh.md) · [हिन्दी](architecture.hi.md) · [Español](architecture.es.md)

Status: as built and deployed, 2026-10-28.
Live demo: https://meta-global-ai-hackathon-trifecta-c.vercel.app/
Repo: https://github.com/moruku36/meta-global-ai-hackathon-trifecta-checker

## 1. 目的

AIエージェントのための、飛行前安全チェックです。専門家でない人を想定しています。ユーザーが、自分のエージェントにできることを自分の言葉で説明すると、チェッカーがその力の組み合わせを評価します。それが「致命的な3点セット」(Lethal trifecta)（Simon Willison提唱）—— 個人データへのアクセス × 信頼できないコンテンツへの接触 × 外部への発信 —— に当てはまるかどうかを判定し、結果をやさしい言葉で説明します。具体的な直し方（エージェントを分ける、送信に承認を挟む）も添えます。

位置づけ: 設計時の診断です。実行時の取り締まりツール（例: NVIDIA OpenShell）や、作者の既存作 `ai-governance-control`（*開発*環境向けのガバナンス）を補うものです。判定ロジックにいちばん近い既発表の考え方は、Metaの「Agents Rule of Two」です。

## 2. アーキテクチャ

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

データベースなし、ビルド手順なし、サーバー側のセッションなし。クライアントが現在のプロファイルと判定結果をページの状態として持ち、呼び出しのたびに送り直します。

## 3. 構成要素

- **`trifecta_checker.py` — 決定的なルールエンジン。** 判定はLLMから決して来ません。能力の語彙は閉じています:
  - DATA_ACCESS {gmail_read, email_read, calendar_read, local_files,
    drive_read, contacts_read, message_read}
  - UNTRUSTED {web_browse, email_body, uploaded_files, webhook, chat_input}
  - OUTBOUND {email_send, chat_post, http_post, message_send,
    code_execute_outbound}
  - AMPLIFIERS {no_human_approval, auto_execute_code,
    long_term_memory_write}
  - ルール: 3要素そろえば **Lethal**（致命的）; 2要素、または1要素+増幅器なら **Risky**（要注意）; それ以外は **Low**（低い）。すべての判定には根拠（どのトークンがどの要素になったか）と、分離案（読み取り専用のReader + 許可リスト付き・承認必須のSender）が付きます。
- **`extract.py` — ガードレール付きのSpark抽出。** 自由文 → 閉じた語彙に収まるプロファイルJSONに変換します。不正なトークンが出たら、許可語彙を見せる修復呼び出しを1回だけ行います。それでも収まらなければ、推測せずにはっきり失敗させます。結果には `unclear` な点の一覧も付けます — {reads_private,
  reads_untrusted, sends_out, human_approval} のうち無害化した一部で、説明文だけでは決められない点を名指しします。
- **`explain.py` — 判定 → やさしい説明。** 5言語（en/ja/zh/hi/es）で見出しは固定: Verdict / What could happen / How to fix it / Bottom line / Next steps。あたたかく、日常の言葉での口調です。「Next steps」はやさしい提案で、最後に1つの誘いの質問で締めます。
- **`check.py` — パイプライン + 追加の会話。** 流れを `extract_and_judge`（LLM呼び出し1回）、`judge_profile`（0回）、`explain_result`（1回、失敗しても致命的でない）、`followup`（UIの言語でSparkが返答、日常語のみで生トークンは出さない。モデルは末尾に `[[SPLIT]]` と付けて分割表示を起動でき、別のエージェントの話になったら `[[NEW]]` と答える）に分けています。
- **`llm.py` — 共通のSpark呼び出し部。** ホスト環境: `META_API_KEY` 環境変数 → api.meta.aiへ直接呼び出し。ローカル開発: ヘルパーのサブプロセス経由でvault保管のキーにフォールバック（キーはコードにもログにも出ません）。
- **`app.py` — Webクライアント生成部。** 静的HTML1枚: チャット専用UI、マスコット（Trafica）、UI全体を切り替える言語選択、音声入力（Web Speech API）、ファイル添付、そして後述の聞き返しロジック。MCP設定JSON（例: Claude Desktop / MCPクライアントの設定）を添付すると、クライアント側でサーバーの概要を平易な説明文にまとめ、そのまま通常の抽出にかけます — 実際のエージェント設定をそのまま調べられます（`fixtures/sample_mcp_config.json`）。ページフッターにはヒューリスティックである旨の注意書きと、デモがパートナークレジットで動いていることのプライバシー注記があります。

## 4. 会話の設計

1. **あいさつ。** Traficaが自己紹介します: 何を調べるのか、どう始めればいいか（例文付き）。会話が始まるまでは、選んだ言語で表示し直します。
2. **判定はまず言葉で。** 判定の吹き出しは話し言葉の一文から始めます（「見てみました — 判定は Risky です」）、次にバッジ、親しみやすい要素チップ、「3つの力のうちn個」のカウントを付けます。
3. **聞き返しは最大1問。** クライアントがエンジンのルールを手元でなぞり、`unclear` な点が実際に判定を変えうる時だけ質問します。答えは Yes / No / Not sure チップ（直接入力も可）。答えると代表的な修正を当てはめ、/api/check-profile で判定し直します。直接入力したら質問を中断し、合わせた文章から抽出し直します。
4. **判定後の会話。** 追加の質問は /api/followup 経由でSparkへ。「分けたらどうなる?」にはReader / Sender の半分ずつを新しい判定付きで見せます — Lethal → Risky + Low というデモの流れです。

## 5. 主な判断とトレードオフ

- **賢さより再現性。** 評価は再現できます: 同じプロファイルなら同じ判定です。LLMは翻訳者として扱い、審判にはしません。これがこの製品のいちばんの信頼のよりどころです。
- 抽出では**黙って推測せず、はっきり失敗する**（1回修復して、だめなら目に見える形で失敗）。
- **ステートレスなホスティング。** Vercel無料枠、標準ライブラリのみのPython。ユーザーデータはどこにも保存しません。説明文は Meta Model API にだけ送ります。
- **公開デモ用のAPIガード。** 4つのエンドポイントは共通の `api_guard.py` を使います: リクエスト本文サイズ（64 KB）と項目ごとの文字数に上限を設け、LLM呼び出しの前に適用します。IPごとの簡易レート制限もあります（プロセス内カウンター — ステートレスなインスタンスなので素朴な連続呼び出しを鈍らせる程度で、全体の上限を保証するものではありません。厳密な上限には Vercel KV のような共有ストアが必要です）。公開UATの前に2026-10-28に追加しました。
- **無料クレジットの注意点。** パートナーの無料クレジット使用中は、送信内容が製品改善に使われる場合があります — UIの利用者はサンプルの説明文で試す想定で、UAT向けに明記しています。
- **範囲の正直さ。** この評価は目安であって、基準ではありません。3点セットが主に扱うのはデータ窃取で、エージェントのあらゆる危険を覆うものではありません（全体像にはOWASP Agentic Top 10を参照しています）。

## 6. 検証

- **エンジンの再現性（LLMなし）:** `test_engine.py` で6つの基本プロファイル + 境界2件（1要素+増幅器、無能力）を各2回ずつ判定 — 8/8 パス、実行をまたいで判定はバイト単位で同一。
- **抽出:** テキストの備品4件で4/4確認（Low / Risky / Lethal / Lethal）、エンジンの期待判定と一致。修復経路の探り（最初に造語トークンを出した説明文）では、修復呼び出しで閉じた語彙に正規化され、正しい判定に届くことを確認。修復できないプロファイルは設計通りはっきり失敗します。
- **オープンウェイト経路:** 抽出と説明は Muse Spark Open（Baseten経由の `meta-models/muse-spark-open-1026`）でも2026-10-27に通しで実行 — ケースCの抽出は正しいプロファイルを返し、説明は日本語と英語で正しく生成されました。
- デプロイごとの本番スモークテスト: /api/check、/api/explain、/api/followup。

## 7. 限界と今後

- 抽出の質は説明文の質に左右されます。聞き返しで和らげられますが、なくなりはしません。
- 実設定の取り込みは基本的な段階: MCP設定JSONをクライアント側で要約します（サーバー名、コマンド、URL）。他の形式（アシスタント設定、エージェント枠組み設定）はまだ解析できません。
- 共有できる判定カード / チーム表示はまだありません。
- 音声入力はブラウザのSpeechRecognition対応に依存します。
- 現在の5言語以外は今後の課題です。

## 8. ハッカソン評価軸への対応（自己評価）

- **Impact (30%)**: 増えつつある非専門のエージェント作り手を狙います。エージェントを配線する前の30秒チェックです。
- **Meta tooling (25%)**: 抽出・説明・会話に Meta Model API 経由の Muse Spark で構築。オープンウェイト経路を残し（テストで Muse Spark Open による抽出・説明を確認済み）。
- **Technical depth (20%)**: 決定的エンジン + 修復付きの検証済み抽出、判定を変えうる時だけの聞き返しロジック、追加対応用のアクションプロトコル。
- **Demo (25%)**: 3分の流れ — Lethal なメールエージェント → 聞き返し → Risky + Low に分割 → 音声 + 日本語UI。
