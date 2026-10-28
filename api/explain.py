"""Vercel function: POST /api/explain  {verdict, profile, lang} -> explanation."""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

for _cand in (os.path.join(os.path.dirname(__file__), ".."), os.getcwd(), "/var/task"):
    _root = os.path.normpath(_cand)
    if os.path.isdir(_root) and _root not in sys.path:
        sys.path.insert(0, _root)

from check import explain_result  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = explain_result(payload.get("verdict", {}), payload.get("profile"),
                                    lang=payload.get("lang", "en"))
            obj, code = {"ok": True, "result": result}, 200
        except Exception as exc:
            obj, code = {"ok": False, "error": str(exc)}, 200
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
