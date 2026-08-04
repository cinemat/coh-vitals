#!/usr/bin/env python3
"""
Знімає PageSpeed Insights (mobile + desktop) для childrenheroes.org та /en/
і дописує рядки в log/performance-monitoring.md.

Використання:
    python3 scripts/measure-performance.py "Коментар: що щойно змінили"
    python3 scripts/measure-performance.py "Після Етапу 1" --field

--field  також знімає та дописує рядок у таблицю FIELD DATA (CrUX).
         Робіть це не частіше ніж раз на 1-2 тижні — дані CrUX
         оновлюються повільно (28-денне ковзне вікно).
"""
import json
import sys
import time
import urllib.request
import urllib.parse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
LOG_FILE = ROOT / "log" / "performance-monitoring.md"

URLS = {
    "/": "https://childrenheroes.org/",
    "/en/": "https://childrenheroes.org/en/",
}
STRATEGIES = ["mobile", "desktop"]

CATEGORY_EMOJI = {"FAST": "🟢 FAST", "AVERAGE": "🟡 AVERAGE", "SLOW": "🔴 SLOW"}


def load_api_key():
    if not ENV_FILE.exists():
        sys.exit(f"Не знайдено {ENV_FILE}. Створіть .env з рядком PAGESPEED_API_KEY=...")
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("PAGESPEED_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    sys.exit("PAGESPEED_API_KEY порожній у .env")


def fetch_psi(api_key, url, strategy, retries=4):
    params = urllib.parse.urlencode({
        "url": url,
        "strategy": strategy,
        "category": "performance",
        "key": api_key,
    })
    req_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?{params}"
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req_url, timeout=90) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            if e.code == 429 and attempt < retries:
                wait = 10 * attempt
                print(f"  429 rate limit, чекаю {wait}с і повторюю ({attempt}/{retries})...", flush=True)
                time.sleep(wait)
                continue
            sys.exit(f"HTTP {e.code} для {url} [{strategy}]: {body[:300]}")
        except (TimeoutError, urllib.error.URLError) as e:
            if attempt < retries:
                wait = 8 * attempt
                print(f"  {e.__class__.__name__} ({e}), чекаю {wait}с, повтор {attempt}/{retries}...", flush=True)
                time.sleep(wait)
                continue
            sys.exit(f"{e.__class__.__name__} для {url} [{strategy}]: {e}")
    sys.exit(f"Не вдалось отримати дані для {url} [{strategy}] після {retries} спроб")


def fmt_ms(ms):
    if ms is None:
        return "—"
    s = f"{ms/1000:.1f} с" if ms >= 1000 else f"{ms:.0f} мс"
    return s.replace(".", ",")


def fmt_num(value, decimals):
    return f"{value:.{decimals}f}".replace(".", ",")


def lab_row(date_str, url_label, data, comment):
    lr = data["lighthouseResult"]
    a = lr["audits"]
    score = round(lr["categories"]["performance"]["score"] * 100)
    items = a["network-requests"]["details"]["items"]
    weight_mb = sum(i.get("transferSize", 0) for i in items) / 1048576
    ttfb = a.get("server-response-time", {}).get("numericValue")
    cols = [
        date_str,
        f"`{url_label}`",
        f"{score} (1 прогін)",
        fmt_ms(a["largest-contentful-paint"]["numericValue"]),
        fmt_num(a["cumulative-layout-shift"]["numericValue"], 3),
        fmt_ms(a["first-contentful-paint"]["numericValue"]),
        fmt_ms(ttfb),
        fmt_ms(a["total-blocking-time"]["numericValue"]),
        fmt_ms(a["speed-index"]["numericValue"]),
        f"{fmt_num(weight_mb, 1)} МБ",
        str(len(items)),
        comment,
    ]
    return "| " + " | ".join(cols) + " |"


def field_metric(metrics, key, is_cls=False):
    v = metrics.get(key)
    if not v:
        return "н/д (мало даних)"
    p = v["percentile"]
    cat = CATEGORY_EMOJI.get(v.get("category", ""), v.get("category", "н/д"))
    val = fmt_num(p / 100, 2) if is_cls else fmt_ms(p)
    return f"{val} {cat}"


def field_row(date_str, url_label, strategy, data, comment):
    le = data.get("loadingExperience", {})
    metrics = le.get("metrics", {})
    overall = CATEGORY_EMOJI.get(le.get("overall_category", ""), "н/д")
    cols = [
        date_str,
        f"`{url_label}`",
        strategy,
        field_metric(metrics, "LARGEST_CONTENTFUL_PAINT_MS"),
        field_metric(metrics, "INTERACTION_TO_NEXT_PAINT"),
        field_metric(metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE", is_cls=True),
        field_metric(metrics, "FIRST_CONTENTFUL_PAINT_MS"),
        field_metric(metrics, "EXPERIMENTAL_TIME_TO_FIRST_BYTE"),
        overall,
        comment,
    ]
    return "| " + " | ".join(cols) + " |"


def insert_before_anchor(text, anchor, new_lines):
    marker = f"<!-- {anchor} -->"
    idx = text.find(marker)
    if idx == -1:
        sys.exit(f"Не знайдено якір {marker} у {LOG_FILE}. Файл міг бути змінений вручну.")
    insertion = "\n".join(new_lines) + "\n"
    return text[:idx] + insertion + text[idx:]


def main():
    if len(sys.argv) < 2:
        sys.exit('Використання: python3 measure-performance.py "коментар" [--field]')
    comment = sys.argv[1]
    include_field = "--field" in sys.argv[2:]

    api_key = load_api_key()
    today = date.today().isoformat()

    results = {}
    for url_label, url in URLS.items():
        for strategy in STRATEGIES:
            print(f"Знімаю {url_label} [{strategy}]...")
            results[(url_label, strategy)] = fetch_psi(api_key, url, strategy)
            time.sleep(2)

    mobile_rows = [
        lab_row(today, label, results[(label, "mobile")], comment)
        for label in URLS
    ]
    desktop_rows = [
        lab_row(today, label, results[(label, "desktop")], comment)
        for label in URLS
    ]

    text = LOG_FILE.read_text(encoding="utf-8")
    text = insert_before_anchor(text, "MOBILE_ROWS_END", mobile_rows)
    text = insert_before_anchor(text, "DESKTOP_ROWS_END", desktop_rows)

    if include_field:
        field_rows = []
        for label in URLS:
            for strategy in STRATEGIES:
                field_rows.append(
                    field_row(today, label, strategy, results[(label, strategy)], comment)
                )
        text = insert_before_anchor(text, "FIELD_ROWS_END", field_rows)

    LOG_FILE.write_text(text, encoding="utf-8")
    print(f"\nДодано {len(mobile_rows)} mobile + {len(desktop_rows)} desktop рядків"
          + (f" + {len(field_rows)} field рядків" if include_field else "")
          + f" у {LOG_FILE}")


if __name__ == "__main__":
    main()
