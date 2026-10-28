# Trifecta Checker

[English](README.md) · **日本語** · [中文](README.zh.md) · [हिन्दी](README.hi.md) · [Español](README.es.md)

**AIエージェントのための離陸前チェック**。エージェントにできることを言葉で説明するだけで、その力の組み合わせが安全かどうか、理由は何か、ダメならどう分ければいいかを教えてくれます。

Meta Global AI Developer Hackathon（2026年10〜11月）向けに作りました。

**ライブデモ:** https://meta-global-ai-hackathon-trifecta-c.vercel.app/


## 使ってみるとこんな感じ

**Trafica**という親しみやすいチェッカーキャラとチャットするだけです。フォームも、セキュリティ用語もいりません。

1. **エージェントの内容を自分の言葉で説明してください**。 文字で打っても、🎤をタップして話しても、+をタップしてファイルを読み込んでもOKです。素朴な説明文でも、**MCPの設定JSON**でもいけます。サーバーの内容を要約してそのまま診断します（`fixtures/sample_mcp_config.json`で試せます）。
2. **結果がやさしい言葉で返ってきます** — Low（低い）、Risky（要注意）、Lethal（致命的）のいずれかです。どの力が効いたのか、どんなトラブルが起きうるのか、どう直せばいいのかを、日常の言葉で説明します。
3. **結果を左右しそうな点があいまいなら、Traficaが一つだけ質問します**。当て推量はしません。タップでも入力でも答えられます。
4. **そのまま会話を続けられます**。「分けてみたら？」と聞けば、読み取り専用のReaderと、承認されたものだけ送るSenderへの分割案を出し、それぞれの結果も新しく判定します。

会話全体は5言語に対応しています。英語、日本語、中国語、ヒンディー語、スペイン語です。

## 基本の考え方: lethal trifecta

エージェントは、3つの力が一か所に集まると危なくなります。

1. **プライベートなデータを読みます**（メール、ファイル、カレンダーなど）
2. **信用できないものを読みます**（本文、ウェブページ、アップロードなど。攻撃者が指示を仕込める場所です）
3. **外にデータを送れます**（メール送信、投稿、外部APIの呼び出しなど）

この3つがそろうと、汚染されたメッセージ一つでデータを盗まれる恐れがあります。Simon Willisonが*lethal trifecta*と名づけた形です。Metaの「Agents Rule of Two」も、土台側から同じことを言っています。1つの場面では3つのうち2つまでしか持たせない、という考え方です。

Trifecta Checkerはエージェントの内容をこう判定します。

| 判定 | 意味 |
|---|---|
| **Lethal**（致命的） | 3つの要素がすべてそろっている |
| **Risky**（要注意） | 2つの要素がある、または1つの要素＋リスクを強める要因がある |
| **Low**（低い） | 要素は1つ以下で、強める要因もない |

強める要因: **人の承認なしで動くこと****、コードの自動実行****、長期メモリへの書き込み**です。

## 仕組み

```
description ──▶ extraction ──▶ rule engine ──▶ explanation
               (Muse Spark)    (deterministic)  (Muse Spark)
```

- **判定をLLMには任せません**。 小さな決まったルールエンジン（`trifecta_checker.py`）が判定ルールを当てはめるので、同じ内容ならいつも同じ結果になります。この再現性こそが大事な点です。
- **Muse Sparkの役目は翻訳です**。自由な説明文をエンジン用の決まった形に直し、判定結果を5言語のやさしい言葉に戻します。具体的な攻撃の流れを一つと直し方を添え、判定後のやり取りも続けます。
- **変換結果は確かめます**。 エンジンの言葉づかいは閉じています。モデルが勝手な言葉を作ったら、許される言葉づきで一度だけやり直させ（*repair call*）、それでも合わなければ推測せずにはっきり失敗させます。説明に足りない点は報告され、結果を変えうる一点について画面がたずねます。

この分け方は、Metaのハッカソンの勉強会「Agents 102: Best Practices for Verifiable Agents Pt. 2」（Yash Khare氏、Metaパートナーエンジニア）が確かめられるエージェント向けに教える形と同じです。確かめを後づけにせず道具に組み込むこと、先に決まった検査をしてLLMには判断が要るところだけ任せること、人の承認を必須の関門にすることです。勉強会のデモのメモ自体が確かめに落ちました。この分け方があれば早めに気づける類のミスです。

どの判定にも根拠がつきます（どの力がどの要素になったか）と、**分け方の提案**です。読み取り専用のReaderと、許可先に・人が承認した文だけ送るSenderに分けます。見本には「分けた後」の状態も入っているので、もう一度走らせて、Lethalだったものが安全な二つになる様子を見られます。

## クイックスタート

```bash
# The engine alone — no API key needed
python3 trifecta_checker.py
python3 tests/test_engine.py   # reproducibility + boundary tests (8 cases, no LLM)

# Full pipeline (needs access to the Meta Model API)
python3 extract.py --file fixtures/case_c.txt     # description -> verdict
python3 check.py   --file fixtures/case_c.txt --lang en

# Web UI (stdlib only)
python3 app.py 8765   # http://127.0.0.1:8765/
```

## 見本

| ケース | 内容 | 予想 |
|---|---|---|
| A `case_a.txt` | ネットなしの社内メモ要約 | Low |
| B `case_b.txt` | メール＋ウェブを読むが、送れない | Risky |
| C `case_c.txt` | 独断で送り、台本も走らせるメールエージェント | Lethal |
| D `case_d.txt` | チャットを送る身近な助手 | Lethal |
| C-fixed `case_c_fixed_reader.txt` | 分けた後: Readerの方 | Risky |
| C-fixed `case_c_fixed_sender.txt` | 分けた後: 承認つきSenderの方 | Low |

一覧は`fixtures/fixtures.json`を見てください。

## 正直な限界

- この判定は**目安**であり、規格ではありません。エージェント設定の確かな点数式はまだありません。3つの数の勘定は欠かせない検査ですが、それだけでは足りません。
- trifectaの形が主に扱うのは**データの盗み出し**です。エージェントが危ない道はほかにもあり（危うい道具、弱い砂場、広すぎる承認など）、この検査では拾えません。広い地図はOWASP Top 10 for Agentic Applicationsを見てください。
- 変換の質は説明しだいです。あいまいな説明からはあいまいな像しかできません。大事な抜けは聞き返しますが、正直で具体的な説明ほど確かな結果になります。

## 参考文献

- Simon Willison, *The lethal trifecta for AI agents* (2025-06-16) —
  https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Meta, *Agents Rule of Two* (2025-10-31) —
  https://ai.meta.com/blog/practical-ai-agent-security/
- OWASP, *Top 10 for Agentic Applications for 2026* —
  https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

## 使ったもの

- 変換と説明のための**Muse Spark**（Meta Model API）
- 決まった動きをするPythonのルールエンジン（このリポジトリ。会期中に書きました）
- 同じ作者の先行作を背景として挙げます。`ai-governance-control`（*開発*環境のための統治。承認の関門と失敗時は閉じる設計）。Trifecta Checkerは対になる実行時の側です。すでに存在するエージェント設定を診ます。
