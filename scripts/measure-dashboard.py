#!/usr/bin/env python3
"""
Знімає PageSpeed Insights (mobile+desktop) для всіх 4 сторінок з data/history.json,
дописує новий часовий зріз, перебудовує dist/dashboard.html + docs/index.html,
і комітить + пушить результат на GitHub (звідки підхоплює GitHub Pages).

Використання:
    python3 scripts/measure-dashboard.py "Коментар: що щойно змінили на сайті"
    python3 scripts/measure-dashboard.py "коментар" --no-push   # тільки локально, без git

Після push дублювати вручну на claude.ai/code — Artifact-версію (dist/dashboard.html)
можна republish-нути окремо, якщо потрібно тримати і її в актуальному стані.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
import parse_psi_to_json as parser  # noqa: E402
import build_dashboard  # noqa: E402

ENV_FILE = PROJECT_ROOT / ".env"


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
            retriable = e.code == 429 or e.code >= 500
            if retriable and attempt < retries:
                wait = 10 * attempt
                print(f"  HTTP {e.code}, чекаю {wait}с, повтор {attempt}/{retries}...", flush=True)
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


def run_git(*args):
    return subprocess.run(
        ["git", *args], cwd=str(PROJECT_ROOT), capture_output=True, text=True,
    )


def commit_and_push(comment):
    files = ["data/history.json", "dist/dashboard.html", "docs/index.html"]

    r = run_git("add", *files)
    if r.returncode != 0:
        print(f"  git add провалився: {r.stderr.strip()}", flush=True)
        return False

    r = run_git("diff", "--cached", "--quiet")
    if r.returncode == 0:
        print("  Немає змін для коміту (дані ідентичні попереднім).", flush=True)
        return True

    r = run_git("commit", "-m", f"chore: оновлення Vitals — {comment}")
    if r.returncode != 0:
        print(f"  git commit провалився: {r.stderr.strip()}", flush=True)
        return False
    print(f"  {r.stdout.strip()}", flush=True)

    r = run_git("pull", "--rebase", "--autostash", "origin", "main")
    if r.returncode != 0:
        print(f"  git pull --rebase провалився: {r.stderr.strip()}", flush=True)
        return False

    r = run_git("push")
    if r.returncode != 0:
        print(f"  git push провалився: {r.stderr.strip()}", flush=True)
        return False

    print("  Запушено на GitHub — Pages задеплоїться за 1-2 хв.", flush=True)
    return True


def main():
    if len(sys.argv) < 2:
        sys.exit('Використання: python3 measure-dashboard.py "коментар" [--no-push]')
    comment = sys.argv[1]
    push = "--no-push" not in sys.argv[2:]
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

    if push:
        print("\nКомічу і пушу на GitHub...", flush=True)
        ok = commit_and_push(comment)
        if not ok:
            print("\nЛокальні дані оновлено, але git push НЕ вдався (дивись помилку вище). "
                  "Виправте вручну: git status.", flush=True)
        else:
            print("\nГотово — локально оновлено і запушено на GitHub.", flush=True)
    else:
        print("\nГотово (--no-push): локальні файли оновлено, git не чіпав.", flush=True)


if __name__ == "__main__":
    main()
