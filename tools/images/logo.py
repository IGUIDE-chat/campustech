"""Render the placeholder logo: the hero lockup (CAMPUS / TECH / tagline, left
aligned) centred in a square. Writes assets/logo.png (light) and
assets/logo-dark.png (dark), 1024x1024, and the browser-tab / home-screen icons
from the same lockup, cropped tight (favicon.ico, favicon-32.png,
favicon-192.png, apple-touch-icon.png). Run: python tools/images/logo.py"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SIZE = 1024
PAD = 128  # CAMPUS spans the square minus this on each side

THEMES = {
    "logo.png": {"bg": "#ffffff", "ink": "#2d2e36", "muted": "#818286"},
    "logo-dark.png": {"bg": "#0d0d12", "ink": "#f4f4f6", "muted": "#98989b"},
}


def html(t, pad=PAD):
    # Proportions from the site: CAMPUS 80px/700, TECH 60px/500, tagline 16px/500,
    # 10px between lines. Everything is set in units of CAMPUS's size (--u) and
    # scaled so CAMPUS fills the width between the paddings.
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;700&display=swap" rel="stylesheet">
<style>
  html,body{{margin:0;width:{SIZE}px;height:{SIZE}px;background:{t['bg']};overflow:hidden;font-family:Montserrat,sans-serif}}
  body{{display:grid;place-items:center}}
  .lockup{{--u:100px;display:flex;flex-direction:column;align-items:flex-start}}
  .c{{font-size:var(--u);font-weight:700;line-height:1;color:{t['ink']}}}
  .t{{font-size:calc(var(--u)*.75);font-weight:500;line-height:1;margin-top:calc(var(--u)*.125);color:{t['ink']}}}
  .p{{font-size:calc(var(--u)*.2);font-weight:500;line-height:1.4;margin-top:calc(var(--u)*.125);color:{t['muted']}}}
</style></head><body>
<div class="lockup"><div class="c">CAMPUS</div><div class="t">TECH</div><div class="p">We build products for campus life.</div></div>
<script>
  document.fonts.ready.then(() => {{
    const l = document.querySelector('.lockup'), c = document.querySelector('.c')
    l.style.setProperty('--u', (100 * ({SIZE} - 2 * {pad}) / c.getBoundingClientRect().width) + 'px')
    document.body.dataset.ready = '1'
  }})
</script></body></html>"""


with sync_playwright() as pw:
    try:
        browser = pw.chromium.launch(channel="chrome")
    except Exception:
        browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": SIZE, "height": SIZE})
    for name, theme in THEMES.items():
        page.set_content(html(theme), wait_until="networkidle")
        page.wait_for_selector("body[data-ready]")
        page.wait_for_timeout(200)
        page.screenshot(path=str(ROOT / "assets" / name))
        print("wrote assets/" + name)
    # Tab icons: the light lockup with almost no margin, so the words are as big
    # as a 16-32px square allows; scaled down from 1024px for clean edges.
    import io
    from PIL import Image
    page.set_content(html(THEMES["logo.png"], pad=40), wait_until="networkidle")
    page.wait_for_selector("body[data-ready]")
    page.wait_for_timeout(200)
    with Image.open(io.BytesIO(page.screenshot())) as big:
        big = big.convert("RGB")
        for size, name in [(32, "favicon-32.png"), (192, "favicon-192.png"), (180, "apple-touch-icon.png")]:
            big.resize((size, size), Image.LANCZOS).save(ROOT / "assets" / name)
            print("wrote assets/" + name)
        big.resize((48, 48), Image.LANCZOS).save(ROOT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
        print("wrote favicon.ico")
    browser.close()
