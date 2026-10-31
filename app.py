#!/usr/bin/env python3
"""Trifecta Checker — chat-style web UI (standard library only).

Conversation flow:
  1. The user describes their agent in plain words (typing or voice).
  2. Muse Spark sorts the words into capabilities; if something important
     is unclear, the checker asks back with Yes / No / Not sure buttons.
  3. The rule engine (not an LLM) gives the verdict.
  4. Muse Spark explains it in plain language, ending with concrete
     next steps. A "safer split" button shows how the rating changes when
     the powers are split across two agents.

The whole page follows the language picker (en / ja / zh / hi / es).

Run:  python3 app.py   (then open http://127.0.0.1:8765)
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from api_guard import (MAX_MESSAGE_CHARS, check_body_size, check_payload,  # noqa: E402
                       check_rate, check_text)
from check import explain_result, extract_and_judge, followup, judge_profile  # noqa: E402

BASE = Path(__file__).resolve().parent
LANGS = ["en", "ja", "zh", "hi", "es", "ko"]

# --- UI strings -------------------------------------------------------------
STRINGS = {
    "verdict_say": {
        "en": "I had a look — the verdict is {v}.",
        "ja": "見てみたよ。判定は {v} だね。",
        "zh": "我看过了，判定是 {v}。",
        "hi": "मैंने देख लिया — निर्णय है {v}।",
        "es": "Ya lo revisé: el veredicto es {v}.",
    },
    "venn_hint": {"en": "Run a check and the three powers light up here.", "ja": "チェックしてみて！3つのパワーがここで光るよ", "zh": "运行检查，三种能力会在此点亮。", "hi": "चेक चलाओ, तीनों पावर्स यहाँ जलेंगी।", "es": "Haz un check y se iluminan los 3 poderes."},
    "chip_safe": {"en": "Try: a safe setup", "ja": "試す：安全な構成", "zh": "试试：安全配置", "hi": "आज़माएं: सुरक्षित सेटअप", "es": "Probar: setup seguro"},
    "chip_risky": {"en": "Try: a risky setup", "ja": "試す：危険な構成", "zh": "试试：风险配置", "hi": "आज़माएं: जोखिम वाला सेटअप", "es": "Probar: setup riesgoso"},
    "chip_lethal": {"en": "Try: a lethal setup", "ja": "試す：致命的な構成", "zh": "试试：致命配置", "hi": "आज़माएं: घातक सेटअप", "es": "Probar: setup letal"},
    "sample_safe": {"en": "A personal notes assistant. It reads only my own notes on this device, never opens links or files from other people, and cannot send messages or post anything anywhere.", "ja": "個人用のメモ助手。自分の端末にある自分のメモだけを読み、他の人から来たリンクやファイルは開かず、メッセージを送ったり投稿したりはできません。", "zh": "个人笔记助手。只读本机自己的笔记，不打开他人链接或文件，不能发消息或发布内容。", "hi": "पर्सनल नोट्स असिस्टेंट। सिर्फ इस डिवाइस के मेरे नोट्स पढ़ता है, दूसरों के लिंक/फाइल नहीं खोलता, मैसेज/पोस्ट नहीं कर सकता।", "es": "Asistente de notas personal. Solo lee mis notas en este dispositivo, nunca abre enlaces/archivos ajenos y no puede enviar mensajes ni publicar."},
    "sample_risky": {"en": "A research assistant. It reads my documents and browses web pages and forum posts to summarize them. It cannot send messages or change anything outside.", "ja": "調査アシスタント。私の文書を読み、ウェブページやフォーラムの投稿を閲覧して要約します。メッセージを送ったり、外部のものを変更したりはできません。", "zh": "研究助手。读取我的文档并浏览网页和论坛帖子来总结。不能发消息或更改外部内容。", "hi": "रिसर्च असिस्टेंट। मेरे दस्तावेज़ पढ़ता है, वेब पेज-फोरम देखकर सार देता है। मैसेज नहीं भेज सकता, बाहर कुछ बदल नहीं सकता।", "es": "Asistente de investigación. Lee mis documentos y resume páginas web y foros. No puede enviar mensajes ni cambiar nada externo."},
    "sample_lethal": {"en": "An inbox agent. It reads my private email and files, opens links and attachments people send me, and can reply to emails and post to Slack on my behalf.", "ja": "受信箱エージェント。私の非公開のメールやファイルを読み、人から送られてきたリンクや添付ファイルを開き、私の代わりにメールに返信したりSlackに投稿したりできます。", "zh": "收件箱代理。读取我的私人邮件和文件，打开他人发来的链接和附件，可代我回邮件并发到Slack。", "hi": "इनबॉक्स एजेंट। मेरी प्राइवेट ईमेल-फाइलें पढ़ता है, मिले लिंक/अटैचमेंट खोलता है, मेरी ओर से ईमेल जवाब-Slack पोस्ट कर सकता है।", "es": "Agente de inbox. Lee mi email privado y archivos, abre enlaces y adjuntos recibidos, y puede responder emails y publicar en Slack por mí."},
    "lang_label": {"en": "Language", "ja": "言語", "zh": "语言", "hi": "भाषा", "es": "Idioma"},
    "greeting": {
        "en": "Hi, I'm Trafica, your Trifecta Checker! 👋\nI look at three powers an AI agent can have: reading your private data, reading things that arrive from other people, and sending things out. When one agent has all three, a trick hidden in an incoming message can make it leak your data — that's the mix I check for you.\nStarting is easy. Just write what your agent does in the box below — for example: \"It reads my email and sends replies for me.\" You can also tap + to load a text file, or tap 🎤 and just talk to me.",
        "ja": "こんにちは、トラフィカだよ。三要素チェックを担当してるよ👋\nAIエージェントが持つ3つの力——大事なデータを読めること、よそから届いた文を読むこと、外に送れること——を見ていくよ。この3つが1つのエージェントにそろうと、届いた文に仕掛けられたワナで、大事なデータが漏れてしまうことがあるんだ。その危ない組み合わせになっていないか、一緒に確かめよう。\n始め方はかんたん。下の欄に、あなたのエージェントが何をしているか書いてみて。たとえば「メールを読んで、返事も送ってくれるアシスタント」みたいにね。＋ボタンでテキストファイルを読み込ませたり、🎤で話しかけたりもできるよ。",
        "zh": "你好，我是 Trafica，负责三要素检查👋\n我会看 AI 智能体的三种能力：读取你的重要数据、读取从外面送来的内容、把内容发送到外面。当一个智能体同时拥有这三种能力时，送来的内容里藏着的陷阱可能会让它把你的数据泄露出去。我就是来帮你检查这种危险组合的。\n开始很简单，在下面的框里写下你的智能体在做什么就行，比如：“它会读我的邮件，还会替我回复。”也可以点＋加载文本文件，或者点🎤直接跟我说。",
        "hi": "नमस्ते, मैं Trafica हूँ, तुम्हारी Trifecta जाँच करने वाली👋\nमैं AI एजेंट की तीन ताकतें देखती हूँ: तुम्हारा निजी डेटा पढ़ना, बाहर से आई चीज़ें पढ़ना, और बाहर कुछ भेजना। जब एक ही एजेंट के पास तीनों हों, तो बाहर से आए संदेश में छिपी चाल से तुम्हारा डेटा बाहर जा सकता है। मैं यही खतरनाक मेल जाँचती हूँ।\nशुरू करना आसान है। नीचे वाले डिब्बे में बस लिख दो कि तुम्हारा एजेंट क्या करता है — जैसे: “यह मेरी ईमेल पढ़ता है और मेरी तरफ से जवाब भी भेजता है।” + दबाकर टेक्स्ट फ़ाइल भी लगा सकते हो, या 🎤 दबाकर मुझसे बात भी कर सकते हो।",
        "es": "¡Hola! Soy Trafica, tu verificadora trifecta 👋\nReviso tres poderes que puede tener un agente de IA: leer tus datos privados, leer cosas que llegan de otras personas y enviar cosas fuera. Cuando un solo agente tiene los tres, un truco escondido en un mensaje entrante puede hacer que filtre tus datos. Esa es la mezcla que reviso por ti.\nEmpezar es fácil. Escribe en el cuadro de abajo qué hace tu agente, por ejemplo: «Lee mi correo y envía respuestas por mí». También puedes tocar + para cargar un archivo de texto, o tocar 🎤 y hablar conmigo.",
    },
    "check_btn": {"en": "Check", "ja": "チェック", "zh": "检查", "hi": "जाँचें", "es": "Comprobar"},
    "mic_btn": {"en": "🎤", "ja": "🎤", "zh": "🎤", "hi": "🎤", "es": "🎤"},
    "thinking": {"en": "Let me take a look…", "ja": "うーん、見てみるね…", "zh": "我看看啊…", "hi": "ज़रा देखने दो…", "es": "Déjame ver…"},
    "yes": {"en": "Yes", "ja": "はい", "zh": "是", "hi": "हाँ", "es": "Sí"},
    "no": {"en": "No", "ja": "いいえ", "zh": "不是", "hi": "नहीं", "es": "No"},
    "unsure": {"en": "Not sure", "ja": "わからない", "zh": "不确定", "hi": "पता नहीं", "es": "No lo sé"},
    "q_reads_private": {
        "en": "Let me ask one thing: can it read your important data — mail, files, calendar, that kind of thing?",
        "ja": "ちょっとだけ聞かせて。そのエージェント、あなたの大事なデータ（メール・ファイル・予定とか）を読める？",
        "zh": "我先问一句：它能读到你的重要数据吗，比如邮件、文件、日历之类的？",
        "hi": "एक बात पूछूँ: क्या यह तुम्हारा ज़रूरी डेटा पढ़ सकता है — मेल, फ़ाइलें, कैलेंडर वगैरह?",
        "es": "Te pregunto una cosa: ¿puede leer tus datos importantes, como correo, archivos o calendario?",
    },
    "q_reads_untrusted": {
        "en": "And does stuff from other people reach it — incoming mail, web pages, files people upload?",
        "ja": "もう1つ。よその人から届いたもの（メール・Webページ・アップされたファイル）は、そのエージェントに届く？",
        "zh": "再问一个：别人发来的东西会到它那里吗，比如收到的邮件、网页、别人上传的文件？",
        "hi": "और एक बात: क्या दूसरों की भेजी चीज़ें इस तक पहुँचती हैं — आने वाले मेल, वेब पेज, लोगों की अपलोड की फ़ाइलें?",
        "es": "Y otra: ¿le llegan cosas de otras personas, como correos que recibe, páginas web o archivos que sube la gente?",
    },
    "q_sends_out": {
        "en": "Also — can it send things out by itself? Sending mail, posting, or sending data to a server, for example.",
        "ja": "それと、自分から外へ送ったりできる？ たとえば、メールを送る・投稿する・どこかのサーバーに送る、みたいなこと。",
        "zh": "还有，它能自己往外发东西吗？比如发邮件、发帖，或者把数据发到某个服务器。",
        "hi": "और यह भी: क्या यह खुद बाहर कुछ भेज सकता है? जैसे मेल भेजना, पोस्ट करना, या किसी सर्वर पर डेटा भेजना।",
        "es": "Y también: ¿puede enviar cosas por su cuenta? Por ejemplo, mandar correos, publicar o enviar datos a un servidor.",
    },
    "q_human_approval": {
        "en": "One more: before it does something, do you get to say OK first?",
        "ja": "あと、動き出す前に、あなたが「いいよ」って確認する形になってる？",
        "zh": "再问一句：它行动之前，会先让你点头确认吗？",
        "hi": "आख़िरी बात: कुछ करने से पहले, क्या यह पहले तुम्हारी हाँ लेता है?",
        "es": "Una más: antes de hacer algo, ¿te pide tu OK primero?",
    },
    "verdict_updated": {"en": "With your answers, here's how it looks now:", "ja": "答えてもらった内容で見直すと、こうだね：", "zh": "加上你的回答，现在看起来是这样：", "hi": "तुम्हारे जवाबों के साथ अब यह ऐसा दिखता है:", "es": "Con tus respuestas, así queda:"},
    "split_btn": {"en": "What if I split it up?", "ja": "分けたらどうなる？", "zh": "拆开会怎样？", "hi": "बाँटने पर क्या होगा?", "es": "¿Y si lo divido?"},
    "restart_btn": {"en": "Check another agent", "ja": "別のエージェントで試す", "zh": "换一个智能体试试", "hi": "दूसरा एजेंट आज़माएँ", "es": "Probar con otro agente"},
    "split_intro": {
        "en": "If you split the powers across two agents, it looks like this:",
        "ja": "力を2つに分けると、こんな感じになるよ：",
        "zh": "把能力拆到两个智能体上，会变成这样：",
        "hi": "शक्तियों को दो एजेंटों में बाँटने पर ऐसा होगा:",
        "es": "Si divides los poderes entre dos agentes, quedaría así:",
    },
    "var_no_out": {"en": "reader only (cannot send)", "ja": "読むだけ（送信なし）", "zh": "只读（不能发送）", "hi": "सिर्फ़ पढ़ने वाला (भेज नहीं सकता)", "es": "solo lectura (no puede enviar)"},
    "var_no_untrusted": {"en": "sender only (no outside content)", "ja": "送るだけ（外の内容なし）", "zh": "只发送（不接收外部内容）", "hi": "सिर्फ़ भेजने वाला (बाहरी सामग्री नहीं)", "es": "solo envío (sin contenido externo)"},
    "form_note": {"en": "(Answered the three questions)", "ja": "（3つの質問に回答）", "zh": "（已回答三个问题）", "hi": "(तीन सवालों के जवाब दिए)", "es": "(Respondió las tres preguntas)"},
    "or_title": {"en": "or answer three questions instead", "ja": "代わりに3つの質問に答える", "zh": "或者回答三个问题", "hi": "या तीन सवालों के जवाब दें", "es": "o responde tres preguntas"},
    "form_hint": {
        "en": "Tick everything your agent can do. Leave a question blank if the answer is none.",
        "ja": "できることに全部チェックしてください。なければ空欄でOKです。",
        "zh": "把您的智能体能做的都勾上；没有就留空。",
        "hi": "आपका एजेंट जो कर सकता है, उन सब पर निशान लगाएँ; कुछ नहीं है तो खाली छोड़ दें।",
        "es": "Marca todo lo que tu agente puede hacer; si no aplica, déjalo en blanco.",
    },
    "name_ph": {"en": "Agent name (optional)", "ja": "エージェント名（任意）", "zh": "智能体名称（可选）", "hi": "एजेंट का नाम (वैकल्पिक)", "es": "Nombre del agente (opcional)"},
    "form_btn": {"en": "Check with these answers", "ja": "この回答でチェック", "zh": "按这些答案检查", "hi": "इन जवाबों से जाँच करें", "es": "Comprobar con estas respuestas"},
    "footer": {
        "en": "The rating is a simple safety heuristic, not a certification. It focuses on data theft: an agent that can read private data, swallow other people's content, and send data out can be tricked into leaking what it read.",
        "ja": "この評価は目安であり、認証ではありません。対象は主にデータの盗み出しです：秘密のデータを読めて、他人の内容を取り込めて、外へ送れるエージェントは、だまされて読んだ内容を漏らすことがあります。",
        "zh": "这个评级只是一个简单的安全参考，不是认证。它主要防的是数据被盗：能读私人数据、能吞下他人内容、又能向外发送的智能体，可能被骗着把读到的内容泄露出去。",
        "hi": "यह रेटिंग एक सरल सुरक्षा अनुमान है, प्रमाणपत्र नहीं। इसका ध्यान डेटा चोरी पर है: जो एजेंट निजी डेटा पढ़ सके, दूसरों की सामग्री निगल सके और बाहर भेज सके, उसे बहकाकर पढ़ा हुआ डेटा लीक कराया जा सकता है।",
        "es": "La calificación es una heurística de seguridad sencilla, no una certificación. Se centra en el robo de datos: un agente que puede leer datos privados, tragarse el contenido de otros y enviar datos fuera puede ser engañado para filtrar lo que leyó.",
    },
    "privacy_note": {
        "en": "Demo note: this demo runs on partner credits, so what you type may be used to improve the service. Please try it with sample descriptions, not real private data.",
        "ja": "デモ版の注意：このデモはパートナーのクレジットで動いているため、入力した内容がサービス改善に使われることがあります。実データではなく、サンプルの説明で試してね。",
        "zh": "演示提示：本演示使用合作伙伴额度，你输入的内容可能会被用于改进服务。请使用示例说明，不要输入真实的私人数据。",
        "hi": "डेमो नोट: यह डेमो पार्टनर क्रेडिट पर चलता है, इसलिए तुम जो लिखोगे वह सेवा सुधारने में इस्तेमाल हो सकता है। असली निजी डेटा नहीं, नमूना विवरण इस्तेमाल करो।",
        "es": "Nota de la demo: esta demo funciona con créditos de socio, así que lo que escribas puede usarse para mejorar el servicio. Usa descripciones de ejemplo, no datos privados reales.",
    },
    "exp_loading": {
        "en": "Putting it into plain words…",
        "ja": "分かりやすい言葉にしてみるね…",
        "zh": "我用大白话说一下…",
        "hi": "आसान शब्दों में समझाता हूँ…",
        "es": "Lo pongo en palabras sencillas…",
    },
    "exp_unavailable": {
        "en": "(Explanation unavailable: ", "ja": "（説明を取得できませんでした：",
        "zh": "（无法获取说明：", "hi": "(व्याख्या उपलब्ध नहीं: ", "es": "(Explicación no disponible: ",
    },
    "error_prefix": {
        "en": "Could not complete the check: ", "ja": "チェックを完了できませんでした：",
        "zh": "无法完成检查：", "hi": "जाँच पूरी नहीं हो सकी: ", "es": "No se pudo completar la comprobación: ",
    },
    "error_tip": {
        "en": "Tip: add a little more detail — what it can read, what reaches it, what it can send — and try again.",
        "ja": "ヒント：何を読めるか・何が届くか・何を送れるかを少し足して、もう一度試してください。",
        "zh": "提示：补充一点细节——它能读什么、会收到什么、能发送什么——然后再试一次。",
        "hi": "सुझाव: थोड़ी और जानकारी जोड़ें — यह क्या पढ़ सकता है, इसे क्या मिलता है, यह क्या भेज सकता है — और फिर कोशिश करें।",
        "es": "Consejo: añade un poco más de detalle (qué puede leer, qué le llega, qué puede enviar) e inténtalo de nuevo."
    },
    "el1": {"en": "Can read your important data", "ja": "大事なデータを読める", "zh": "能读到重要数据", "hi": "ज़रूरी डेटा पढ़ सकता है", "es": "Puede leer datos importantes"},
    "el2": {"en": "Reads what others send in", "ja": "よそから来た文を読む", "zh": "会读别人发来的内容", "hi": "दूसरों की भेजी बातें पढ़ता है", "es": "Lee lo que envían otros"},
    "el3": {"en": "Can send things out", "ja": "外に送れる", "zh": "能往外发东西", "hi": "बाहर भेज सकता है", "es": "Puede enviar cosas fuera"},
    "of_powers": {"en": "of the 3 powers", "ja": "3つの力のうち", "zh": "三项能力中占", "hi": "3 शक्तियों में से", "es": "de los 3 poderes"},
    "powers_fmt": {"en": "{n} of the 3 powers", "ja": "3つの力のうち {n}つ", "zh": "三项能力中占 {n} 项", "hi": "3 शक्तियों में से {n}", "es": "{n} de los 3 poderes"},
    "attach_error": {
        "en": "I couldn't read that file — a plain text file works best.",
        "ja": "そのファイルは読み込めなかった。テキストファイルだと読めるよ。",
        "zh": "这个文件读不了，纯文本文件最合适。",
        "hi": "वह फ़ाइल पढ़ नहीं पाया — साधारण टेक्स्ट फ़ाइल सबसे ठीक रहती है।",
        "es": "No pude leer ese archivo; un archivo de texto simple funciona mejor.",
    },
    "chips_hint": {
        "en": "Tap one — or just type your answer below.",
        "ja": "ボタンでも、下に言葉で書いてもらっても大丈夫だよ。",
        "zh": "点一个就行，也可以直接在下面输入。",
        "hi": "एक दबाएँ — या नीचे लिखकर भी बता सकते हैं।",
        "es": "Toca uno, o escribe tu respuesta abajo.",
    },
    "plus": {"en": "plus:", "ja": "追加：", "zh": "另外：", "hi": "साथ में:", "es": "además:"},
}

# --- Capability groups: engine tokens with a plain label per language -------
def L(en, ja, zh, hi, es):
    return {"en": en, "ja": ja, "zh": zh, "hi": hi, "es": es}


GROUPS = [
    {"field": "data_access",
     "title": L("Question 1 — What private data can it read?",
                "質問1 — 何の個人データを読めますか？",
                "问题 1 — 它能读取哪些私人数据？",
                "सवाल 1 — यह कौन-सा निजी डेटा पढ़ सकता है?",
                "Pregunta 1: ¿qué datos privados puede leer?"),
     "items": [
         ("gmail_read", L("Gmail", "Gmail", "Gmail", "Gmail", "Gmail")),
         ("email_read", L("Other email", "その他のメール", "其他邮箱", "अन्य ईमेल", "Otro correo")),
         ("calendar_read", L("Calendar", "カレンダー", "日历", "कैलेंडर", "Calendario")),
         ("contacts_read", L("Contacts", "連絡先", "联系人", "संपर्क", "Contactos")),
         ("drive_read", L("Cloud drive (Google Drive etc.)", "クラウドドライブ（Google Driveなど）", "云端硬盘（Google Drive 等）", "क्लाउड ड्राइव (Google Drive आदि)", "Nube (Google Drive, etc.)")),
         ("local_files", L("Files on the computer", "パソコン内のファイル", "电脑里的文件", "कंप्यूटर की फ़ाइलें", "Archivos del ordenador")),
         ("message_read", L("Chat / message history", "チャット・メッセージ履歴", "聊天/消息记录", "चैट / संदेश इतिहास", "Historial de chat/mensajes")),
     ]},
    {"field": "untrusted_inputs",
     "title": L("Question 2 — What can reach it from other people?",
                "質問2 — 他人から何が届きますか？",
                "问题 2 — 他人的哪些内容能到达它？",
                "सवाल 2 — दूसरों से क्या इस तक पहुँच सकता है?",
                "Pregunta 2: ¿qué puede llegarle de otras personas?"),
     "items": [
         ("email_body", L("Emails it receives", "届くメール", "它收到的邮件", "इसे मिलने वाले ईमेल", "Correos que recibe")),
         ("web_browse", L("Web pages it opens", "開くWebページ", "它打开的网页", "इसके खोले वेब पेज", "Páginas web que abre")),
         ("uploaded_files", L("Files people upload", "人がアップロードしたファイル", "别人上传的文件", "लोगों द्वारा अपलोड फ़ाइलें", "Archivos que sube la gente")),
         ("chat_input", L("Chat messages from users", "ユーザーからのチャット", "用户发来的聊天消息", "उपयोगकर्ताओं के चैट संदेश", "Mensajes de chat de usuarios")),
         ("webhook", L("Webhooks / triggers from other systems", "Webhook・他システムからの起動", "Webhook / 其他系统的触发", "Webhook / अन्य सिस्टम के ट्रिगर", "Webhooks / activadores de otros sistemas")),
     ]},
    {"field": "outbound",
     "title": L("Question 3 — What can it send out or do outside?",
                "質問3 — 外へ何を送れますか・何ができますか？",
                "问题 3 — 它能向外发送什么、做什么？",
                "सवाल 3 — यह बाहर क्या भेज सकता है या कर सकता है?",
                "Pregunta 3: ¿qué puede enviar o hacer fuera?"),
     "items": [
         ("email_send", L("Send email", "メールを送る", "发送邮件", "ईमेल भेजना", "Enviar correos")),
         ("chat_post", L("Post messages in chat channels", "チャットに投稿する", "在聊天频道发言", "चैट चैनलों में पोस्ट करना", "Publicar en canales de chat")),
         ("message_send", L("Send direct messages", "DMを送る", "发送私信", "सीधे संदेश भेजना", "Enviar mensajes directos")),
         ("http_post", L("Send data to a web address", "Webアドレスへデータを送る", "向网址发送数据", "वेब पते पर डेटा भेजना", "Enviar datos a una dirección web")),
         ("code_execute_outbound", L("Run code that sends data out", "データを送るコードを実行する", "运行会向外发送数据的代码", "बाहर डेटा भेजने वाला कोड चलाना", "Ejecutar código que envía datos")),
     ]},
    {"field": "amplifiers",
     "title": L("One more thing — any of these?",
                "もう1つ — 当てはまるものは？",
                "再问一个 — 有以下情况吗？",
                "एक और बात — इनमें से कुछ है?",
                "Una cosa más: ¿algo de esto?"),
     "items": [
         ("no_human_approval", L("It acts without asking a person first", "人の確認なしで動く", "不经人确认就行动", "बिना व्यक्ति से पूछे काम करता है", "Actúa sin pedir permiso a una persona")),
         ("auto_execute_code", L("It runs code by itself", "自分でコードを実行する", "自己运行代码", "खुद कोड चलाता है", "Ejecuta código por sí solo")),
         ("long_term_memory_write", L("It remembers things long-term", "長期的に記憶する", "长期记忆事情", "चीज़ें लंबे समय तक याद रखता है", "Recuerda cosas a largo plazo")),
     ]},
]


# --- Text diet + Korean support (2026-10-30) ---
_SHORT = {
 "greeting": {
  "en": "Hi, I'm Trafica! 👋 I check one risky mix: an agent that can read your private data, read outside content, and send things out can be tricked into leaking your data.\nJust tell me what your agent does — e.g. \"It reads my email and replies for me.\" You can also attach a file with +, or tap 🎤 and talk.",
  "ja": "こんにちは、トラフィカだよ👋 危ない組み合わせをチェックするよ：大事なデータを読めて、外から来た文を読めて、外に送れるエージェントは、だまされてデータを漏らすことがあるんだ。\n下の欄に、あなたのエージェントが何をするか書いてみて。たとえば「メールを読んで返信もする」。＋でファイル添付、🎤で音声でもOKだよ。",
  "zh": "嗨，我是 Trafica！👋 我只检查一种危险组合：能读取你的私人数据、读取外部内容、还能向外发送的智能体，可能会被骗而泄露你的数据。\n告诉我你的智能体会做什么——比如“它帮我读邮件并回复。” 你也可以用 + 添加文件，或点 🎤 直接说。",
  "hi": "हाय, मैं Trafica हूँ! 👋 मैं एक खतरनाक मेल की जाँच करती हूँ: जो एजेंट तुम्हारा निजी डेटा पढ़ सकता है, बाहर की सामग्री पढ़ सकता है, और बाहर भेज सकता है, उसे बहकाकर तुम्हारा डेटा लीक कराया जा सकता है।\nबस बताओ तुम्हारा एजेंट क्या करता है — जैसे \"यह मेरा ईमेल पढ़कर जवाब देता है।\" तुम + से फाइल जोड़ सकते हो, या 🎤 दबाकर बोल सकते हो।",
  "es": "¡Hola, soy Trafica! 👋 Reviso una sola mezcla riesgosa: un agente que puede leer tus datos privados, leer contenido externo y enviar cosas puede ser engañado para filtrar tus datos.\nCuéntame qué hace tu agente — p. ej. «Lee mi correo y responde por mí». También puedes adjuntar un archivo con +, o tocar 🎤 y hablar."
 },
 "footer": {
  "en": "Simple safety heuristic, not a certification — it flags agents that can read private data, take in outside content, and send data out.",
  "ja": "この評価は目安であり、認証ではありません。大事なデータを読めて、外の内容を取り込めて、外へ送れるエージェントが、だまされて漏らす危険を見ます。",
  "zh": "简单的安全经验法则，不是认证——它会标记那些能读取私人数据、接收外部内容并向外发送数据的智能体。",
  "hi": "साधारण सुरक्षा अनुमान, प्रमाणन नहीं — यह उन एजेंटों को बताता है जो निजी डेटा पढ़ सकते हैं, बाहरी सामग्री लेते हैं, और डेटा बाहर भेज सकते हैं।",
  "es": "Heurística de seguridad simple, no una certificación — detecta agentes que pueden leer datos privados, recibir contenido externo y enviar datos."
 },
 "privacy_note": {
  "en": "Demo note: this demo runs on partner credits, and your input may be used to improve the service. Please use sample descriptions, not real private data.",
  "ja": "デモ版の注意：このデモはパートナーのクレジットで動いているため、入力内容がサービス改善に使われることがあります。実データではなく、サンプルで試してね。",
  "zh": "演示说明：本演示使用合作伙伴额度运行，你的输入可能被用于改进服务。请使用示例描述，不要用真实私人数据。",
  "hi": "डेमो नोट: यह डेमो पार्टनर क्रेडिट पर चलता है, और तुम्हारा इनपुट सेवा सुधारने में इस्तेमाल हो सकता है। कृपया असली निजी डेटा नहीं, नमूना विवरण इस्तेमाल करो।",
  "es": "Nota de demo: esta demo funciona con créditos de socios, y tu entrada podría usarse para mejorar el servicio. Usa descripciones de ejemplo, no datos privados reales."
 }
}
for _key, _langs in _SHORT.items():
    STRINGS[_key].update(_langs)
_KO_STRINGS = {
 "verdict_say": "봤어 — 판정은 {v}야.",
 "lang_label": "언어",
 "greeting": "안녕, 난 트라피카야! 👋 내가 확인하는 건 딱 하나의 위험한 조합이야: 네 private한 데이터를 읽고, 외부 내용을 읽고, 밖으로 보낼 수 있는 에이전트는 속아서 데이터를 샐 수 있어.\n네 에이전트가 뭘 하는지 말해줘 — 예를 들면 \"내 이메일을 읽고 답장해 줘.\" +로 파일을 첨부하거나, 🎤를 눌러 말해도 돼.",
 "check_btn": "확인하기",
 "mic_btn": "🎤",
 "thinking": "보고 있어…",
 "yes": "응",
 "no": "아니",
 "unsure": "잘 모르겠어",
 "q_reads_private": "한 가지만 물어볼게: 네 중요한 데이터 — 메일, 파일, 캘린더 같은 거 — 읽을 수 있어?",
 "q_reads_untrusted": "그리고 다른 사람에게서 온 게 닿아? 들어오는 메일, 웹페이지, 사람들이 올린 파일 같은 거?",
 "q_sends_out": "또 — 혼자서 밖으로 보낼 수 있어? 메일 보내기, 올리기, 서버로 데이터 보내기 같은 거 말이야.",
 "q_human_approval": "마지막으로: 뭔가 하기 전에 네가 먼저 OK 해줘야 돼?",
 "verdict_updated": "네 답을 반영하면, 지금은 이렇게 보여:",
 "split_btn": "나누면 어떻게 돼?",
 "restart_btn": "다른 에이전트 확인하기",
 "split_intro": "힘을 두 에이전트로 나누면 이렇게 돼:",
 "var_no_out": "읽기만 (보내기 불가)",
 "var_no_untrusted": "보내기만 (외부 내용 없음)",
 "form_note": "(세 질문에 답변 완료)",
 "or_title": "아니면 세 질문에 답해줘",
 "form_hint": "네 에이전트가 할 수 있는 건 다 체크해. 해당 없으면 비워 둬.",
 "name_ph": "에이전트 이름 (선택)",
 "form_btn": "이 답변으로 확인하기",
 "footer": "간단한 안전 휴리스틱이야, 인증은 아니야 — private 데이터 읽기, 외부 내용 받기, 데이터 보내기가 다 되는 에이전트를 알려줘.",
 "privacy_note": "데모 안내: 이 데모는 파트너 크레딧으로 돌아가고, 입력은 서비스 개선에 쓰일 수 있어. 진짜 private 데이터 말고 예시 설명을 써줘.",
 "exp_loading": "알기 쉽게 풀어쓰는 중…",
 "exp_unavailable": "(설명을 볼 수 없어: ",
 "error_prefix": "확인을 끝내지 못했어: ",
 "error_tip": "팁: 뭘 읽을 수 있고, 뭐가 닿고, 뭘 보낼 수 있는지 조금 더 자세히 적고 다시 해봐.",
 "el1": "네 중요한 데이터를 읽을 수 있음",
 "el2": "다른 사람이 보낸 걸 읽음",
 "el3": "밖으로 보낼 수 있음",
 "of_powers": "3가지 힘 중",
 "powers_fmt": "3가지 힘 중 {n}개",
 "attach_error": "그 파일은 읽지 못했어 — 일반 텍스트 파일이 가장 좋아.",
 "chips_hint": "하나 눌러 — 아니면 아래에 직접 답을 써줘.",
 "plus": "플러스:",
 "venn_hint": "검사하면 세 가지 파워가 여기에 켜져요.",
 "chip_safe": "시도: 안전한 설정",
 "chip_risky": "시도: 위험한 설정",
 "chip_lethal": "시도: 치명적인 설정",
 "sample_safe": "개인 메모 도우미. 이 기기의 내 메모만 읽고, 타인의 링크/파일은 열지 않으며, 메시지 전송·게시 불가.",
 "sample_risky": "리서치 도우미. 내 문서를 읽고 웹·포럼 글을 요약함. 메시지 전송·외부 변경 불가.",
 "sample_lethal": "받은편지함 에이전트. 내 비공개 메일·파일을 읽고, 받은 링크·첨부파일을 열며, 대신 메일 답장·Slack 게시 가능.",
}
for _key, _val in _KO_STRINGS.items():
    STRINGS[_key]["ko"] = _val
_KO_TITLES = ["질문 1 — 어떤 private 데이터를 읽을 수 있어?", "질문 2 — 다른 사람에게서 뭐가 닿아?", "질문 3 — 밖으로 뭘 보내거나 할 수 있어?", "마지막으로 — 이런 것도 있어?"]
_KO_ITEMS = [
 [
  "Gmail",
  "기타 이메일",
  "캘린더",
  "연락처",
  "클라우드 드라이브 (구글 드라이브 등)",
  "컴퓨터에 있는 파일",
  "채팅 / 메시지 기록"
 ],
 [
  "받는 이메일",
  "여는 웹페이지",
  "사람들이 올린 파일",
  "사용자의 채팅 메시지",
  "웹훅 / 다른 시스템의 트리거"
 ],
 [
  "이메일 보내기",
  "채팅 채널에 메시지 올리기",
  "다이렉트 메시지 보내기",
  "웹 주소로 데이터 보내기",
  "데이터를 밖으로 보내는 코드 실행"
 ],
 [
  "사람에게 묻지 않고 행동함",
  "혼자서 코드를 실행함",
  "오래 기억함"
 ]
]
for _group, _title, _items in zip(GROUPS, _KO_TITLES, _KO_ITEMS):
    _group["title"]["ko"] = _title
    for (_token, _label), _ko in zip(_group["items"], _items):
        _label["ko"] = _ko
QUESTIONS = {
    "reads_private": "q_reads_private",
    "reads_untrusted": "q_reads_untrusted",
    "sends_out": "q_sends_out",
    "human_approval": "q_human_approval",
}

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trifecta Checker — is your AI agent safe?</title>
<link rel="icon" type="image/webp" href="__FAVICON__">
<style>
 body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;background:#0f172a;color:#e2e8f0}
 main{max-width:760px;margin:0 auto;padding:20px 16px 48px}
 h1{font-size:24px;margin:0}
 .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;margin:16px 0}
 button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:12px 16px;font-size:16px;cursor:pointer;min-height:48px}
 fieldset{border:1px solid #334155;border-radius:8px;margin:0 0 14px;padding:6px 12px 10px}
 legend{padding:0 6px;color:#93c5fd;font-size:15px;font-weight:600}
 label{display:flex;align-items:center;gap:10px;padding:9px 4px;cursor:pointer;font-size:16px;border-radius:6px}
 label:active{background:#273549}
 input[type=checkbox]{width:22px;height:22px;flex:none;accent-color:#2563eb}
 select,input[type=text]{background:#0b1220;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:10px;font-size:16px}
 input[type=text]{width:100%;box-sizing:border-box}
 .badge{font-weight:700;padding:3px 12px;border-radius:999px;color:#0b1220}
 .Low{background:#4ade80}.Risky{background:#facc15}.Lethal{background:#f87171}
 .elem{display:inline-block;margin:4px 6px 0 0;padding:4px 10px;border-radius:999px;font-size:13px}
 .elem.on{background:#7f1d1d;color:#fecaca}.elem.off{background:#164e2a;color:#bbf7d0}
 pre{white-space:pre-wrap;font-size:14px;line-height:1.6;margin:8px 0 0;font-family:inherit}
 .muted{color:#94a3b8;font-size:13px}
 details.card summary{cursor:pointer;font-size:17px;font-weight:600;padding:2px 0}
 .row{display:flex;gap:10px;align-items:flex-end;margin-top:10px}
 .topbar{display:flex;justify-content:space-between;align-items:center;gap:12px}
 .brand{display:flex;align-items:center;gap:12px}
 .mascot{width:52px;height:52px;border-radius:50%;object-fit:cover;background:#f5f0e6}
 .avatar{width:30px;height:30px;border-radius:50%;object-fit:cover;background:#f5f0e6;flex:none;margin-top:2px}
 #chat{display:flex;flex-direction:column;gap:12px;margin:18px 0}
 .msg{display:flex;gap:8px;max-width:100%}
 .msg.user{justify-content:flex-end}
 .bubble{border-radius:14px;padding:10px 14px;font-size:15px;line-height:1.55;max-width:85%}
 .msg.user .bubble{background:#2563eb;color:#fff;border-bottom-right-radius:4px}
 .msg.bot .bubble{background:#1e293b;border:1px solid #334155;border-bottom-left-radius:4px}
 .chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
 .chip{background:#0b1220;border:1px solid #2563eb;color:#93c5fd;border-radius:999px;padding:8px 14px;font-size:14px;min-height:40px;cursor:pointer}
 .chip:disabled{opacity:.45;cursor:default}
 .dots span{display:inline-block;width:7px;height:7px;border-radius:50%;background:#93c5fd;margin-right:4px;animation:blink 1.2s infinite}
 .dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
 @keyframes blink{0%,80%,100%{opacity:.25}40%{opacity:1}}
 .inputbar{position:sticky;bottom:0;background:#0f172a;padding:10px 0 4px}
 .composer{display:flex;gap:8px;align-items:flex-end;background:#1e293b;border:1px solid #334155;border-radius:20px;padding:8px}
 textarea{flex:1;min-height:44px;max-height:180px;background:transparent;color:#e2e8f0;border:0;outline:none;padding:8px 4px;font-size:16px;line-height:1.5;box-sizing:border-box;resize:none;overflow-y:auto;scrollbar-width:none}
 textarea::-webkit-scrollbar{display:none}
 .iconbtn{border-radius:50%;width:44px;height:44px;flex:none;font-size:19px;padding:0;min-height:44px;background:#2563eb}
 .iconbtn.ghost{background:transparent;border:0;color:#cbd5e1}
 #recbar{display:none;gap:10px;align-items:center;background:#1e293b;border:1px solid #334155;border-radius:20px;padding:8px}
 #recbar.on{display:flex}
 #rectime{color:#94a3b8;font-size:14px;min-width:34px;text-align:center}
 #wave{flex:1;display:flex;gap:2px;align-items:center;height:26px;overflow:hidden}
 #wave span{flex:1;min-width:2px;height:5px;background:#60a5fa;border-radius:2px}
 #wave.cssanim span{animation:wv .9s ease-in-out infinite}
 #wave.cssanim span:nth-child(2n){animation-delay:.15s}#wave.cssanim span:nth-child(3n){animation-delay:.3s}#wave.cssanim span:nth-child(4n){animation-delay:.45s}
 @keyframes wv{0%,100%{height:5px}50%{height:20px}}
 #trifectaPanel{
   background:#1e293b;
   border:1px solid #334155;
   border-radius:12px;
   padding:16px;
   margin:16px 0;
   display:flex;
   gap:16px;
   align-items:center;
   flex-wrap:wrap;
   transition:border-color .3s;
 }
 #trifectaPanel.lethal{
   border-color:#f87171;
   box-shadow:0 0 0 1px #f87171,0 0 22px rgba(248,113,113,.35);
 }

 .vcircle{
   fill:rgba(100,116,139,.18);
   stroke:#64748b;
   stroke-width:2;
   transition:all .3s;
 }
 .vcircle.on.el-data{fill:rgba(37,99,235,.30);stroke:#2563eb;}
 .vcircle.on.el-untrusted{fill:rgba(147,51,234,.30);stroke:#9333ea;}
 .vcircle.on.el-outbound{fill:rgba(234,88,12,.30);stroke:#ea580c;}

 #vcenter{fill:#ef4444;opacity:0;pointer-events:none;}
 #vcenter.on{opacity:.55;animation:vpulse 1.1s ease-in-out infinite;}
 @keyframes vpulse{0%,100%{opacity:.25}50%{opacity:.65}}

 .vlegend{
   display:flex;
   flex-direction:column;
   gap:4px;
   font-size:13px;
 }
 .vlegend .dot{
   display:inline-block;
   width:10px;
   height:10px;
   border-radius:50%;
   margin-right:6px;
 }

 .traficaBox{margin:0;text-align:center;}
 .traficaWrap{position:relative;display:inline-block;border-radius:50%;}
 #traficaImg{
   width:96px;
   height:96px;
   border-radius:50%;
   object-fit:cover;
   background:#f5f0e6;
   display:block;
 }
 .traficaWrap.st-risky #traficaImg{
   box-shadow:0 0 0 3px #f59e0b,0 0 18px rgba(245,158,11,.55);
 }
 .traficaWrap.st-lethal #traficaImg{
   box-shadow:0 0 0 3px #ef4444,0 0 20px rgba(239,68,68,.65);
   animation:vpulse2 1.1s ease-in-out infinite;
 }
 @keyframes vpulse2{
   0%,100%{box-shadow:0 0 0 3px #ef4444,0 0 10px rgba(239,68,68,.4)}
   50%{box-shadow:0 0 0 4px #ef4444,0 0 26px rgba(239,68,68,.8)}
 }
 .traficaWrap.shake{animation:tshake .45s ease-in-out 1;}
 @keyframes tshake{
   0%,100%{transform:translateX(0)}
   25%{transform:translateX(-4px)}
   75%{transform:translateX(4px)}
 }

 .tbadge{
   position:absolute;
   top:-2px;
   right:-2px;
   width:26px;
   height:26px;
   border-radius:50%;
   color:#0b1220;
   font-weight:800;
   font-size:16px;
   line-height:26px;
   text-align:center;
 }
 .tbadge.risky{background:#f59e0b;}
 .tbadge.lethal{background:#ef4444;color:#fff;}

 #traficaStatus{margin-top:6px;max-width:180px;}

 .samplebar{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 8px;}
 @media (min-width:720px){
   main{max-width:920px}
   .qgrid{display:grid;grid-template-columns:1fr 1fr;gap:0 14px;align-items:start}
 }
</style></head><body><main>
<div class="topbar">
 <div class="brand"><img class="mascot" src="__MASCOT__" alt=""><h1>Trifecta Checker</h1></div>
 <label style="padding:0;font-size:14px"><span data-i18n="lang_label"></span>
  <select id="lang" onchange="setLang(this.value)">
   <option value="en">English</option><option value="ja">日本語</option>
   <option value="zh">中文（简体）</option><option value="hi">हिन्दी</option><option value="es">Español</option><option value="ko">한국어</option>
  </select></label>
</div>
<section id="trifectaPanel">
  <svg id="venn" viewBox="0 0 200 172" width="200" height="172" role="img" aria-label="trifecta diagram">
    <circle id="vc1" class="vcircle el-data" cx="72" cy="64" r="52"></circle>
    <circle id="vc2" class="vcircle el-untrusted" cx="128" cy="64" r="52"></circle>
    <circle id="vc3" class="vcircle el-outbound" cx="100" cy="112" r="52"></circle>
    <circle id="vcenter" cx="100" cy="80" r="17"></circle>
  </svg>
  <div class="vlegend">
    <span><span class="dot" style="background:#2563eb"></span><span data-i18n="el1"></span></span>
    <span><span class="dot" style="background:#9333ea"></span><span data-i18n="el2"></span></span>
    <span><span class="dot" style="background:#ea580c"></span><span data-i18n="el3"></span></span>
    <span id="vennHint" class="muted" data-i18n="venn_hint"></span>
  </div>
  <figure class="traficaBox">
    <div class="traficaWrap" id="traficaWrap">
      <img id="traficaImg" src="__MASCOT__" alt="Trafica">
      <span id="traficaBadge" class="tbadge risky" hidden>!</span>
    </div>
    <figcaption id="traficaStatus" class="muted"></figcaption>
  </figure>
</section>
<div id="chat"></div>

<div class="inputbar">
 <div id="samplebar" class="samplebar">
  <button class="chip" data-i18n="chip_safe" onclick="fillSample('safe')"></button>
  <button class="chip" data-i18n="chip_risky" onclick="fillSample('risky')"></button>
  <button class="chip" data-i18n="chip_lethal" onclick="fillSample('lethal')"></button>
</div>
 <div id="composer" class="composer">
  <button id="attachbtn" class="iconbtn ghost" onclick="document.getElementById('filein').click()" title="add a text file">＋</button>
  <textarea id="desc" rows="1"></textarea>
  <button id="micbtn" class="iconbtn ghost" onclick="toggleMic()" title="voice input">🎤</button>
  <button id="sendbtn" class="iconbtn" onclick="sendText()" title="check">↑</button>
 </div>
 <div id="recbar">
  <button class="iconbtn ghost" onclick="discardVoice()" title="discard">🗑</button>
  <span id="rectime">0:00</span>
  <div id="wave"></div>
  <button class="iconbtn ghost" onclick="stopVoiceKeep()" title="stop">⏹</button>
  <button class="iconbtn" onclick="sendVoice()" title="send">↑</button>
 </div>
 <input type="file" id="filein" hidden accept=".txt,.md,.json,.yaml,.yml,.csv,.log,text/plain,text/markdown,application/json">
</div>

<p class="muted" data-i18n="footer"></p>
<p class="muted" data-i18n="privacy_note"></p>
</main><script>
const DATA = __DATA__;
const MASCOT = "__MASCOT__";
const MASCOT_LOW = "__MASCOT_LOW__";
let lang = "en";
let profile = null, verdict = null;
function t(key){ return (DATA.strings[key] || {})[lang] || (DATA.strings[key] || {})["en"] || ""; }
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")}
function scrollDown(){ window.scrollTo({top: document.body.scrollHeight, behavior:"smooth"}); }
function addUser(text){
  const d = document.createElement("div"); d.className = "msg user";
  d.innerHTML = '<div class="bubble"></div>';
  d.querySelector(".bubble").textContent = text;
  document.getElementById("chat").appendChild(d); scrollDown(); return d;
}
function addBot(html){
  const d = document.createElement("div"); d.className = "msg bot";
  d.innerHTML = '<img class="avatar" src="'+MASCOT+'" alt=""><div class="bubble">'+html+"</div>";
  document.getElementById("chat").appendChild(d); scrollDown(); return d;
}
function addThinking(){
  return addBot('<span class="muted">'+esc(t("thinking"))+'</span> <span class="dots"><span></span><span></span><span></span></span>');
}
function verdictHTML(v, prefix){
  const el = [[t("el1"), v.elements.data_access], [t("el2"), v.elements.untrusted_input], [t("el3"), v.elements.outbound]];
  let h = (prefix ? '<div style="margin-bottom:6px">'+esc(prefix)+"</div>" :
           '<div style="margin-bottom:6px">'+esc(t("verdict_say").replace("{v}", v.verdict))+"</div>") +
    '<span class="badge '+v.verdict+'">'+v.verdict+'</span> '+
    '<span class="muted">'+t("powers_fmt").replace("{n}", v.element_count)+
    (v.amplifiers.length ? " · "+t("plus")+" "+v.amplifiers.length : "")+'</span><div style="margin-top:6px">';
  for (const [name,on] of el)
    h += '<span class="elem '+(on?"on":"off")+'">'+(on?"✓ ":"✗ ")+name+"</span>";
  return h + "</div>";
}
function updateTrifecta(v) {
  if (!v || !v.elements) return;

  var panel = document.getElementById("trifectaPanel");
  var vc1 = document.getElementById("vc1");
  var vc2 = document.getElementById("vc2");
  var vc3 = document.getElementById("vc3");
  var vcenter = document.getElementById("vcenter");
  var vennHint = document.getElementById("vennHint");

  var traficaWrap = document.getElementById("traficaWrap");
  var traficaImg = document.getElementById("traficaImg");
  var traficaBadge = document.getElementById("traficaBadge");
  var traficaStatus = document.getElementById("traficaStatus");

  if (vc1) vc1.classList.toggle("on", !!v.elements.data_access);
  if (vc2) vc2.classList.toggle("on", !!v.elements.untrusted_input);
  if (vc3) vc3.classList.toggle("on", !!v.elements.outbound);

  var count = 0;
  if (v.elements.data_access) count++;
  if (v.elements.untrusted_input) count++;
  if (v.elements.outbound) count++;

  var lethal = count === 3;

  if (vcenter) vcenter.classList.toggle("on", lethal);
  if (panel) panel.classList.toggle("lethal", lethal);
  if (vennHint) vennHint.style.display = "none";

  if (traficaWrap) {
    traficaWrap.classList.remove("st-risky", "st-lethal");
  }

  if (v.verdict === "Low") {
    if (traficaImg) traficaImg.src = MASCOT_LOW;
    if (traficaBadge) traficaBadge.hidden = true;
  } else if (v.verdict === "Risky") {
    if (traficaImg) traficaImg.src = MASCOT;
    if (traficaWrap) traficaWrap.classList.add("st-risky");
    if (traficaBadge) {
      traficaBadge.hidden = false;
      traficaBadge.className = "tbadge risky";
    }
  } else if (v.verdict === "Lethal") {
    if (traficaImg) traficaImg.src = MASCOT;
    if (traficaWrap) {
      traficaWrap.classList.add("st-lethal");
      traficaWrap.classList.remove("shake");
      void traficaWrap.offsetWidth;
      traficaWrap.classList.add("shake");
    }
    if (traficaBadge) {
      traficaBadge.hidden = false;
      traficaBadge.className = "tbadge lethal";
    }
  }

  if (traficaStatus) {
    traficaStatus.textContent = t("verdict_say").replace("{v}", v.verdict);
  }
}

function fillSample(kind) {
  var ta = document.getElementById("desc");
  if (!ta) return;
  ta.value = t("sample_" + kind);
  autogrow();
  ta.focus();
}
async function post(url, body){
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  const d = await r.json();
  if (!d.ok) throw new Error(d.error || "failed");
  return d.result;
}
function chipsHTML(items){
  let h = '<div class="chips">';
  items.forEach((it, i) => { h += '<button class="chip" data-chip="'+i+'">'+esc(it.label)+"</button>"; });
  return h + "</div>";
}
function wireChips(bubbleEl, items){
  bubbleEl.querySelectorAll("[data-chip]").forEach(btn => {
    btn.onclick = () => {
      bubbleEl.querySelectorAll("[data-chip]").forEach(b => b.disabled = true);
      items[Number(btn.dataset.chip)].fn();
    };
  });
}
const EDITS = {
  reads_private: (p, ans) => { if (ans === "yes" && !p.data_access.includes("local_files")) p.data_access.push("local_files"); },
  reads_untrusted: (p, ans) => { if (ans === "yes" && !p.untrusted_inputs.includes("web_browse")) p.untrusted_inputs.push("web_browse"); },
  sends_out: (p, ans) => { if (ans === "yes" && !p.outbound.includes("http_post")) p.outbound.push("http_post"); },
  human_approval: (p, ans) => {
    if (ans === "no" && !p.amplifiers.includes("no_human_approval")) p.amplifiers.push("no_human_approval");
    if (ans === "yes") p.amplifiers = p.amplifiers.filter(a => a !== "no_human_approval");
  },
};
function levelOf(p){
  const e = (p.data_access.length?1:0)+(p.untrusted_inputs.length?1:0)+(p.outbound.length?1:0);
  if (e === 3) return 2;
  if (e === 2 || (e === 1 && p.amplifiers.length)) return 1;
  return 0;
}
function pickQuestions(result){
  // Ask at most ONE follow-up, and only when the answer could change the verdict.
  const cur = levelOf(result.profile);
  for (const key of result.unclear || []){
    const p2 = JSON.parse(JSON.stringify(result.profile));
    EDITS[key](p2, key === "human_approval" ? "no" : "yes");
    if (levelOf(p2) !== cur) return [key];
  }
  return [];
}
let runSeq = 0, qInterrupt = null, lastText = "";
async function askQuestions(keys){
  const my = runSeq;
  for (const key of keys){
    const qkey = DATA.questions[key]; if (!qkey) continue;
    const ans = await new Promise(resolve => {
      const m = addBot(esc(t(qkey)) + chipsHTML([
        {label: t("yes")}, {label: t("no")}, {label: t("unsure")}]) +
        '<div class="muted" style="margin-top:8px">'+esc(t("chips_hint"))+"</div>");
      const bubble = m.querySelector(".bubble");
      qInterrupt = () => { bubble.querySelectorAll("[data-chip]").forEach(b => b.disabled = true); resolve("typed"); };
      wireChips(bubble, [
        {label: t("yes"), fn: () => { qInterrupt = null; resolve("yes"); }},
        {label: t("no"), fn: () => { qInterrupt = null; resolve("no"); }},
        {label: t("unsure"), fn: () => { qInterrupt = null; resolve("unsure"); }},
      ]);
    });
    if (ans === "typed" || my !== runSeq) return false;
    addUser(t(ans === "yes" ? "yes" : ans === "no" ? "no" : "unsure"));
    EDITS[key](profile, ans);
  }
  const think = addThinking();
  try{
    const r = await post("/api/check-profile", {profile});
    think.querySelector(".bubble").innerHTML = verdictHTML(r.verdict, t("verdict_updated"));
    verdict = r.verdict; updateTrifecta(verdict);
  }catch(e){ think.querySelector(".bubble").textContent = t("error_prefix") + e.message; }
  return true;
}
async function explainFlow(){
  const m = addBot('<span class="muted">'+esc(t("exp_loading"))+"</span>");
  try{
    const exp = await post("/api/explain", {verdict, profile, lang});
    m.querySelector(".bubble").innerHTML = "<pre></pre>";
    m.querySelector("pre").textContent = exp.explanation;
  }catch(e){
    m.querySelector(".bubble").textContent = t("exp_unavailable") + e.message + ")";
  }
}
async function showSplit(){
  const think = addThinking();
  try{
    const a = JSON.parse(JSON.stringify(profile)); a.outbound = [];
    const b = JSON.parse(JSON.stringify(profile)); b.untrusted_inputs = [];
    const ra = await post("/api/check-profile", {profile: a});
    const rb = await post("/api/check-profile", {profile: b});
    think.querySelector(".bubble").innerHTML = esc(t("split_intro")) +
      '<div style="margin-top:8px">'+esc(t("var_no_out"))+' → <span class="badge '+ra.verdict.verdict+'">'+ra.verdict.verdict+"</span></div>"+
      '<div style="margin-top:6px">'+esc(t("var_no_untrusted"))+' → <span class="badge '+rb.verdict.verdict+'">'+rb.verdict.verdict+"</span></div>";
  }catch(e){ think.querySelector(".bubble").textContent = t("error_prefix") + e.message; }
}
async function runCheck(url, body, isText){
  const my = ++runSeq;
  const think = addThinking();
  try{
    const result = await post(url, body);
    if (my !== runSeq) return;
    profile = result.profile; verdict = result.verdict; updateTrifecta(verdict);
    think.querySelector(".bubble").innerHTML = verdictHTML(verdict, "");
    if (isText){
      const qs = pickQuestions(result);
      if (qs.length){
        const ok = await askQuestions(qs);
        if (!ok || my !== runSeq) return;
      }
    }
    await explainFlow();
  }catch(e){
    if (my !== runSeq) return;
    think.querySelector(".bubble").innerHTML = esc(t("error_prefix") + String(e.message)) +
      '<br><span class="muted">'+esc(t("error_tip"))+"</span>";
  }finally{ scrollDown(); }
}
async function runFollowup(text){
  const my = ++runSeq;
  const think = addThinking();
  try{
    const r = await post("/api/followup", {message: text, profile, verdict, lang});
    if (my !== runSeq) return;
    if (r.action === "new"){
      think.remove(); lastText = text;
      runCheck("/api/check", {text}, true);
      return;
    }
    if (r.reply){
      think.querySelector(".bubble").innerHTML = "<pre></pre>";
      think.querySelector("pre").textContent = r.reply;
    } else think.remove();
    if (r.action === "split") await showSplit();
  }catch(e){
    think.remove(); lastText = text;
    runCheck("/api/check", {text}, true);
  }
}
function stopVoice(){ if (listening) stopVoiceKeep(); }
function sendText(){
  const box = document.getElementById("desc");
  const text = box.value.trim(); if (!text) return;
  box.value = ""; autogrow();
  stopVoice();
  started = true;
  addUser(text);
  if (qInterrupt){
    const f = qInterrupt; qInterrupt = null; runSeq++; f();
    lastText = (lastText + " " + text).trim();
    runCheck("/api/check", {text: lastText}, true);
  } else if (verdict){
    runFollowup(text);
  } else {
    lastText = text;
    runCheck("/api/check", {text}, true);
  }
}
let started = false;
function setLang(l){
  lang = l;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.innerHTML = t(el.dataset.i18n); });
  document.getElementById("desc").placeholder = t("placeholder");
  const g = document.getElementById("greeting");
  if (g && !started) g.innerHTML = esc(t("greeting")).replaceAll("\\n", "<br>");
  // [setLang hook]
  if (typeof verdict !== "undefined" && verdict && document.getElementById("traficaStatus")) {
    document.getElementById("traficaStatus").textContent = t("verdict_say").replace("{v}", verdict.verdict);
  }
  autogrow();
}
const SPEECH_LANG = {en: "en-US", ja: "ja-JP", zh: "zh-CN", hi: "hi-IN", es: "es-ES"};
let recog = null, listening = false, voiceBase = "", recStart = 0, recTimer = null;
let micStream = null, audioCtx = null, analyser = null;
function waveEl(){ return document.getElementById("wave"); }
function buildWave(){
  const w = waveEl();
  if (!w.children.length) for (let i = 0; i < 36; i++) w.appendChild(document.createElement("span"));
}
function fmtTime(ms){ const s = Math.floor(ms/1000); return Math.floor(s/60)+":"+String(s%60).padStart(2,"0"); }
async function startWave(){
  buildWave();
  try{
    micStream = await navigator.mediaDevices.getUserMedia({audio: true});
    if (!listening){ micStream.getTracks().forEach(tr => tr.stop()); micStream = null; return; }
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const src = audioCtx.createMediaStreamSource(micStream);
    analyser = audioCtx.createAnalyser(); analyser.fftSize = 128;
    src.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    const bars = waveEl().children;
    const loop = () => {
      if (!listening || !analyser) return;
      analyser.getByteFrequencyData(data);
      for (let i = 0; i < bars.length; i++){
        const v = data[Math.floor(i*data.length/bars.length)]/255;
        bars[i].style.height = (3 + v*22) + "px";
      }
      requestAnimationFrame(loop);
    };
    loop();
  }catch(_){ waveEl().classList.add("cssanim"); }
}
function stopWave(){
  if (micStream){ micStream.getTracks().forEach(tr => tr.stop()); micStream = null; }
  if (audioCtx){ audioCtx.close().catch(() => {}); audioCtx = null; }
  analyser = null;
  waveEl().classList.remove("cssanim");
}
function endVoiceUI(){
  listening = false;
  if (recTimer){ clearInterval(recTimer); recTimer = null; }
  stopWave();
  document.getElementById("recbar").classList.remove("on");
  document.getElementById("composer").style.display = "flex";
}
function toggleMic(){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return;
  if (listening){ stopVoiceKeep(); return; }
  recog = new SR();
  recog.lang = SPEECH_LANG[lang] || "en-US";
  recog.interimResults = true;
  recog.continuous = true;
  const box = document.getElementById("desc");
  voiceBase = box.value;
  recog.onresult = (e) => {
    let s = "";
    for (const r of e.results) s += r[0].transcript;
    box.value = voiceBase + (voiceBase && s ? " " : "") + s;
    autogrow();
  };
  recog.onend = () => { if (listening) endVoiceUI(); };
  recog.onerror = () => { if (listening) endVoiceUI(); };
  recog.start();
  listening = true;
  document.getElementById("composer").style.display = "none";
  document.getElementById("recbar").classList.add("on");
  recStart = Date.now();
  document.getElementById("rectime").textContent = "0:00";
  recTimer = setInterval(() => { document.getElementById("rectime").textContent = fmtTime(Date.now() - recStart); }, 500);
  startWave();
}
function stopVoiceKeep(){
  if (recog){ recog.onresult = null; recog.onend = null; recog.onerror = null; try{ recog.stop(); }catch(_){} }
  endVoiceUI();
}
function discardVoice(){
  document.getElementById("desc").value = voiceBase; autogrow();
  stopVoiceKeep();
}
function sendVoice(){ stopVoiceKeep(); sendText(); }
function autogrow(){
  const box = document.getElementById("desc");
  box.style.height = "auto";
  box.style.height = Math.min(box.scrollHeight, 180) + "px";
}
const INIT_LANG = (navigator.language || "en").slice(0, 2);
document.getElementById("lang").value = ["en","ja","zh","hi","es"].includes(INIT_LANG) ? INIT_LANG : "en";
setLang(document.getElementById("lang").value);
addBot('<span id="greeting"></span>');
document.getElementById("greeting").innerHTML = esc(t("greeting")).replaceAll("\\n", "<br>");
if (!(window.SpeechRecognition || window.webkitSpeechRecognition))
  document.getElementById("micbtn").style.display = "none";
document.getElementById("desc").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing){ e.preventDefault(); sendText(); }
});
document.getElementById("desc").addEventListener("input", autogrow);
window.addEventListener("resize", autogrow);
function describeUpload(text, name){
  try{
    const obj = JSON.parse(text);
    if (obj && typeof obj === "object"){
      const servers = obj.mcpServers || obj.mcp_servers || obj.servers;
      if (servers && typeof servers === "object"){
        const lines = ["Agent configuration file (" + name + ") using these MCP servers:"];
        for (const [sname, cfg] of Object.entries(servers)){
          const parts = [];
          if (cfg && cfg.command) parts.push("runs: " + cfg.command + (Array.isArray(cfg.args) ? " " + cfg.args.join(" ") : ""));
          if (cfg && cfg.url) parts.push("connects to: " + cfg.url);
          lines.push("- " + sname + (parts.length ? ": " + parts.join("; ") : ""));
        }
        return lines.join("\\n");
      }
      return "Agent configuration file (" + name + "):\\n" + JSON.stringify(obj).slice(0, 3000);
    }
  }catch(_){}
  return text;
}
document.getElementById("filein").addEventListener("change", async (e) => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f) return;
  try{
    if (f.size > 200000) throw new Error("too big");
    const text = await f.text();
    const box = document.getElementById("desc");
    box.value = (box.value ? box.value + "\\n" : "") + describeUpload(text, f.name).trim();
    autogrow(); box.focus();
  }catch(_){ addBot(esc(t("attach_error"))); }
});
</script></body></html>"""


