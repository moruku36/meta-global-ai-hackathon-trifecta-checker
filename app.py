#!/usr/bin/env python3
"""Trifecta Checker — minimal web UI (standard library only).

Two ways in:
  1. Describe your agent in plain words -> Muse Spark sorts it into
     capabilities -> the rule engine (not an LLM) gives the verdict ->
     Muse Spark explains the verdict in plain language.
  2. Answer three questions by ticking plain-language capabilities.
     No LLM is involved until the explanation step.

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

# Plain-language labels for the engine's capability tokens.
# The tokens are what the rule engine understands; people see the labels.
GROUPS = [
    ("data_access", "Question 1 — What private data can it read?", [
        ("gmail_read", "Gmail"),
        ("email_read", "Other email"),
        ("calendar_read", "Calendar"),
        ("contacts_read", "Contacts"),
        ("drive_read", "Cloud drive (Google Drive etc.)"),
        ("local_files", "Files on the computer"),
        ("message_read", "Chat / message history"),
    ]),
    ("untrusted_inputs", "Question 2 — What can reach it from other people?", [
        ("email_body", "Emails it receives"),
        ("web_browse", "Web pages it opens"),
        ("uploaded_files", "Files people upload"),
        ("chat_input", "Chat messages from users"),
        ("webhook", "Webhooks / triggers from other systems"),
    ]),
    ("outbound", "Question 3 — What can it send out or do outside?", [
        ("email_send", "Send email"),
        ("chat_post", "Post messages in chat channels"),
        ("message_send", "Send direct messages"),
        ("http_post", "Send data to a web address"),
        ("code_execute_outbound", "Run code that sends data out"),
    ]),
    ("amplifiers", "One more thing — any of these?", [
        ("no_human_approval", "It acts without asking a person first"),
        ("auto_execute_code", "It runs code by itself"),
        ("long_term_memory_write", "It remembers things long-term"),
    ]),
]

SAMPLES = [
    ("case_a.txt", "Sample A · Note taker"),
    ("case_b.txt", "Sample B · Web researcher"),
    ("case_c.txt", "Sample C · Auto mail agent"),
    ("case_d.txt", "Sample D · Personal assistant"),
    ("case_c_fixed_reader.txt", "Sample C, fixed · reading only"),
    ("case_c_fixed_sender.txt", "Sample C, fixed · sending only"),
]

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trifecta Checker — is your AI agent safe?</title>
<style>
 body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;background:#0f172a;color:#e2e8f0}
 main{max-width:760px;margin:0 auto;padding:20px 16px 48px}
 h1{font-size:26px;margin:8px 0 4px}
 .lead{color:#cbd5e1;font-size:15px;line-height:1.55}
 .lead b{color:#fff}
 .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;margin:16px 0}
 textarea{width:100%;min-height:120px;background:#0b1220;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:10px;font-size:16px;box-sizing:border-box}
 button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:14px 18px;font-size:16px;cursor:pointer;min-height:48px}
 button.ghost{background:#334155;padding:9px 12px;font-size:14px;min-height:40px;margin:0 6px 6px 0}
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
 .chips{margin:10px 0 2px}
</style></head><body><main>
<h1>Trifecta Checker</h1>
<p class="lead">An AI agent gets dangerous when three powers combine: it can read
<b>private data</b>, it takes in <b>content from other people</b>, and it can
<b>send data out</b>. Describe your agent below — a rule engine (not an AI) gives
the verdict, and Muse Spark only helps read your description and explain the result.</p>

<div class="card">
 <div><b>Describe your agent</b> <span class="muted">— in your own words: what does it do?</span></div>
 <div class="chips">__SAMPLES__</div>
 <textarea id="desc" placeholder="e.g. My agent reads my Gmail, follows links in messages, and sends replies by itself..."></textarea>
 <div class="row">
   <label style="padding:0">Explanation language
     <select id="lang"><option value="en">English</option><option value="ja">日本語</option></select></label>
   <button onclick="runText()" style="flex:1">Check this agent</button>
   <span id="busy" class="muted"></span>
 </div>
</div>

<details class="card">
 <summary>or answer three questions instead</summary>
 <p class="muted">Tick everything your agent can do. Leave a question blank if the answer is "none of these". No AI is used for this part — the verdict comes straight from the rule engine.</p>
 __GROUPS__
 <input type="text" id="pname" placeholder="Agent name (optional)">
 <div class="row"><button onclick="runForm()" style="flex:1">Check with these answers</button></div>
</details>

<div id="out"></div>
<p class="muted">The rating is a simple safety heuristic, not a certification. It focuses on data theft:
an agent that can read private data, swallow other people's content, and send data out can be tricked
into leaking what it read.</p>
</main><script>
function esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;")}
function render(d, explanation){
  const v = d.verdict;
  const el = [["Reads private data", v.elements.data_access, v.evidence.data_access],
              ["Takes in others' content", v.elements.untrusted_input, v.evidence.untrusted_inputs],
              ["Can send data out", v.elements.outbound, v.evidence.outbound]];
  let h = '<div class="card"><span class="badge '+v.verdict+'">'+v.verdict+'</span> '+
          '<span class="muted">'+v.element_count+' of the 3 powers'+
          (v.amplifiers.length ? " · plus: "+v.amplifiers.join(", ") : "")+'</span><div>';
  for (const [name,on,items] of el)
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
  const busy = document.getElementById("busy"); busy.textContent = "checking… (a few seconds)";
  const lang = document.getElementById("lang").value;
  try{
    const result = await post(url, body);
    render(result, "Writing the plain-language explanation…");
    busy.textContent = "";
    try{
      const exp = await post("/api/explain", {verdict: result.verdict, profile: result.profile, lang});
      document.getElementById("exp").textContent = exp.explanation;
    }catch(e){
      document.getElementById("exp").textContent = "(Explanation unavailable: "+e.message+")";
    }
  }catch(e){
    document.getElementById("out").innerHTML = '<div class="card">Could not complete the check: '+esc(String(e.message))+
      '<br><span class="muted">Tip: use the three questions below instead — they need no AI translation.</span></div>';
  }finally{ busy.textContent = ""; }
}
function runText(){
  run("/api/check", {text: document.getElementById("desc").value});
}
function runForm(){
  const p = {name: document.getElementById("pname").value, data_access:[], untrusted_inputs:[], outbound:[], amplifiers:[]};
  document.querySelectorAll("input[type=checkbox]:checked").forEach(c => p[c.dataset.f].push(c.value));
  run("/api/check-profile", {profile: p});
}
async function loadSample(fn){
  const r = await fetch("/fixtures/"+fn);
  document.getElementById("desc").value = await r.text();
}
</script></body></html>"""


def _groups_html() -> str:
    parts = []
    for field, title, items in GROUPS:
        boxes = "".join(
            f'<label><input type="checkbox" data-f="{field}" value="{token}"> {label}</label>'
            for token, label in items)
        parts.append(f"<fieldset><legend>{title}</legend>{boxes}</fieldset>")
    return "".join(parts)


def _samples_html() -> str:
    return "".join(f'<button class="ghost" onclick="loadSample(\'{fn}\')">{label}</button>'
                   for fn, label in SAMPLES)


def page_html() -> bytes:
    return (PAGE.replace("__GROUPS__", _groups_html())
                .replace("__SAMPLES__", _samples_html()).encode("utf-8"))


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
