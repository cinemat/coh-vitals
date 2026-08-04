#!/usr/bin/env python3
"""
Локальний сервер для app.html.

Роздає файли проєкту (app.html, assets/, data/history.json) і приймає
POST /refresh, який запускає measure-dashboard.py: знову знімає PageSpeed
для всіх 4 сторінок, дописує data/history.json, перебудовує dist/dashboard.html
+ docs/index.html, і сам комітить + пушить на GitHub — звідки підхопить
GitHub Pages.

Використання:
    python3 scripts/server.py
    -> відкрити http://127.0.0.1:8420/app.html у браузері

Ця кнопка існує лише в локальній версії (app.html). На GitHub Pages і в
Claude Artifact кнопки немає — там read-only перегляд, оновлюється через
GitHub Actions за розкладом або через цю саму кнопку (яка пушить дані).
"""
import http.server
import json
import os
import socketserver
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
PORT = 8420

socketserver.TCPServer.allow_reuse_address = True


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if self.path != "/refresh":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            payload = {}
        comment = (payload.get("comment") or "Оновлено через кнопку Refresh").strip()

        print(f"[refresh] запускаю measure-dashboard.py: {comment!r}")
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        try:
            result = subprocess.run(
                [sys.executable, "-u", str(ROOT / "scripts" / "measure-dashboard.py"), comment],
                capture_output=True, text=True, cwd=str(ROOT), timeout=600, env=env,
            )
        except subprocess.TimeoutExpired:
            self._respond(504, False, "Перевищено ліміт часу (10 хв). Спробуйте ще раз.")
            return

        ok = result.returncode == 0
        print(f"[refresh] завершено, ok={ok}")
        log = (result.stdout[-3000:] + "\n" + result.stderr[-1500:]).strip()
        if not ok:
            print(log)
        self._respond(200 if ok else 500, ok, log)

    def _respond(self, code, ok, log):
        body = json.dumps({"ok": ok, "log": log}, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[server]", fmt % args)


def main():
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Локальний сервер запущено: http://127.0.0.1:{PORT}/app.html")
        print("Перегляд повністю офлайн, кнопка «Оновити дані» потребує інтернету. Ctrl+C — зупинити.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nЗупинено.")


if __name__ == "__main__":
    main()
