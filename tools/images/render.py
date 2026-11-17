"""Render the social preview image (assets/og.png) and the iPhone icon
(assets/apple-touch-icon.png) with Playwright. Run: python tools/images/render.py"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FAVICON = (ROOT / "assets" / "favicon.svg").read_text(encoding="utf-8")

OG = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;700&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;width:1200px;height:630px;background:#0d0d12;overflow:hidden;font-family:Montserrat,sans-serif}
  svg{position:absolute;inset:0}
  .text{position:absolute;left:96px;top:150px;color:#f4f4f6}
  h1{margin:0;font-size:150px;font-weight:700;line-height:1;letter-spacing:-1px}
  h2{margin:8px 0 0;font-size:104px;font-weight:500;line-height:1}
  p{margin:34px 0 0;font-size:34px;font-weight:500;color:#98989b}
  .url{position:absolute;left:96px;bottom:56px;font-size:24px;letter-spacing:.12em;color:#5e5e62;text-transform:uppercase}
</style></head><body>
<svg width="1200" height="630" viewBox="0 0 1200 630">
  <defs><filter id="g" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
  <g fill="none" stroke-linecap="round" filter="url(#g)">
    <path d="M760 600 C 820 330, 980 210, 1180 170" stroke="#f967fb" stroke-width="10"/>
    <path d="M800 640 C 870 380, 1010 270, 1200 240" stroke="#6958d5" stroke-width="9"/>
    <path d="M850 660 C 920 430, 1040 330, 1210 310" stroke="#53bc28" stroke-width="8"/>
    <path d="M720 620 C 790 360, 950 250, 1150 110" stroke="#60aed5" stroke-width="6"/>
  </g>
</svg>
<div class="text"><h1>CAMPUS</h1><h2>TECH</h2><p>We build products for campus life.</p></div>
<div class="url">campustech.iguide.chat · UIUC</div>
</body></html>"""

ICON = f"""<!doctype html><html><body style="margin:0;width:180px;height:180px;overflow:hidden">
<div style="width:180px;height:180px">{FAVICON.replace('<svg ', '<svg width="180" height="180" ')}</div></body></html>"""

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
    page = browser.new_page(viewport={"width": 1200, "height": 630})
    page.set_content(OG, wait_until="networkidle")
    page.wait_for_timeout(500)
    page.screenshot(path=str(ROOT / "assets" / "og.png"))
    page = browser.new_page(viewport={"width": 180, "height": 180})
    page.set_content(ICON)
    page.screenshot(path=str(ROOT / "assets" / "apple-touch-icon.png"))
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
print("wrote assets/og.png, assets/apple-touch-icon.png")
