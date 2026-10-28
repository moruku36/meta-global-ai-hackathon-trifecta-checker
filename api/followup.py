"""Vercel function: POST /api/followup {message, profile, verdict, lang}
-> {reply, action} conversational reply after a verdict."""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from check import followup  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = followup(str(payload.get("message", "")),
                              payload.get("profile"), payload.get("verdict"),
                              lang=payload.get("lang", "en"))
            body = json.dumps({"ok": True, "result": result},
                              ensure_ascii=False).encode("utf-8")
        except Exception as exc:
            body = json.dumps({"ok": False, "error": str(exc)},
                              ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
