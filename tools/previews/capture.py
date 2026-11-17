"""Capture hover-preview screenshots for every outbound link in index.html.

Most sites refuse to be shown in an iframe (X-Frame-Options / CSP), so the
page shows static screenshots instead. Run this whenever a linked site changes:

    python tools/previews/capture.py

Needs Playwright for Python (`pip install playwright`) and Pillow. It drives the
installed Chrome (falling back to Playwright's Chromium) with a fresh, signed-out
English profile, saves 640x400 WebP files to assets/previews/, and writes
assets/previews/manifest.json mapping each URL to its image.
"""

import hashlib
import io
import json
import re
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "previews"
# fonts: not pages. codepen.io: headless browsers get a Cloudflare bot check instead.
SKIP_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com", "codepen.io")


def show_dorm_list(page):
    """iguide.chat/dorms opens on the map; switch to the list view for the shot."""
    page.locator('button[title="List View"], button[title="列表视图"]').first.click()
    page.wait_for_timeout(1500)


# Per-URL steps to run before the screenshot, keyed by URL prefix.
ACTIONS = {"https://iguide.chat/dorms": show_dorm_list}

LINKEDIN_LOGO = (
    '<svg viewBox="0 0 24 24" width="88" height="88"><path fill="#fff" d="M20.45 20.45h-3.55v-5.57c0-1.33-.02-3.04-1.85-3.04-1.86 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z"/></svg>'
)


def linkedin_card(url):
    """LinkedIn shows signed-out visitors a sign-up wall, so render a simple card instead."""
    path = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      html,body{{margin:0;width:1280px;height:800px;background:#0a66c2;font-family:system-ui,Segoe UI,sans-serif;color:#fff}}
      .wrap{{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:28px}}
      .name{{font-size:64px;font-weight:700}} .path{{font-size:34px;opacity:.85}}
      .btn{{margin-top:12px;padding:16px 36px;border:2px solid #fff;border-radius:999px;font-size:30px;font-weight:600}}
    </style></head><body><div class="wrap">{LINKEDIN_LOGO}
      <div class="name">LinkedIn</div><div class="path">{path}</div><div class="btn">View profile</div>
    </div></body></html>"""


X_LOGO = (
    '<svg viewBox="0 0 24 24" width="88" height="88"><path fill="#fff" d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"/></svg>'
)


def x_card(url):
    """x.com refuses headless browsers (HTTP error before the page loads), so render a card."""
    handle = "@" + url.rstrip("/").rsplit("/", 1)[-1]
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      html,body{{margin:0;width:1280px;height:800px;background:#0f1419;font-family:system-ui,Segoe UI,sans-serif;color:#fff}}
      .wrap{{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:28px}}
      .name{{font-size:56px;font-weight:700}}
      .btn{{margin-top:12px;padding:16px 36px;border:2px solid #fff;border-radius:999px;font-size:30px;font-weight:600}}
    </style></head><body><div class="wrap">{X_LOGO}
      <div class="name">{handle}</div><div class="btn">View profile</div>
    </div></body></html>"""


# URLs rendered from a local card instead of a screenshot of the live page.
CARDS = {"https://www.linkedin.com/": linkedin_card, "https://x.com/": x_card}


def outbound_links():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    urls = re.findall(r'<a [^>]*href="(https?://[^"]+)"', html)
    seen = []
    for url in urls:
        url = url.replace("&amp;", "&")
        if url not in seen and not any(h in url for h in SKIP_HOSTS):
            seen.append(url)
    return seen


def slug(url):
    name = re.sub(r"[^a-z0-9]+", "-", re.sub(r"^https?://", "", url.lower())).strip("-")[:48]
    return f"{name}-{hashlib.sha1(url.encode()).hexdigest()[:6]}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome")
        except Exception:
            browser = pw.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 800}, locale="en-US", color_scheme="light"
        )
        for url in outbound_links():
            page = context.new_page()
            try:
                card = next((make for prefix, make in CARDS.items() if url.startswith(prefix)), None)
                if card:
                    page.set_content(card(url))
                else:
                    # Not "networkidle": map pages keep streaming tiles and never settle.
                    page.goto(url, wait_until="load", timeout=45000)
                    page.wait_for_timeout(3000)
                    for prefix, action in ACTIONS.items():
                        if url.startswith(prefix):
                            action(page)
                png = page.screenshot()
            except Exception as error:
                print(f"skip ({error.__class__.__name__}): {url}")
                page.close()
                continue
            page.close()
            name = slug(url) + ".webp"
            with Image.open(io.BytesIO(png)) as im:
                im.convert("RGB").resize((640, 400), Image.LANCZOS).save(OUT / name, "WEBP", quality=80)
            manifest[url] = f"assets/previews/{name}"
            print(f"ok: {url} -> {name}")
        browser.close()
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
