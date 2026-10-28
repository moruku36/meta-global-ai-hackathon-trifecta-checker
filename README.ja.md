# Trifecta Checker

[English](README.md) · **日本語** · [中文](README.zh.md) · [हिन्दी](README.hi.md) · [Español](README.es.md)

**AIエージェントのための離陸前チェック。**あなたのエージェントに何ができるかを説明するだけで —
その力の組み合わせが安全かどうか、理由は何か、安全でない場合にどう分ければいいかを、Trifecta Checkerが教えてくれます。

Meta Global AI Developer Hackathon（2026年10月〜11月）のために作りました。

**ライブデモ:** https://meta-global-ai-hackathon-trifecta-c.vercel.app/


## 使い方のイメージ

**Trafica**という親しみやすいチェッカーキャラとチャットするだけです — フォームも、セキュリティ用語もいりません：

1. **あなたのエージェントについて、自分の言葉で説明してください。**入力する、🎤をタップして話す、+をタップしてファイルを読み込む、のどれでもOKです：プレーンなテキストの説明文でも、**MCPの設定JSON**でも大丈夫です — サーバーの内容は説明文にまとめられて、そのままチェックされます（`fixtures/sample_mcp_config.json`で試せます）。
2. **結果はやさしい言葉で** — Low、Risky、Lethalのいずれか — 根拠になった力と、何が起こりうるか、どう直せばいいかを、日常の言葉で説明します。
3. **結果を左右しそうなあいまいな点があれば、Traficaは推測せずに1つだけ質問します。**タップか入力で答えてください。
4. **そのまま会話を続けられます。**「分けてみたら？」と聞けば、分割案を表示します — 読み取り専用のReaderと、承認つきで送るだけのSender — それぞれの新しい判定つきで。

会話全体は5言語に対応しています：英語、日本語、中国語、ヒンディー語、スペイン語です。

## 考え方：lethal trifecta

エージェントが危険になるのは、3つの力が1か所に集まったときです：

1. **プライベートなデータを読み取る**（メール、ファイル、カレンダーなど）
2. **信頼できないコンテンツを読み取る**（メッセージ本文、ウェブページ、アップロードファイルなど — 攻撃者が指示を仕込める場所）
3. **データを外に送り出せる**（メール送信、メッセージ投稿、外部APIの呼び出し）

3つがそろうと、1通の仕掛けられたメッセージだけで、エージェントをだましてデータを漏らさせることができます：Simon Willisonが*lethal trifecta*と名付けたパターンです。Metaの「Agents Rule of Two」も、プラットフォーム側から同じことを言っています：1つのセッションでは3つのうち最大2つまでに抑えよう、と。

Trifecta Checkerはエージェントの構成をこう評価します：

| Verdict | 意味 |
|---|---|
| **Lethal** | 3つの要素がすべてそろっている |
| **Risky** | 2つの要素がある、または1つの要素＋リスク増幅器がある |
| **Low** | 要素は1つ以下で、増幅器もない |

増幅器とは：**人の承認なしに動く**こと、**コードを自動実行する**こと、**長期記憶に書き込む**ことです。

## 仕組み

```
description ──▶ extraction ──▶ rule engine ──▶ explanation
               (Muse Spark)    (deterministic)  (Muse Spark)
```

- **判定自体はLLMが出しません。**小さな決定的ルールエンジン（`trifecta_checker.py`）が評価ルールを適用するので、同じ構成ならいつも同じ判定になります。その再現性こそがポイントです。
- **Muse Sparkの役割は翻訳です**：自由な説明文をエンジン用の構造化プロファイルに変えること、判定を5言語のやさしい言葉に戻すこと（具体的な攻撃シナリオと直し方つき）、判定後のやり取りを続けることです。
- **抽出は検証されます。**エンジンが使う言葉は決まった語彙だけです。モデルが存在しないトークンを作ったら、許される語彙つきでもう一度だけ送り返し（*repair call*）、それでも合わなければ推測せずに失敗としてはっきり伝えます。説明文で決まっていない点は報告され、判定を変えうる1点についてUIがたずねます。

すべての判定には根拠（どの機能がどの要素になったか）と**分離提案**がつきます：読み取り専用のReaderと、人間が承認した文面だけを許可リストに送るSenderに分ける案です。サンプルには分割「後」の状態も入っているので、再実行してLethalな構成が2つの安全な半分になる様子を確認できます。

## クイックスタート

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

## サンプル

| ケース | 内容 | 判定 |
|---|---|---|
| A `case_a.txt` | ネットなしのローカル用メモ要約 | Low |
| B `case_b.txt` | メール＋ウェブを読むが、送信はできない | Risky |
| C `case_c.txt` | 自分で送り、スクリプトも走らせるメールエージェント | Lethal |
| D `case_d.txt` | チャットメッセージを送る日常アシスタント | Lethal |
| C-fixed `case_c_fixed_reader.txt` | 分割後：Reader | Risky |
| C-fixed `case_c_fixed_sender.txt` | 分割後：承認つきのSender | Low |

一覧は`fixtures/fixtures.json`を見てください。

## 正直な限界

- この評価は**ヒューリスティック**であり、標準ではありません。エージェント設定の検証済みスコア式はまだ存在しません。3条件のカウントは必須のチェックであって、十分なチェックではありません。
- この3条件パターンが扱うのは主に**データ窃取**です。エージェントには他にも危険があります（危ういツール、弱いサンドボックス、広すぎる承認など）が、このチェックではカバーしません — 全体像はOWASP Top 10 for Agentic Applicationsを見てください。
- 抽出の質は説明文に左右されます。あいまいな説明からはあいまいなプロファイルしかできません。大事な抜けは聞き返しますが、正直で具体的な説明ほど信頼できる判定になります。

## 参考文献

- Simon Willison, *The lethal trifecta for AI agents* (2025-06-16) —
  https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Meta, *Agents Rule of Two* (2025-10-31) —
  https://ai.meta.com/blog/practical-ai-agent-security/
- OWASP, *Top 10 for Agentic Applications for 2026* —
  https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

## 構成

- 抽出と説明のための**Muse Spark**（Meta Model API）
- 決定的なPythonルールエンジン（このリポジトリ、イベント期間中に記述）
- 同一著者の先行作業を背景として引用：`ai-governance-control`
  （*開発*環境のためのガバナンス — 承認ゲートとフェイルクローズド設計）。Trifecta Checkerはそれを補う実行時側です：
  すでに存在するエージェント設定を診断します。
