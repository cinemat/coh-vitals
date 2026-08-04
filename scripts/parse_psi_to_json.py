#!/usr/bin/env python3
"""Parse raw PSI JSON reports into data/history.json (structured, numeric, timestamped)."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "history.json"

URL_META = {
    "root": {"full": "https://childrenheroes.org/", "label": "Головна (UA)", "lang": "ua"},
    "en": {"full": "https://childrenheroes.org/en/", "label": "Home (EN)", "lang": "en"},
    "donate-ua": {"full": "https://childrenheroes.org/support-ukrainian-children-who-lost-parents/", "label": "Донат-лендінг (UA)", "lang": "ua"},
    "donate-en": {"full": "https://childrenheroes.org/en/support-ukrainian-children-who-lost-parents-2/", "label": "Donate landing (EN)", "lang": "en"},
}


def parse_lab(d):
    lr = d["lighthouseResult"]
    a = lr["audits"]
    items = a["network-requests"]["details"]["items"]
    weight_bytes = sum(i.get("transferSize", 0) for i in items)
    return {
        "score": round(lr["categories"]["performance"]["score"] * 100),
        "lcp_ms": a["largest-contentful-paint"]["numericValue"],
        "cls": a["cumulative-layout-shift"]["numericValue"],
        "fcp_ms": a["first-contentful-paint"]["numericValue"],
        "ttfb_ms": a.get("server-response-time", {}).get("numericValue"),
        "tbt_ms": a["total-blocking-time"]["numericValue"],
        "si_ms": a["speed-index"]["numericValue"],
        "tti_ms": a.get("interactive", {}).get("numericValue"),
        "weight_bytes": weight_bytes,
        "requests": len(items),
        "fetch_time": lr.get("fetchTime"),
    }


def parse_field(d, requested_url):
    le = d.get("loadingExperience")
    if not le or not le.get("metrics"):
        return None
    m = le["metrics"]
    page_id = le.get("id", "")
    scope = "page" if page_id.rstrip("/") == requested_url.rstrip("/") else "origin_fallback"

    def metric(key, is_cls=False):
        v = m.get(key)
        if not v:
            return None
        return {
            "value": (v["percentile"] / 100 if is_cls else v["percentile"]),
            "category": v.get("category"),
        }

    return {
        "scope": scope,
        "overall_category": le.get("overall_category"),
        "lcp_ms": metric("LARGEST_CONTENTFUL_PAINT_MS"),
        "inp_ms": metric("INTERACTION_TO_NEXT_PAINT"),
        "cls": metric("CUMULATIVE_LAYOUT_SHIFT_SCORE", is_cls=True),
        "fcp_ms": metric("FIRST_CONTENTFUL_PAINT_MS"),
        "ttfb_ms": metric("EXPERIMENTAL_TIME_TO_FIRST_BYTE"),
    }


def main():
    raw_dir = Path(sys.argv[1])
    comment = sys.argv[2] if len(sys.argv) > 2 else ""
    measured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    history = {"urls": URL_META, "snapshots": []}
    if DATA_FILE.exists():
        history = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        history["urls"] = URL_META

    for slug in URL_META:
        for strategy in ("mobile", "desktop"):
            f = raw_dir / f"{slug}-{strategy}.json"
            if not f.exists():
                print(f"SKIP missing {f}")
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            snapshot = {
                "timestamp": measured_at,
                "url_key": slug,
                "strategy": strategy,
                "comment": comment,
                "lab": parse_lab(d),
                "field": parse_field(d, URL_META[slug]["full"]),
            }
            history["snapshots"].append(snapshot)
            print(f"added {slug} {strategy}: score={snapshot['lab']['score']}")

    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved -> {DATA_FILE} ({len(history['snapshots'])} total snapshots)")


if __name__ == "__main__":
    main()
