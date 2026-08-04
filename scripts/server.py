#!/usr/bin/env python3
"""
Локальний сервер для app.html.

Роздає файли проєкту (app.html, assets/, data/history.json). Потрібен тому,
що app.html підвантажує data/history.json через fetch() — браузер блокує
такі запити при відкритті файлу подвійним кліком (file://).

Використання:
    python3 scripts/server.py
    -> відкрити http://127.0.0.1:8420/app.html у браузері

Дані оновлюються автоматично через GitHub Actions (.github/workflows/update-vitals.yml)
або вручну: python3 scripts/measure-dashboard.py "коментар".
"""
import http.server
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8420

socketserver.TCPServer.allow_reuse_address = True


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print("[server]", fmt % args)


def main():
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Локальний сервер запущено: http://127.0.0.1:{PORT}/app.html")
        print("Працює повністю офлайн. Ctrl+C — зупинити.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nЗупинено.")


if __name__ == "__main__":
    main()
