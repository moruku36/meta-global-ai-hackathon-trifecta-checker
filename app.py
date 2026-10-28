#!/usr/bin/env python3
"""Trifecta Checker — minimal web UI (stdlib only, no dependencies).

Run:  python3 app.py [port]        (default: $PORT or 8765)
Open: http://127.0.0.1:8765/ locally, or the Hugging Face Space URL.

Two input modes:
- Describe: free-text description -> Muse Spark extracts the profile ->
  the deterministic engine judges -> Spark explains in plain language.
- Form: tick the capability checkboxes yourself (the fallback when
  extraction fails, and the precise route for demos).
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trifecta_checker as engine  # noqa: E402
from check import explain_result, extract_and_judge, judge_profile  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trifecta Checker — is your AI agent safe?</title>
<style>
 /* Mobile-first: designed for iPhone, widened for PC. */
 *{box-sizing:border-box}
 body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;background:#0f172a;color:#e2e8f0;font-size:16px;line-height:1.55}
 main{max-width:860px;margin:0 auto;padding:16px 12px 56px}
 h1{font-size:24px;margin:6px 0 4px} .sub{color:#94a3b8;margin:0 0 16px;font-size:15px}
 .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:14px;margin:12px 0}
 textarea{width:100%;min-height:150px;background:#0f172a;color:#e2e8f0;border:1px solid #475569;border-radius:8px;padding:12px;font-size:16px}
 button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:12px 18px;font-size:16px;cursor:pointer;min-height:48px;touch-action:manipulation}
 button.sub2{background:#334155;flex:1 1 40%;padding:10px 8px;font-size:14px;min-height:44px}
 button:disabled{opacity:.5}
 select{background:#0f172a;color:#e2e8f0;border:1px solid #475569;border-radius:6px;padding:10px;font-size:16px}
 input[type=text],#pname{background:#0f172a;color:#e2e8f0;border:1px solid #475569;border-radius:6px;padding:11px;font-size:16px;width:100%}
 .badge{display:inline-block;padding:4px 14px;border-radius:999px;font-weight:700;font-size:18px}
 .Lethal{background:#7f1d1d;color:#fecaca} .Risky{background:#713f12;color:#fde68a} .Low{background:#14532d;color:#bbf7d0}
 .elems{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
 .elem{border:1px solid #475569;border-radius:8px;padding:6px 10px;font-size:13px}
 .elem.on{border-color:#dc2626;background:#450a0a} .elem.off{opacity:.55}
 pre{white-space:pre-wrap;word-break:break-word;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px;font-size:14px;line-height:1.6}
 fieldset{border:1px solid #334155;border-radius:8px;margin:10px 0;padding:8px 12px}
 legend{color:#93c5fd;padding:0 4px}
 fieldset label{display:flex;align-items:center;gap:10px;padding:9px 2px;font-size:15px;border-bottom:1px solid #263449}
 fieldset label:last-child{border-bottom:0}
 input[type=checkbox]{width:22px;height:22px;flex:none;accent-color:#2563eb}
 .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
 .row>*{min-width:0}
 #go{width:100%}
 .muted{color:#94a3b8;font-size:13px}
 @media (min-width:720px){
  main{padding:24px 16px 64px} h1{font-size:26px}
  .card{padding:16px} button.sub2{flex:0 1 auto;padding:10px 14px}
  fieldset label{display:inline-flex;border-bottom:0;padding:6px 8px 6px 0}
  #go{width:auto} #pname{width:auto;flex:1}
 }
</style></head><body><main>
<h1>Trifecta Checker</h1>
<p class="sub">Three powers make an AI agent dangerous in combination: reading <b>private data</b>,
reading <b>untrusted content</b>, and <b>sending data out</b>. Describe your agent — a deterministic
rule engine (not an LLM) gives the verdict; Muse Spark only translates and explains.</p>

<div class="card">
 <div class="row"><b>Describe your agent</b>
  <span class="muted">samples:</span>
  <button class="sub2" onclick="loadSample('case_a')">A: memo tool</button>
  <button class="sub2" onclick="loadSample('case_b')">B: researcher</button>
  <button class="sub2" onclick="loadSample('case_c')">C: mail agent</button>
  <button class="sub2" onclick="loadSample('case_d')">D: assistant</button>
 </div>
 <textarea id="desc" placeholder="e.g. My agent reads my Gmail, follows links in messages, and sends replies by itself..."></textarea>
 <div class="row" style="margin-top:10px">
  <label>Explanation language <select id="lang"><option value="en">English</option><option value="ja">日本語</option></select></label>
  <button id="go" onclick="runText()">Check this agent</button>
  <span id="busy" class="muted"></span>
 </div>
</div>

<div class="card">
 <b>…or tick the capabilities yourself</b>
 <div id="form"></div>
 <div class="row" style="margin-top:8px">
  <input id="pname" placeholder="agent name" style="background:#0f172a;color:#e2e8f0;border:1px solid #475569;border-radius:6px;padding:7px">
  <button onclick="runForm()">Check with these capabilities</button>
 </div>
</div>

<div id="out"></div>

<script>
const VOCAB = __VOCAB__;
function buildForm(){
  const names = {data_access:"① Reads private data", untrusted_inputs:"② Reads untrusted content",
                 outbound:"③ Can send data out", amplifiers:"Amplifiers"};
  let h = "";
  for (const k of Object.keys(VOCAB)){
    h += "<fieldset><legend>"+names[k]+"</legend>";
    for (const t of VOCAB[k]) h += '<label><input type="checkbox" data-f="'+k+'" value="'+t+'"> '+t+"</label>";
    h += "</fieldset>";
  }
  document.getElementById("form").innerHTML = h;
}
async function loadSample(name){
  const r = await fetch("/fixtures/"+name+".txt"); document.getElementById("desc").value = await r.text();
}
function esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;")}
function render(d, explanation){
  const v = d.verdict;
  const el = [["Private data", v.elements.data_access, v.evidence.data_access],
              ["Untrusted content", v.elements.untrusted_input, v.evidence.untrusted_inputs],
              ["Sends data out", v.elements.outbound, v.evidence.outbound]];
  let h = '<div class="card"><span class="badge '+v.verdict+'">'+v.verdict+'</span> '+
          '<span class="muted">'+v.element_count+' of 3 elements'+
          (v.amplifiers.length ? " · amplifiers: "+v.amplifiers.join(", ") : "")+'</span><div class="elems">';
  for (const [name,on,items] of el)
    h += '<span class="elem '+(on?"on":"off")+'">'+(on?"✓ ":"✗ ")+name+(items.length?": "+items.join(", "):"")+"</span>";
  h += '</div><pre id="exp">'+esc(explanation)+'</pre>'+
       '<p class="muted">Profile: '+esc(JSON.stringify(d.profile))+"</p></div>";
  document.getElementById("out").innerHTML = h;
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
      '<br><span class="muted">Tip: use the capability checkboxes below — they need no AI translation.</span></div>';
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
buildForm();
</script></main></body></html>"""


def page_html() -> bytes:
    vocab = {
        "data_access": sorted(engine.DATA_ACCESS),
        "untrusted_inputs": sorted(engine.UNTRUSTED_INPUTS),
        "outbound": sorted(engine.OUTBOUND),
        "amplifiers": sorted(engine.AMPLIFIERS),
    }
    return PAGE.replace("__VOCAB__", json.dumps(vocab)).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep stdout clean
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
        if self.path == "/":
            self._send(200, page_html(), "text/html; charset=utf-8")
        elif self.path.startswith("/fixtures/"):
            name = Path(self.path).name
            target = FIXTURES / name
            if target.is_file() and target.suffix == ".txt":
                self._send(200, target.read_bytes(), "text/plain; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

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
            self._json(200, {"ok": True, "result": result})
        except Exception as exc:
            self._json(200, {"ok": False, "error": str(exc)})


def main() -> int:
    import os

    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8765"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Trifecta Checker UI on port {port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
