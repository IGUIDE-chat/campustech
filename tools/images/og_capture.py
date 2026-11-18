"""Capture the link preview (assets/og.jpg, 1200x630) from the real home page: the hero
lockup with the actual neon tubes, nav and cord hidden.

    python tools/images/og_capture.py          # writes candidates to tools/images/og-candidates/
    python tools/images/og_capture.py 2        # keeps candidate 2 as assets/og.jpg

Uses the installed Chrome with a window, so the tubes render on the GPU.
"""

import functools
import http.server
import io
import math
import socketserver
import sys
import threading
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = Path(__file__).resolve().parent / "og-candidates"
# A small viewport scaled 4x: the hero type is large relative to the card, as it
# needs to be in a phone-sized preview.
VIEW = {"width": 600, "height": 315}

HIDE = """
  .nav, #cord, .pullcord, .hero-align, .next, #loader, .preview { display: none !important; }
  html, body { overflow: hidden !important; }
  #og-url { position: fixed; left: 0; right: 0; bottom: 20px; z-index: 50;
            font: 500 11px Montserrat, sans-serif; letter-spacing: .14em; text-transform: uppercase; color: #6e6e74; }
"""


def main():
    if len(sys.argv) > 1:
        src = CANDIDATES / f"og-{sys.argv[1]}.jpg"
        Image.open(src).save(ROOT / "assets" / "og.jpg", "JPEG", quality=90)
        print(f"kept {src.name} as assets/og.jpg")
        return

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    CANDIDATES.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        ctx = browser.new_context(viewport=VIEW, device_scale_factor=4)
        ctx.add_init_script("try { localStorage.setItem('campustech-theme','dark'); localStorage.setItem('campustech-hero','left') } catch (e) {}")
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/", wait_until="networkidle")
        page.add_style_tag(content=HIDE)
        page.evaluate("document.body.insertAdjacentHTML('beforeend', '<div id=\"og-url\">campustech.iguide.chat · UIUC</div>')")
        page.wait_for_timeout(2500)
        # The URL line shares the lockup's left edge: start it where the tagline's text starts.
        page.evaluate("""() => {
          const r = document.createRange();
          r.selectNodeContents(document.querySelector('.tagline'));
          document.getElementById('og-url').style.paddingLeft = r.getClientRects()[0].left + 'px';
        }""")
        # Sweep the cursor around the right side so the tubes swirl beside the lockup.
        n = 0
        for a in range(0, 160):
            t = a / 10
            page.mouse.move(470 + 95 * math.cos(t), 160 + 105 * math.sin(t * 1.3), steps=2)
            page.wait_for_timeout(16)
            if a in (40, 70, 100, 130, 159):
                n += 1
                with Image.open(io.BytesIO(page.screenshot())) as im:
                    im.convert("RGB").resize((1200, 630), Image.LANCZOS).save(CANDIDATES / f"og-{n}.jpg", "JPEG", quality=90)
        browser.close()
    server.shutdown()
    print(f"wrote {n} candidates to {CANDIDATES}")


if __name__ == "__main__":
    main()
