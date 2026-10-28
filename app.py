#!/usr/bin/env python3
"""Trifecta Checker — minimal web UI (standard library only).

Two ways in:
  1. Describe your agent in plain words -> Muse Spark sorts it into
     capabilities -> the rule engine (not an LLM) gives the verdict ->
     Muse Spark explains the verdict in plain language.
  2. Answer three questions by ticking plain-language capabilities.
     No LLM is involved until the explanation step.

The whole page follows the language picker (en / ja / zh / hi / es):
UI strings and capability labels are rendered client-side from the
embedded I18N data below.

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
        "en": "An AI agent gets dangerous when three powers combine: reading <b>private data</b>, taking in <b>content from other people</b>, and <b>sending data out</b>. Describe your agent — a rule engine (not an AI) gives the verdict; Muse Spark only helps read your words and explain the result.",
        "ja": "AIエージェントが危なくなるのは、3つの力が揃ったときです：<b>秘密のデータを読む</b>、<b>他人からの内容を受け取る</b>、<b>外へ送信する</b>。あなたのエージェントを説明してください。判定はAIではなくルールエンジンが行い、Muse Spark は文章の読み取りと説明だけを手伝います。",
        "zh": "当三种能力凑齐时，AI 智能体就会变得危险：<b>读取私人数据</b>、<b>接收他人发来的内容</b>、<b>向外发送数据</b>。请描述您的智能体——判定由规则引擎（不是 AI）完成，Muse Spark 只帮忙读懂您的描述并解释结果。",
        "hi": "AI एजेंट तब खतरनाक बनता है जब तीन शक्तियाँ एक साथ मिलती हैं: <b>निजी डेटा पढ़ना</b>, <b>दूसरों की सामग्री ग्रहण करना</b>, और <b>बाहर डेटा भेजना</b>। अपने एजेंट का वर्णन करें — निर्णय एक नियम-आधारित इंजन (AI नहीं) देता है; Muse Spark सिर्फ़ आपके शब्दों को पढ़ने और परिणाम समझाने में मदद करता है।",
        "es": "Un agente de IA se vuelve peligroso cuando se combinan tres poderes: <b>leer datos privados</b>, <b>recibir contenido de otras personas</b> y <b>enviar datos fuera</b>. Describe tu agente: el veredicto lo da un motor de reglas (no una IA); Muse Spark solo ayuda a leer tu descripción y explicar el resultado.",
    },
    "lang_label": {"en": "Language", "ja": "言語", "zh": "语言", "hi": "भाषा", "es": "Idioma"},
    "describe_title": {"en": "Describe your agent", "ja": "エージェントを説明する", "zh": "描述您的智能体", "hi": "अपने एजेंट का वर्णन करें", "es": "Describe tu agente"},
    "describe_hint": {
        "en": "What it can read, what reaches it, what it can send.",
        "ja": "何を読めるか、何が届くか、何を送れるか。",
        "zh": "它能读什么、会收到什么、能发送什么。",
        "hi": "यह क्या पढ़ सकता है, इसे क्या मिलता है, यह क्या भेज सकता है।",
        "es": "Qué puede leer, qué le llega, qué puede enviar.",
    },
    "placeholder": {
        "en": "Describe your agent here…",
        "ja": "エージェントの説明をここに書く…",
        "zh": "在这里描述您的智能体…",
        "hi": "अपने एजेंट का वर्णन यहाँ लिखें…",
        "es": "Describe tu agente aquí…",
    },
    "check_btn": {"en": "Check this agent", "ja": "このエージェントをチェック", "zh": "检查这个智能体", "hi": "इस एजेंट की जाँच करें", "es": "Comprobar este agente"},
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
    "busy": {"en": "checking… (a few seconds)", "ja": "チェック中…（数秒）", "zh": "检查中…（几秒）", "hi": "जाँच हो रही है… (कुछ सेकंड)", "es": "Comprobando… (unos segundos)"},
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
        "en": "Tip: use the three questions instead — they need no AI translation.",
        "ja": "ヒント：下の3つの質問ならAIの読み取りなしで判定できます。",
        "zh": "提示：可以用下面的三个问题，不需要 AI 读取。",
        "hi": "सुझाव: नीचे के तीन सवाल आज़माएँ — इन्हें AI की ज़रूरत नहीं।",
        "es": "Consejo: usa las tres preguntas de abajo; no necesitan IA.",
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

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trifecta Checker — is your AI agent safe?</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
 body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;background:#0f172a;color:#e2e8f0}
 main{max-width:760px;margin:0 auto;padding:20px 16px 48px}
 h1{font-size:26px;margin:8px 0 4px}
 .lead{color:#cbd5e1;font-size:15px;line-height:1.55}
 .lead b{color:#fff}
 .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;margin:16px 0}
 textarea{width:100%;min-height:120px;background:#0b1220;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:10px;font-size:16px;box-sizing:border-box}
 button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:14px 18px;font-size:16px;cursor:pointer;min-height:48px}
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
 pre{white-space:pre-wrap;background:#0b1220;padding:12px;border-radius:8px;font-size:14px;line-height:1.6}
 .muted{color:#94a3b8;font-size:13px}
 details.card summary{cursor:pointer;font-size:17px;font-weight:600;padding:2px 0}
 .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px}
 .topbar{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
 @media (min-width:720px){
   main{max-width:920px}
   .qgrid{display:grid;grid-template-columns:1fr 1fr;gap:0 14px;align-items:start}
 }
</style></head><body><main>
<div class="topbar"><h1>Trifecta Checker</h1>
 <label style="padding:0;font-size:14px"><span data-i18n="lang_label"></span>
  <select id="lang" onchange="setLang(this.value)">
   <option value="en">English</option><option value="ja">日本語</option>
   <option value="zh">中文（简体）</option><option value="hi">हिन्दी</option><option value="es">Español</option>
  </select></label>
</div>
<p class="lead" data-i18n="lead"></p>

<div class="card">
 <div><b data-i18n="describe_title"></b></div>
 <p class="muted" style="margin:6px 0 8px" data-i18n="describe_hint"></p>
 <textarea id="desc"></textarea>
 <div class="row">
   <button onclick="runText()" style="flex:1" data-i18n="check_btn"></button>
   <span id="busy" class="muted"></span>
 </div>
</div>

<details class="card">
 <summary data-i18n="or_title"></summary>
 <p class="muted" data-i18n="form_hint"></p>
 <div id="groups"></div>
 <input type="text" id="pname">
 <div class="row"><button onclick="runForm()" style="flex:1" data-i18n="form_btn"></button></div>
</details>

<div id="out"></div>
<p class="muted" data-i18n="footer"></p>
</main><script>
const DATA = __DATA__;
let lang = "en";
function t(key){ return (DATA.strings[key] || {})[lang] || (DATA.strings[key] || {})["en"] || ""; }
function buildGroups(){
  let h = '<div class="qgrid">';
  for (const g of DATA.groups){
    h += "<fieldset><legend>"+g.title[lang]+"</legend>";
    for (const [token, labels] of g.items)
      h += '<label><input type="checkbox" data-f="'+g.field+'" value="'+token+'"> '+labels[lang]+"</label>";
    h += "</fieldset>";
  }
  document.getElementById("groups").innerHTML = h + "</div>";
}
function setLang(l){
  lang = l;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.innerHTML = t(el.dataset.i18n); });
  document.getElementById("desc").placeholder = t("placeholder");
  document.getElementById("pname").placeholder = t("name_ph");
  buildGroups();
}
function esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;")}
function render(d, explanation){
  const v = d.verdict;
  const el = [[t("el1"), v.elements.data_access], [t("el2"), v.elements.untrusted_input], [t("el3"), v.elements.outbound]];
  let h = '<div class="card"><span class="badge '+v.verdict+'">'+v.verdict+'</span> '+
          '<span class="muted">'+v.element_count+" "+t("of_powers")+
          (v.amplifiers.length ? " · "+t("plus")+" "+v.amplifiers.length : "")+'</span><div>';
  for (const [name,on] of el)
    h += '<span class="elem '+(on?"on":"off")+'">'+(on?"✓ ":"✗ ")+name+"</span>";
  h += '</div><pre id="exp">'+esc(explanation)+'</pre></div>';
  document.getElementById("out").innerHTML = h;
  document.getElementById("out").scrollIntoView({behavior:"smooth"});
}
async function post(url, body){
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  const d = await r.json();
  if (!d.ok) throw new Error(d.error || "failed");
  return d.result;
}
async function run(url, body){
  const busy = document.getElementById("busy"); busy.textContent = t("busy");
  try{
    const result = await post(url, body);
    render(result, t("exp_loading"));
    busy.textContent = "";
    try{
      const exp = await post("/api/explain", {verdict: result.verdict, profile: result.profile, lang});
      document.getElementById("exp").textContent = exp.explanation;
    }catch(e){
      document.getElementById("exp").textContent = t("exp_unavailable")+e.message+")";
    }
  }catch(e){
    document.getElementById("out").innerHTML = '<div class="card">'+esc(t("error_prefix")+String(e.message))+
      '<br><span class="muted">'+esc(t("error_tip"))+"</span></div>";
  }finally{ busy.textContent = ""; }
}
function runText(){ run("/api/check", {text: document.getElementById("desc").value}); }
function runForm(){
  const p = {name: document.getElementById("pname").value, data_access:[], untrusted_inputs:[], outbound:[], amplifiers:[]};
  document.querySelectorAll("input[type=checkbox]:checked").forEach(c => p[c.dataset.f].push(c.value));
  run("/api/check-profile", {profile: p});
}
setLang("en");
</script></body></html>"""


def page_html() -> bytes:
    data = {"strings": STRINGS,
            "groups": [{"field": g["field"], "title": g["title"],
                        "items": [[tok, labels] for tok, labels in g["items"]]}
                       for g in GROUPS]}
    return PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)).encode("utf-8")


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
