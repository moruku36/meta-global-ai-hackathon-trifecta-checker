# Trifecta Checker — 全体設計

[English](architecture.md) · **日本語** · [中文](architecture.zh.md) · [हिन्दी](architecture.hi.md) · [Español](architecture.es.md)

ステータス： 2026-10-28時点の実装・デプロイ済みの内容。
ライブデモ： https://meta-global-ai-hackathon-trifecta-c.vercel.app/
リポジトリ： https://github.com/moruku36/meta-global-ai-hackathon-trifecta-checker

## 1. 目的

AIエージェントのための離陸前安全チェックで、専門家ではない人を対象にしています。ユーザーは自分のエージェントにできることを自分の言葉で説明し、チェッカーはその力の組み合わせが「lethal trifecta」（Simon Willison提唱の、非公開データへのアクセス×信頼できないコンテンツへの接触×外部への発信）かどうかを判定し、結果をやさしい言葉で説明したうえで、具体的な直し方（エージェントを分割する、送信に承認を挟む）を提案します。

位置づけは、設計時の診断です。実行時の強制ツール（例：NVIDIA OpenShell）を補完するもので、作者の過去作`ai-governance-control`（*開発*環境向けのガバナンス）とも補完関係にあります。判定ロジックに一番近い公開済みの考え方は、Metaの「Agents Rule of Two」です。

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

データベースなし、ビルド手順なし、サーバー側のセッションなしです。クライアントが現在のprofile／verdictをページの状態として持ち、呼び出しのたびに送り直します。

## 3. コンポーネント

- **`trifecta_checker.py` — 決定的なルールエンジン**。判定結果はLLMからは絶対に出てきません。機能の語彙は閉じたものを使います。
  - DATA_ACCESS {gmail_read, email_read, calendar_read, local_files,
    drive_read, contacts_read, message_read}
  - UNTRUSTED {web_browse, email_body, uploaded_files, webhook, chat_input}
  - OUTBOUND {email_send, chat_post, http_post, message_send,
    code_execute_outbound}
  - AMPLIFIERS {no_human_approval, auto_execute_code,
    long_term_memory_write}
  - ルール： 3要素そろえば**Lethal**、2要素、または1要素＋増幅要素なら**Risky**、それ以外は**Low**。すべての判定には根拠（どのトークンがどの要素になったか）と分離案（読み取り専用のReader＋承認つき・許可リストつきのSender）が付きます。
- **`extract.py` — ガードレール付きのSpark抽出**。自由文→閉じた語彙に限定したprofile JSONに変換します。不正なトークンが出たら、許可語彙を見せてONE回だけ修復コールをかけ、それでも収まらなければ推測せずにはっきり失敗します。結果には`unclear`な点の一覧も含みます。{reads_private,
  reads_untrusted, sends_out, human_approval}のうち無害化した一部だけを使い、説明文で何が開いたままかを名指しします。
- **`explain.py` — 判定→やさしい説明**。6言語（en/ja/zh/hi/es/ko）で見出し固定：Verdict／What could happen／How to fix it／Bottom line／Next steps。あたたかく、日常言葉の口調です。「Next steps」はやさしい提案で、最後にONEつの誘う質問で締めます。
- **`check.py` — パイプライン＋その後の会話**。流れを`extract_and_judge`（LLM呼び出し1回）、`judge_profile`（0回）、`explain_result`（1回、失敗しても致命的でない）、`followup`（SparkがUI言語で返答、平易な言葉のみで生トークンは出さない。モデルは末尾に`[[SPLIT]]`と付けて分割ビューを出したり、別のエージェントの話になったら`[[NEW]]`と答えたりできる）に分けます。
- **`llm.py` — 共通のSpark呼び出し**。ホスト環境では`META_API_KEY`環境変数→api.meta.aiへの直接呼び出し。ローカル開発ではヘルパーのサブプロセス経由で保管されたキーにフォールバックします（キーはコードにもログにも出ません）。
- **`app.py` — Webクライアントの生成**。静的HTML 1ページ：チャット専用UI、マスコット（Trafica）、UI全体を切り替える言語選択、音声入力（Web Speech API）、ファイル添付、そして後述の聞き返しロジック。MCP設定JSON（例：Claude Desktop／MCPクライアントの設定）を添付すると、クライアント側でサーバー内容の平易な説明に要約してから通常の抽出に回します。そのため実際のエージェント設定をそのままチェックできます（`fixtures/sample_mcp_config.json`）。ページフッターにはヒューリスティックである旨の注意書きと、デモがパートナークレジットで動いている旨のプライバシーメモがあります。

## 4. 会話デザイン

1. **あいさつ**。Traficaが自己紹介します。何をチェックするか、どう始めるか（例文つき）。会話が始まるまでは選んだ言語で表示し直します。
2. **まず言葉で判定を**。判定バブルは話し言葉の一文から始めます（「見てみましたよ — 判定はRiskyです」）、次にバッジ、やさしい要素チップ、「3つのうちn個」のカウントを出します。
3. **聞き返しは最大ONE問**。クライアント側でエンジンルールをまねて、`unclear`な点が本当に判定を変えそうなときだけ聞きます。答えはYes／No／Not sureのチップ（入力も可）。答えると代表的な編集を当てはめて/api/check-profileで再判定します。代わりに入力すると質問は中断し、合わせた文章から抽出し直します。
4. **判定後の会話**。その後の質問は/api/followup経由でSparkへ。「分割したら？」にはReader／Senderの半分ずつを新しい判定付きで見せます。これがLethal → Risky＋Lowというデモの流れです。

