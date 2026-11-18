"""Capture the link preview (assets/og.jpg, 1200x630) from the real home page: the hero
lockup with the actual neon tubes, nav and cord hidden.

    python tools/images/og_capture.py          # writes candidates to tools/images/og-candidates/
    python tools/images/og_capture.py 2        # keeps candidate 2 as assets/og.jpg

Only balanced candidates are kept: the text starts as far from the left edge as the tubes'
haze ends from the right. The current og.jpg is an upward arc from lower left to upper right:

    OG_STROKE=320,280,450,275,470,45 python tools/images/og_capture.py   # then keep the first
    OG_PHASE=1.7 OG_SWEEP=430,70,100 python tools/images/og_capture.py   # free swirls instead
    OG_DEBUG=1 ...                                                         # also save rejects

Uses the installed Chrome with a window, so the tubes render on the GPU.
"""

import functools
import http.server
import io
import math
import os
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
  /* The page centres the lockup; on the card that left a dead band on the left while the
     tubes filled the right. Start it 8% in (48 of 600 CSS px) and give the tubes the rest. */
  .hero { align-items: flex-start !important; padding-left: 48px !important; }
  #og-url { position: fixed; left: 0; right: 0; bottom: 20px; z-index: 50;
            font: 500 11px Montserrat, sans-serif; letter-spacing: .14em; text-transform: uppercase; color: #6e6e74; }
"""


def margins(im, lift=6):
    """(left, right) empty margins in px. The tubes' red haze counts as content, not as
    margin: a column is empty only if no pixel in it is more than `lift` above the background."""
    px = im.convert("RGB").load()
    w, h = im.size
    bg = sum(px[4, 4])
    used = [x for x in range(w) if any(sum(px[x, y]) - bg > lift for y in range(0, h, 3))]
    return used[0], w - 1 - used[-1]


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
        # Sweep the cursor beside the lockup so the tubes swirl there. Kept left of the edge:
        # their haze must end about as far from the right edge as the text starts from the left.
        # Snapshot often; keep only balanced cards (haze off the edge, margins within 30px).
        for old in CANDIDATES.glob("og-*.jpg"):
            old.unlink()
        n = shots = 0

        def snap(note=""):
            nonlocal n, shots
            shots += 1
            with Image.open(io.BytesIO(page.screenshot())) as im:
                card = im.convert("RGB").resize((1200, 630), Image.LANCZOS)
            left, right = margins(card)
            if right > 0 and abs(left - right) <= 30:
                n += 1
                card.save(CANDIDATES / f"og-{n}.jpg", "JPEG", quality=90)
                print(f"  og-{n}.jpg  margins left {left}px, right {right}px (haze counts as content) {note}")
            elif os.environ.get("OG_DEBUG"):
                card.save(CANDIDATES / f"rejected-{shots}.jpg", "JPEG", quality=90)
                print(f"  rejected-{shots}.jpg  margins left {left}px, right {right}px {note}")

        stroke = os.environ.get("OG_STROKE")
        if stroke:
            # Draw one shape: the tubes trail the cursor, so they take the path it just drew.
            # OG_STROKE="x0,y0,cx,cy,x1,y1" is a quadratic curve in CSS px; e.g. lower left to
            # upper right, bending upward: start, a control point low on the right, end high.
            x0, y0, qx, qy, x1, y1 = map(float, stroke.split(","))
            for frames in (14, 20, 28, 38):
                page.mouse.move(x0, y0, steps=8)
                page.wait_for_timeout(1800)  # let the trail gather at the start
                for i in range(frames + 1):
                    u = i / frames
                    page.mouse.move((1 - u) ** 2 * x0 + 2 * u * (1 - u) * qx + u * u * x1,
                                    (1 - u) ** 2 * y0 + 2 * u * (1 - u) * qy + u * u * y1)
                    page.wait_for_timeout(16)
                for after in (0, 3, 6, 10):
                    page.wait_for_timeout(16 * after)
                    snap(f"stroke {frames} frames, +{after}")
        else:
            # Other poses: OG_PHASE (start of the loop), OG_SWEEP="cx,rx,ry" (its centre and size, CSS px).
            phase = float(os.environ.get("OG_PHASE", "0"))
            cx, rx, ry = map(float, os.environ.get("OG_SWEEP", "430,70,100").split(","))
            for a in range(0, 400):
                t = a / 10 + phase
                page.mouse.move(cx + rx * math.cos(t), 160 + ry * math.sin(t * 1.3), steps=2)
                page.wait_for_timeout(16)
                if a >= 40 and a % 6 == 4:
                    snap()
        browser.close()
    server.shutdown()
    print(f"kept {n} balanced candidates of {shots} snapshots in {CANDIDATES}")


if __name__ == "__main__":
    main()
