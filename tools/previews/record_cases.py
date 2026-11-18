"""Record the short demo clips on the Cases page (one per case).

    python tools/previews/record_cases.py            # all cases
    python tools/previews/record_cases.py caaci      # one

Drives the installed Chrome with a window (the WebGL tubes need a real GPU),
records each site with Playwright, then ffmpeg trims the page load away and
writes assets/cases/<name>.mp4 (H.264, 960x720, muted, ~10 s, web-optimised)
plus assets/cases/<name>-poster.webp (its first frame). Needs ffmpeg on PATH.

The scripts only browse: they never sign in, submit forms or send chat
messages (iGuide's chat would spend AI credits on the live product).
"""

import functools
import http.server
import math
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "cases"
W, H = 1280, 960


def smooth_scroll(page, to, ms):
    page.evaluate(
        """([to, ms]) => new Promise(done => {
          const from = scrollY, t0 = performance.now()
          const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
          const step = now => { const t = Math.min(1, (now - t0) / ms); scrollTo(0, from + (to - from) * ease(t)); t < 1 ? requestAnimationFrame(step) : done() }
          requestAnimationFrame(step)
        })""",
        [to, ms],
    )


def glide(page, points, ms_each=500, steps=20):
    for x, y in points:
        page.mouse.move(x, y, steps=steps)
        page.wait_for_timeout(ms_each // steps)


def caaci(page, base):
    page.goto("https://caaciorg.com", wait_until="load")
    page.wait_for_timeout(2500)
    start = time.time()
    page.wait_for_timeout(1200)
    smooth_scroll(page, 1500, 2600)
    page.wait_for_timeout(500)
    smooth_scroll(page, 3000, 2200)
    page.wait_for_timeout(400)
    smooth_scroll(page, 0, 1800)
    # English -> 中文: the site is bilingual.
    toggle = page.locator("header button").filter(has_text="中").first
    box = toggle.bounding_box()
    glide(page, [(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)], 600)
    toggle.click()
    page.wait_for_timeout(2600)
    return start


def iguide(page, base):
    page.goto("https://iguide.chat/dorms", wait_until="load")
    page.wait_for_timeout(4500)
    start = time.time()
    page.wait_for_timeout(1500)
    glide(page, [(820, 420), (700, 520), (900, 600)], 900)
    page.get_by_role("button", name="List View").first.click()
    page.wait_for_timeout(1600)
    page.mouse.move(800, 600)
    for _ in range(8):
        page.mouse.wheel(0, 160)
        page.wait_for_timeout(180)
    page.wait_for_timeout(900)
    page.get_by_role("button", name="Map View").first.click()
    page.wait_for_timeout(2200)
    return start


def campustech(page, base):
    page.add_init_script("localStorage.setItem('campustech-theme','dark')")
    page.goto(base + "/", wait_until="networkidle")
    page.wait_for_timeout(3000)
    start = time.time()
    # The tubes follow the cursor.
    pts = [(640 + 300 * math.cos(a / 10), 480 + 180 * math.sin(a / 7)) for a in range(0, 63, 3)]
    glide(page, pts, 160, steps=6)
    # Pull the cord: light mode, and the dithered trail.
    knob = page.locator(".pullcord-knob").bounding_box()
    kx, ky = knob["x"] + knob["width"] / 2, knob["y"] + knob["height"] / 2
    glide(page, [(kx, ky)], 500)
    page.mouse.down()
    for i in range(1, 9):
        page.mouse.move(kx, ky + i * 6)
        page.wait_for_timeout(30)
    page.mouse.up()
    page.wait_for_timeout(500)
    glide(page, [(640 + 260 * math.cos(a / 8), 460 + 160 * math.sin(a / 5)) for a in range(0, 48, 3)], 120, steps=6)
    # Scroll into the sections: lines animate in.
    page.mouse.move(640, 600)
    for _ in range(9):
        page.mouse.wheel(0, 140)
        page.wait_for_timeout(160)
    page.wait_for_timeout(1400)
    return start


CASES = {"caaci": caaci, "iguide": iguide, "campustech": campustech}


def record(name, script, base, browser, tmp):
    context = browser.new_context(
        viewport={"width": W, "height": H}, locale="en-US", color_scheme="light",
        record_video_dir=str(tmp), record_video_size={"width": W, "height": H},
    )
    page = context.new_page()
    opened = time.time()
    start = script(page, base)
    end = time.time()
    video = page.video.path()
    context.close()  # flushes the video
    offset, length = start - opened, min(12, end - start)
    mp4, poster = OUT / f"{name}.mp4", OUT / f"{name}-poster.webp"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{offset:.2f}", "-i", str(video), "-t", f"{length:.2f}",
         "-vf", "scale=960:720:flags=lanczos,fps=30", "-c:v", "libx264", "-preset", "slow", "-crf", "27",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(mp4)],
        check=True,
    )
    # WebM too: browsers without H.264 (Chromium builds, some Linux/Android) play this one.
    webm = OUT / f"{name}.webm"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-c:v", "libvpx-vp9", "-crf", "38", "-b:v", "0",
         "-row-mt", "1", "-deadline", "good", "-an", str(webm)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-frames:v", "1", "-c:v", "libwebp", "-quality", "80", str(poster)],
        check=True,
    )
    kb = lambda p: p.stat().st_size // 1024
    print(f"ok: {name} -> {mp4.name} ({kb(mp4)} KB), {webm.name} ({kb(webm)} KB), {length:.1f}s, {poster.name}")


def webm_only(names):
    """Re-encode WebM and posters from existing MP4s (no re-recording)."""
    for name in names:
        mp4 = OUT / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-c:v", "libvpx-vp9", "-crf", "38", "-b:v", "0",
                        "-row-mt", "1", "-deadline", "good", "-an", str(OUT / f"{name}.webm")], check=True)
        print(f"ok: {name}.webm ({(OUT / f'{name}.webm').stat().st_size // 1024} KB)")


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is not on PATH")
    if "--webm-only" in sys.argv:
        return webm_only([n for n in sys.argv[1:] if n in CASES] or list(CASES))
    names = sys.argv[1:] or list(CASES)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False, args=["--window-size=1300,1060"])
        for name in names:
            record(name, CASES[name], base, browser, Path(tmp))
        browser.close()
    server.shutdown()


if __name__ == "__main__":
    main()
