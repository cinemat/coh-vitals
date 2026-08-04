#!/usr/bin/env python3
"""Build dist/dashboard.html: embeds fonts (base64) + data/history.json into
the static template, producing a self-contained page ready for Artifact publish."""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
DATA_FILE = ROOT / "data" / "history.json"
OUT_FILE = ROOT / "dist" / "dashboard.html"
TEMPLATE = Path(__file__).resolve().parent / "dashboard_template.html"

LATIN_RANGE = "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+2074, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"
CYRILLIC_RANGE = "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116"


def b64(path):
    return base64.b64encode(path.read_bytes()).decode("ascii")


def font_face(family, weight_range, filename, unicode_range):
    return f"""@font-face {{
  font-family: '{family}';
  font-style: normal;
  font-weight: {weight_range};
  font-display: swap;
  src: url(data:font/woff2;base64,{b64(FONTS / filename)}) format('woff2');
  unicode-range: {unicode_range};
}}"""


def build():
    font_faces = "\n".join([
        font_face("Unbounded", "300 900", "unbounded-var-latin.woff2", LATIN_RANGE),
        font_face("Unbounded", "300 900", "unbounded-var-cyrillic.woff2", CYRILLIC_RANGE),
        font_face("Plex Sans", "400", "plexsans-400-latin.woff2", LATIN_RANGE),
        font_face("Plex Sans", "400", "plexsans-400-cyrillic.woff2", CYRILLIC_RANGE),
        font_face("Plex Sans", "500", "plexsans-500-latin.woff2", LATIN_RANGE),
        font_face("Plex Sans", "500", "plexsans-500-cyrillic.woff2", CYRILLIC_RANGE),
        font_face("Plex Sans", "600", "plexsans-600-latin.woff2", LATIN_RANGE),
        font_face("Plex Sans", "600", "plexsans-600-cyrillic.woff2", CYRILLIC_RANGE),
        font_face("Plex Mono", "400", "plexmono-400-latin.woff2", LATIN_RANGE),
        font_face("Plex Mono", "400", "plexmono-400-cyrillic.woff2", CYRILLIC_RANGE),
        font_face("Plex Mono", "500", "plexmono-500-latin.woff2", LATIN_RANGE),
        font_face("Plex Mono", "500", "plexmono-500-cyrillic.woff2", CYRILLIC_RANGE),
        font_face("Plex Mono", "600", "plexmono-600-latin.woff2", LATIN_RANGE),
        font_face("Plex Mono", "600", "plexmono-600-cyrillic.woff2", CYRILLIC_RANGE),
    ])

    data_json = json.dumps(json.loads(DATA_FILE.read_text(encoding="utf-8")), ensure_ascii=False)

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__FONT_FACES__*/", font_faces)
    html = html.replace("/*__DATA_JSON__*/", data_json)

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"Built {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
