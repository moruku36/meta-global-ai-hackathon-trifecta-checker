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
from check import explain_result, extract_and_judge, judge_profile  # noqa: E402

BASE = Path(__file__).resolve().parent
LANGS = ["en", "ja", "zh", "hi", "es"]

# --- UI strings -------------------------------------------------------------
STRINGS = {
    "lead": {
        "en": "An AI agent gets dangerous when three powers combine: reading <b>private data</b>, taking in <b>content from other people</b>, and <b>sending data out</b>. Tell me about your agent — a rule engine (not an AI) gives the verdict; Muse Spark only helps read your words and explain the result.",
        "ja": "AIエージェントが危なくなるのは、3つの力が揃ったときです：<b>秘密のデータを読む</b>、<b>他人からの内容を受け取る</b>、<b>外へ送信する</b>。あなたのエージェントのことを教えてください。判定はAIではなくルールエンジンが行い、Muse Spark は文章の読み取りと説明だけを手伝います。",
        "zh": "当三种能力凑齐时，AI 智能体就会变得危险：<b>读取私人数据</b>、<b>接收他人发来的内容</b>、<b>向外发送数据</b>。请把您的智能体告诉我——判定由规则引擎（不是 AI）完成，Muse Spark 只帮忙读懂您的描述并解释结果。",
        "hi": "AI एजेंट तब खतरनाक बनता है जब तीन शक्तियाँ एक साथ मिलती हैं: <b>निजी डेटा पढ़ना</b>, <b>दूसरों की सामग्री ग्रहण करना</b>, और <b>बाहर डेटा भेजना</b>। मुझे अपने एजेंट के बारे में बताएँ — निर्णय एक नियम-आधारित इंजन (AI नहीं) देता है; Muse Spark सिर्फ़ आपके शब्दों को पढ़ने और परिणाम समझाने में मदद करता है।",
        "es": "Un agente de IA se vuelve peligroso cuando se combinan tres poderes: <b>leer datos privados</b>, <b>recibir contenido de otras personas</b> y <b>enviar datos fuera</b>. Cuéntame sobre tu agente: el veredicto lo da un motor de reglas (no una IA); Muse Spark solo ayuda a leer tu descripción y explicar el resultado.",
    },
    "lang_label": {"en": "Language", "ja": "言語", "zh": "语言", "hi": "भाषा", "es": "Idioma"},
    "greeting": {
        "en": "Hi! Tell me about your agent — what it can read, what reaches it, and what it can send. I'll check the combination.",
        "ja": "こんにちは！あなたのエージェントについて教えてください。何を読めて、何が届いて、何を送れるか。それで組み合わせを診断します。",
        "zh": "您好！请告诉我您的智能体能读什么、会收到什么、能发送什么，我来检查这个组合。",
        "hi": "नमस्ते! अपने एजेंट के बारे में बताएँ — यह क्या पढ़ सकता है, इसे क्या मिलता है, यह क्या भेज सकता है। मैं संयोजन की जाँच करूँगा।",
        "es": "¡Hola! Cuéntame sobre tu agente: qué puede leer, qué le llega y qué puede enviar. Revisaré la combinación.",
    },
    "placeholder": {
        "en": "Describe your agent here…",
        "ja": "エージェントの説明をここに書く…",
        "zh": "在这里描述您的智能体…",
        "hi": "अपने एजेंट का वर्णन यहाँ लिखें…",
        "es": "Describe tu agente aquí…",
    },
    "check_btn": {"en": "Check", "ja": "チェック", "zh": "检查", "hi": "जाँचें", "es": "Comprobar"},
    "mic_btn": {"en": "🎤", "ja": "🎤", "zh": "🎤", "hi": "🎤", "es": "🎤"},
    "thinking": {"en": "Thinking…", "ja": "考え中…", "zh": "思考中…", "hi": "सोच रहा हूँ…", "es": "Pensando…"},
    "yes": {"en": "Yes", "ja": "はい", "zh": "是", "hi": "हाँ", "es": "Sí"},
    "no": {"en": "No", "ja": "いいえ", "zh": "不是", "hi": "नहीं", "es": "No"},
    "unsure": {"en": "Not sure", "ja": "わからない", "zh": "不确定", "hi": "पता नहीं", "es": "No lo sé"},
    "q_reads_private": {
        "en": "One thing I couldn't tell: can it read private data (mail, files, calendar…)?",
        "ja": "1つ分からなかった点：秘密のデータ（メール・ファイル・予定など）を読めますか？",
        "zh": "有一点没看出来：它能读取私人数据（邮件、文件、日历等）吗？",
        "hi": "एक बात स्पष्ट नहीं हुई: क्या यह निजी डेटा (मेल, फ़ाइलें, कैलेंडर…) पढ़ सकता है?",
        "es": "Algo no quedó claro: ¿puede leer datos privados (correo, archivos, calendario…)?",
    },
    "q_reads_untrusted": {
        "en": "Can content from other people reach it (incoming mail, web pages, uploads)?",
        "ja": "他人からの内容（届くメール・Webページ・アップロードしたファイル）が届きますか？",
        "zh": "别人的内容（收到的邮件、网页、上传的文件）会到达它吗？",
        "hi": "क्या दूसरों की सामग्री (आने वाले मेल, वेब पेज, अपलोड की गई फ़ाइलें) इस तक पहुँचती है?",
        "es": "¿Le llega contenido de otras personas (correos recibidos, páginas web, archivos subidos)?",
    },
    "q_sends_out": {
        "en": "Can it send anything out on its own (mail, posts, data to a server)?",
        "ja": "自分から外へ送れますか（メール送信・投稿・サーバーへの送信）？",
        "zh": "它能自己向外发送东西吗（发邮件、发帖、向服务器发送数据）？",
        "hi": "क्या यह खुद बाहर कुछ भेज सकता है (मेल, पोस्ट, सर्वर पर डेटा)?",
        "es": "¿Puede enviar algo fuera por su cuenta (correos, publicaciones, datos a un servidor)?",
    },
    "q_human_approval": {
        "en": "Before it acts, does a person check and approve first?",
        "ja": "動く前に、人が確認して承認しますか？",
        "zh": "行动之前，会有人先检查并批准吗？",
        "hi": "काम करने से पहले क्या कोई व्यक्ति जाँचकर मंज़ूरी देता है?",
        "es": "Antes de actuar, ¿una persona lo revisa y aprueba primero?",
    },
    "verdict_updated": {"en": "Updated verdict:", "ja": "更新後の判定：", "zh": "更新后的判定：", "hi": "अद्यतन निर्णय:", "es": "Veredicto actualizado:"},
    "split_btn": {"en": "Show a safer split", "ja": "安全な分け方を見る", "zh": "看看更安全的拆分", "hi": "सुरक्षित बँटवारा देखें", "es": "Ver una división más segura"},
    "restart_btn": {"en": "Start over", "ja": "最初から", "zh": "重新开始", "hi": "फिर से शुरू करें", "es": "Empezar de nuevo"},
    "split_intro": {
        "en": "If the powers are split across two agents, the ratings become:",
        "ja": "力を2つのエージェントに分けると、判定はこうなります：",
        "zh": "把能力拆到两个智能体上，评级会变成：",
        "hi": "शक्तियों को दो एजेंटों में बाँटने पर रेटिंग ऐसी होगी:",
        "es": "Si los poderes se dividen entre dos agentes, las calificaciones serían:",
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
    "exp_loading": {
        "en": "Writing the plain-language explanation…",
        "ja": "平易な説明を書いています…",
        "zh": "正在撰写通俗说明…",
        "hi": "सरल भाषा में व्याख्या लिखी जा रही है…",
        "es": "Escribiendo la explicación en lenguaje sencillo…",
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
    "el1": {"en": "Reads private data", "ja": "個人データを読む", "zh": "读取私人数据", "hi": "निजी डेटा पढ़ता है", "es": "Lee datos privados"},
    "el2": {"en": "Takes in others' content", "ja": "他人の内容を受け取る", "zh": "接收他人内容", "hi": "दूसरों की सामग्री ग्रहण करता है", "es": "Recibe contenido de otros"},
    "el3": {"en": "Can send data out", "ja": "外へ送信できる", "zh": "能向外发送", "hi": "बाहर भेज सकता है", "es": "Puede enviar datos fuera"},
    "of_powers": {"en": "of the 3 powers", "ja": "3つの力のうち", "zh": "三项能力中占", "hi": "3 शक्तियों में से", "es": "de los 3 poderes"},
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
 .lead{color:#cbd5e1;font-size:14px;line-height:1.55}
 .lead b{color:#fff}
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
 textarea{flex:1;min-height:52px;max-height:140px;background:#0b1220;color:#e2e8f0;border:1px solid #334155;border-radius:10px;padding:12px;font-size:16px;box-sizing:border-box;resize:vertical}
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
   <option value="zh">中文（简体）</option><option value="hi">हिन्दी</option><option value="es">Español</option>
  </select></label>
</div>
<p class="lead" data-i18n="lead"></p>

<div id="chat"></div>

<div class="inputbar">
 <div class="row" style="margin-top:0">
  <textarea id="desc" rows="2"></textarea>
  <button id="micbtn" onclick="toggleMic()" title="voice input">🎤</button>
  <button onclick="sendText()" data-i18n="check_btn"></button>
 </div>
</div>

<p class="muted" data-i18n="footer"></p>
</main><script>
const DATA = __DATA__;
const MASCOT = "__MASCOT__";
let lang = "en";
let profile = null, verdict = null, busy = false;
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
  let h = (prefix ? '<div style="margin-bottom:6px">'+esc(prefix)+"</div>" : "") +
    '<span class="badge '+v.verdict+'">'+v.verdict+'</span> '+
    '<span class="muted">'+v.element_count+" "+t("of_powers")+
    (v.amplifiers.length ? " · "+t("plus")+" "+v.amplifiers.length : "")+'</span><div style="margin-top:6px">';
  for (const [name,on] of el)
    h += '<span class="elem '+(on?"on":"off")+'">'+(on?"✓ ":"✗ ")+name+"</span>";
  return h + "</div>";
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
async function askQuestions(keys){
  for (const key of keys){
    const qkey = DATA.questions[key]; if (!qkey) continue;
    const ans = await new Promise(resolve => {
      const m = addBot(esc(t(qkey)) + chipsHTML([
        {label: t("yes")}, {label: t("no")}, {label: t("unsure")}]));
      wireChips(m.querySelector(".bubble"), [
        {label: t("yes"), fn: () => resolve("yes")},
        {label: t("no"), fn: () => resolve("no")},
        {label: t("unsure"), fn: () => resolve("unsure")},
      ]);
    });
    addUser(t(ans === "yes" ? "yes" : ans === "no" ? "no" : "unsure"));
    EDITS[key](profile, ans);
  }
  const think = addThinking();
  try{
    const r = await post("/api/check-profile", {profile});
    think.querySelector(".bubble").innerHTML = verdictHTML(r.verdict, t("verdict_updated"));
    verdict = r.verdict;
  }catch(e){ think.querySelector(".bubble").textContent = t("error_prefix") + e.message; }
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
  const acts = addBot(chipsHTML([{label: t("split_btn")}, {label: t("restart_btn")}]));
  wireChips(acts.querySelector(".bubble"), [
    {label: t("split_btn"), fn: showSplit},
    {label: t("restart_btn"), fn: () => location.reload()},
  ]);
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
  if (busy) return; busy = true;
  const think = addThinking();
  try{
    const result = await post(url, body);
    profile = result.profile; verdict = result.verdict;
    think.querySelector(".bubble").innerHTML = verdictHTML(verdict, "");
    if (isText && result.unclear && result.unclear.length) await askQuestions(result.unclear);
    await explainFlow();
  }catch(e){
    think.querySelector(".bubble").innerHTML = esc(t("error_prefix") + String(e.message)) +
      '<br><span class="muted">'+esc(t("error_tip"))+"</span>";
  }finally{ busy = false; scrollDown(); }
}
function sendText(){
  const box = document.getElementById("desc");
  const text = box.value.trim(); if (!text || busy) return;
  box.value = "";
  started = true;
  addUser(text);
  runCheck("/api/check", {text}, true);
}
let started = false;
function setLang(l){
  lang = l;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.innerHTML = t(el.dataset.i18n); });
  document.getElementById("desc").placeholder = t("placeholder");
  const g = document.getElementById("greeting");
  if (g && !started) g.textContent = t("greeting");
}
const SPEECH_LANG = {en: "en-US", ja: "ja-JP", zh: "zh-CN", hi: "hi-IN", es: "es-ES"};
let recog = null, listening = false;
function toggleMic(){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return;
  const btn = document.getElementById("micbtn");
  if (listening){ recog.stop(); return; }
  recog = new SR();
  recog.lang = SPEECH_LANG[lang] || "en-US";
  recog.interimResults = true;
  recog.continuous = true;
  const box = document.getElementById("desc");
  const base = box.value;
  recog.onresult = (e) => {
    let s = "";
    for (const r of e.results) s += r[0].transcript;
    box.value = base + (base && s ? " " : "") + s;
  };
  recog.onend = () => { listening = false; btn.textContent = "🎤"; };
  recog.onerror = () => { listening = false; btn.textContent = "🎤"; };
  recog.start();
  listening = true;
  btn.textContent = "⏺";
}
const INIT_LANG = (navigator.language || "en").slice(0, 2);
document.getElementById("lang").value = ["en","ja","zh","hi","es"].includes(INIT_LANG) ? INIT_LANG : "en";
setLang(document.getElementById("lang").value);
addBot('<span id="greeting"></span>');
document.getElementById("greeting").textContent = t("greeting");
if (!(window.SpeechRecognition || window.webkitSpeechRecognition))
  document.getElementById("micbtn").style.display = "none";
document.getElementById("desc").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) sendText();
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
    html = html.replace("__MASCOT__", _b64_uri("mascot.b64.txt", "image/webp"))
    html = html.replace("__FAVICON__", _b64_uri("favicon.b64.txt", "image/webp"))
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
            payload = json.loads(self.rfile.read(length) or b"{}")
            lang = payload.get("lang", "en")
            if self.path == "/api/check":
                result = extract_and_judge(str(payload.get("text", "")))
            elif self.path == "/api/check-profile":
                result = judge_profile(payload.get("profile", {}))
            elif self.path == "/api/explain":
                result = explain_result(payload.get("verdict", {}),
                                        payload.get("profile"), lang=lang)
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
