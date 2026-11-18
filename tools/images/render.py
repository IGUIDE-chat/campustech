"""Render the "coming soon" hover cards with Playwright. (Icons come from
tools/images/logo.py; the link preview assets/og.jpg from tools/images/og_capture.py.)
Run: python tools/images/render.py"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

# "Coming soon" hover cards for the placeholder contact icons (data-preview in
# index.html): the platform's icon, its name and "Coming soon", read from the page.
import re as _re
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
SOON = _re.findall(
    r'<a href="\./coming-soon\.html" class="soon" data-preview="([^"]+)" aria-label="([^"]+?) \(coming soon\)"[^>]*>(<svg.*?</svg>)</a>',
    INDEX,
    _re.S,
)


def soon_card(label, svg):
    name = label.split(":")[0]
    svg = svg.replace('class="knockout"', 'fill="#0d0d12"').replace("<svg ", '<svg width="150" height="150" fill="#98989b" ')
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;700&display=swap" rel="stylesheet">
<style>html,body{{margin:0;width:1280px;height:800px;background:#0d0d12;font-family:Montserrat,sans-serif}}
.w{{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:34px}}
.n{{font-size:68px;font-weight:700;color:#f4f4f6}}.s{{font-size:40px;font-weight:500;color:#98989b;letter-spacing:.12em;text-transform:uppercase}}</style>
</head><body><div class="w">{svg}<div class="n">{name}</div><div class="s">Coming soon</div></div></body></html>"""


with sync_playwright() as pw:
    try:
        browser = pw.chromium.launch(channel="chrome")
    except Exception:
        browser = pw.chromium.launch()
    from PIL import Image
    import io
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    for path, label, svg in SOON:
        page.set_content(soon_card(label, svg), wait_until="networkidle")
        png = page.screenshot()
        with Image.open(io.BytesIO(png)) as im:
            im.convert("RGB").resize((640, 400), Image.LANCZOS).save(ROOT / path, "WEBP", quality=82)
        print("wrote", path)
    browser.close()