def _b64_uri(filename: str, mime: str) -> str:
    b64 = BASE / filename
    if b64.is_file():
        return f"data:{mime};base64," + b64.read_text(encoding="utf-8").strip()
    return "/favicon.svg"


def page_html() -> bytes:
    data = {"strings": STRINGS, "questions": QUESTIONS}
    html = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__MASCOT__", _b64_uri("assets/mascot.b64.txt", "image/webp"))
    html = html.replace("__MASCOT_LOW__", _b64_uri("assets/trafica-low.b64.txt", "image/webp"))
    html = html.replace("__FAVICON__", _b64_uri("assets/favicon.b64.txt", "image/webp"))
    return html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, page_html(), "text/html; charset=utf-8")
        if self.path == "/favicon.svg":
            fav = BASE / "public" / "favicon.svg"
            if fav.is_file():
                return self._send(200, fav.read_bytes(), "image/svg+xml")
        if self.path.startswith("/fixtures/"):
            name = Path(self.path).name
            target = BASE / "fixtures" / name
            if target.is_file():
                return self._send(200, target.read_bytes(), "text/plain; charset=utf-8")
        return self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            check_body_size(length)
            check_rate(self.headers)
            payload = json.loads(self.rfile.read(length) or b"{}")
            lang = payload.get("lang", "en")
            if self.path == "/api/check":
                result = extract_and_judge(check_text(str(payload.get("text", ""))))
            elif self.path == "/api/check-profile":
                check_payload(payload.get("profile"))
                result = judge_profile(payload.get("profile", {}))
            elif self.path == "/api/explain":
                check_payload(payload.get("verdict"))
                check_payload(payload.get("profile"))
                result = explain_result(payload.get("verdict", {}),
                                        payload.get("profile"), lang=lang)
            elif self.path == "/api/followup":
                check_payload(payload.get("profile"))
                check_payload(payload.get("verdict"))
                result = followup(check_text(str(payload.get("message", "")),
                                             MAX_MESSAGE_CHARS),
                                  payload.get("profile"), payload.get("verdict"),
                                  lang=lang)
            else:
                return self._json(404, {"ok": False, "error": "unknown endpoint"})
            return self._json(200, {"ok": True, "result": result})
        except Exception as exc:
            return self._json(200, {"ok": False, "error": str(exc)})


def main():
    port = int(os.environ.get("PORT", "8765"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