## 5. 主な判断とトレードオフ

- **賢さより決定性**。判定は再現できます。同じprofileなら同じ判定です。LLMは翻訳者として扱い、裁判官にはしません。これが製品の信頼の要です。
- 抽出では、黙って推測せず**はっきり失敗する**（1回修復して、だめなら見える形で失敗）。
- **ステートレスなホスティング**。Vercel無料枠、標準ライブラリのみのPython。ユーザーデータはどこにも保存しません。説明文はMeta Model APIにだけ送ります。
- **公開デモ用のAPIガード**。4つのエンドポイント共通で`api_guard.py`を使います。リクエスト本文サイズ（64 KB）と項目ごとの文字数に上限をかけ、LLM呼び出しの前に強制するほか、IPごとのベストエフォートなレート制限もあります（プロセス内カウンター — ステートレスなインスタンスでは素朴なループを鈍らせる程度で、全体の上限は保証しません。厳密な上限にはVercel KVのような共有ストアが必要です）。公開UATの前に2026-10-28に追加しました。
- **無料クレジットの注意点**。パートナーの無料クレジット使用中は、送信内容が製品改善に使われる場合があります — UIの利用者はサンプル文で試す想定で、UAT向けに明記しています。
- **範囲の正直さ**。判定はヒューリスティックで、標準ではありません。trifectaは主にデータ窃取をカバーし、あらゆるエージェントリスクをカバーするものではありません（全体像にはOWASP Agentic Top 10を参照しています）。

## 6. 検証

- **エンジンの再現性（LLMなし）：**`tests/test_engine.py`で代表的な6プロファイル＋境界2件（1要素＋増幅要素、無能力）を各2回ずつ判定 — 8/8パス、実行ごとの判定はバイト単位で同一。
- **抽出：**テキストfixture 4件で4/4確認（Low／Risky／Lethal／Lethal）、エンジン想定の判定と一致。修復経路の探り（最初に造語トークンを出した説明文）では、修復コールで閉じた語彙に正規化し、正しい判定に届くことを確認。修復できないprofileは設計通りはっきり失敗します。
- **オープンウェイト経路：**抽出と説明は2026-10-27にMuse Spark Open（Baseten経由の`meta-models/muse-spark-open-1026`）でも端から端まで実行済み — ケースCの抽出は正しいprofileを返し、日本語と英語で説明も正しく生成できました。
- デプロイごとの本番スモークテスト：/api/check、/api/explain、/api/followup。

## 7. 制限と今後の課題

- 抽出品質は説明文の品質に依存します。聞き返しで和らげられますが、なくなりはしません。
- 実設定の取り込みは基本的なもの：MCP設定JSONをクライアント側で要約します（サーバー名、コマンド、URL）。他の書き出し形式（アシスタント設定、エージェントフレームワーク設定）は未対応です。
- 共有できる判定カード／チームビューはまだありません。
- 音声入力はブラウザのSpeechRecognition対応に依存します。
- 現在の6言語以外への対応は今後の課題です。

## 8. ハッカソン評価基準への対応（自己評価）

- **Impact（30%）**：専門家ではないエージェント作り手を狙います。エージェントをつなぐ前に30秒でチェックできます。
- **Meta tooling（25%）**：抽出・説明・会話にMeta Model API経由のMuse Sparkを使っています。オープンウェイト経路も残し、抽出・説明はMuse Spark Openでテスト済みです。
- **Technical depth（20%）**：決定的エンジン＋修復つき検証済み抽出、判定を変える聞き返しロジック、その後の会話用のアクションプロトコル。
- **Demo（25%）**：3分の流れ — Lethalなメールエージェント→聞き返し→Risky＋Lowに分割→音声＋日本語UI。

## 9. 設計の根拠

上記の形 — 決定は決定的チェックが持ち、LLMは判断が要るところだけ、人の承認を関門に — は、Meta自身のハッカソンワークショップで教わったエージェント設計と同じ形です。「Agents 102: Best Practices for Verifiable Agents Pt. 2」（Meta Global AI Developer Hackathonライブセッション、Yash Khare、Metaパートナーエンジニア）。

3つの一致点：

- **検証は組み込みで、任意ではない**。ワークショップの決まり：検証はツールの中に住み、エージェントが飛ばせる別手順にはしません。ここでは毎回のチェックで`trifecta_checker.py`が判定を計算します — LLMの経路で迂回も上書きもできません。
- **決定的を先に、LLM-as-judgeは後に**。ワークショップでは完全性と形式チェックは素のコードで、主張に本当に裏付けがあるかだけLLMが判定します。ここではルールエンジンが判定を持ち、Muse Sparkはprofileの抽出と結果の平易な説明だけをします。
- **人の承認は関門**。ワークショップは全チェック通過後も人のサインオフで終わります。ここでは人の承認なしの動作（`no_human_approval`）自体が判定の中のリスク増幅要素です。

ワークショップのデモは反面教師でもあります。前回作ったメモは検証に落ちました — 裏付けのない主張と壊れたルールです。未検証のエージェント出力は間違いを出荷します。Trifecta Checkerは同じ教訓を一段手前で活かします。出力の後だけでなく、動く前に設定をチェックします。
