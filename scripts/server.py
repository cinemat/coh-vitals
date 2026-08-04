#!/usr/bin/env python3
"""
Локальний сервер для app.html.

Роздає файли проєкту (app.html, assets/, data/history.json) і приймає
POST /refresh, який запускає measure-dashboard.py (знову знімає PageSpeed
для всіх 4 сторінок, дописує data/history.json і перебудовує dist/dashboard.html).

Використання:
    python3 scripts/server.py
    -> відкрити http://127.0.0.1:8420/app.html у браузері

Робота самої сторінки (перегляд історії) повністю офлайн — інтернет потрібен
лише в момент натискання кнопки "Оновити дані" (запит до PageSpeed Insights API).
"""
import http.server
import json
import os
import socketserver
import subprocess
import sys
from pathlib import Path

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
        except subprocess.TimeoutExpired as e:
            print("[refresh] перевищено 10 хв — перериваю")
            body = json.dumps({
                "ok": False,
                "log": "Перевищено ліміт часу (10 хв). Перевірте інтернет-з'єднання і спробуйте ще раз.\n"
                       + (e.stdout or "").decode("utf-8", "ignore")[-2000:] if isinstance(e.stdout, bytes) else str(e.stdout or "")[-2000:],
            }, ensure_ascii=False).encode("utf-8")
            self.send_response(504)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        ok = result.returncode == 0
        print(f"[refresh] завершено, ok={ok}")
        if not ok:
            print(result.stdout)
            print(result.stderr)

        body = json.dumps({
            "ok": ok,
            "log": (result.stdout[-3000:] + "\n" + result.stderr[-1500:]).strip(),
        }, ensure_ascii=False).encode("utf-8")

        self.send_response(200 if ok else 500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[server]", fmt % args)


def main():
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Локальний сервер запущено: http://127.0.0.1:{PORT}/app.html")
        print("Працює повністю офлайн (крім кнопки «Оновити дані»). Ctrl+C — зупинити.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nЗупинено.")


if __name__ == "__main__":
    main()
