#!/usr/bin/env python3
"""
Знімає PageSpeed Insights (mobile+desktop) для всіх 4 сторінок з data/history.json,
дописує новий часовий зріз і перебудовує dist/dashboard.html.

Використання:
    python3 scripts/measure-dashboard.py "Коментар: що щойно змінили на сайті"

Після завершення лишається тільки republish dist/dashboard.html через Artifact tool
(той самий file_path — лінк на сторінку не зміниться).
"""
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import parse_psi_to_json as parser  # noqa: E402
import build_dashboard  # noqa: E402

ENV_FILE = ROOT.parent / ".env"


def load_api_key():
    env_key = os.environ.get("PAGESPEED_API_KEY")
    if env_key:
        return env_key
    if not ENV_FILE.exists():
        sys.exit(f"Не знайдено {ENV_FILE} і немає env-змінної PAGESPEED_API_KEY")
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("PAGESPEED_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    sys.exit("PAGESPEED_API_KEY порожній у .env")


def fetch_psi(api_key, url, strategy, retries=4):
    params = urllib.parse.urlencode({
        "url": url, "strategy": strategy, "category": "performance", "key": api_key,
    })
    req_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?{params}"
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req_url, timeout=90) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = 10 * attempt
                print(f"  429, чекаю {wait}с, повтор {attempt}/{retries}...", flush=True)
                time.sleep(wait)
                continue
            sys.exit(f"HTTP {e.code} для {url} [{strategy}]: {e.read()[:300]}")
        except (TimeoutError, urllib.error.URLError) as e:
            if attempt < retries:
                wait = 8 * attempt
                print(f"  {e.__class__.__name__} ({e}), чекаю {wait}с, повтор {attempt}/{retries}...", flush=True)
                time.sleep(wait)
                continue
            sys.exit(f"{e.__class__.__name__} для {url} [{strategy}]: {e}")
    sys.exit(f"Не вдалось отримати {url} [{strategy}]")


def main():
    if len(sys.argv) < 2:
        sys.exit('Використання: python3 measure-dashboard.py "коментар"')
    comment = sys.argv[1]
    api_key = load_api_key()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for slug, meta in parser.URL_META.items():
            for strategy in ("mobile", "desktop"):
                print(f"Знімаю {slug} [{strategy}]...", flush=True)
                data = fetch_psi(api_key, meta["full"], strategy)
                (tmp_dir / f"{slug}-{strategy}.json").write_text(json.dumps(data), encoding="utf-8")
                time.sleep(2)

        sys.argv = ["parse_psi_to_json.py", str(tmp_dir), comment]
        parser.main()

    build_dashboard.build()

    print("\nГотово. Тепер опублікуйте dist/dashboard.html через Artifact tool (той самий file_path).")


if __name__ == "__main__":
    main()
