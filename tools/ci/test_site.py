"""Browser regression tests (Playwright, Chromium). Run: python tools/ci/test_site.py

Serves the repo on a local port and replays, at desktop and phone sizes, every
bug this site has had; each test names the commit or issue it guards. Lists
every failure and exits non-zero if any test fails.
Needs: pip install playwright && python -m playwright install chromium
"""

import functools
import http.server
import socketserver
import sys
import threading
import time
import traceback
from pathlib import Path

import os

from playwright.sync_api import sync_playwright

# SLOW=4 python tools/ci/test_site.py throttles the CPU 4x, like the GPU-less CI
# runner (the tubes render in software there), to check the tests are not timing-bound.
SLOW = float(os.environ.get("SLOW", "0"))

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = {"viewport": {"width": 1280, "height": 800}}
PHONE = {"viewport": {"width": 375, "height": 812}, "is_mobile": True, "has_touch": True, "device_scale_factor": 2}
PAGES = ["/", "/cases.html", "/past.html", "/faq.html", "/privacy.html", "/terms.html", "/articles/", "/articles/pitch-your-idea.html", "/404.html", "/coming-soon.html"]

# Lines that animate on the home page: section children (not the next link), list items one by one.
LINES_JS = """[...document.querySelectorAll('.sections section')].flatMap(s => [...s.children]
  .filter(e => !e.matches('.next')).flatMap(e => e.tagName === 'UL' ? [...e.children] : [e]))"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(Quiet, directory=str(ROOT))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


class Site:
    def __init__(self, browser, base):
        self.browser = browser
        self.base = base

    def open(self, path="/", device=DESKTOP, theme=None, hero=None, width=None, settle=1200, tubes=False, reduced_motion=False):
        """tubes=False blocks the neon tubes (the page falls back to its static
        background). Without a GPU they render in software and starve everything
        else, which made timing checks a lottery on CI; only tests about the tubes
        themselves load them."""
        opts = dict(device)
        if width:
            opts["viewport"] = {"width": width, "height": opts["viewport"]["height"]}
        if reduced_motion:
            opts["reduced_motion"] = "reduce"
        ctx = self.browser.new_context(**opts)
        init = []
        if theme:
            init.append(f"localStorage.setItem('campustech-theme', '{theme}')")
        if hero:
            init.append(f"localStorage.setItem('campustech-hero', '{hero}')")
        if init:
            ctx.add_init_script("try { " + "; ".join(init) + " } catch (e) {}")
        if not tubes:
            ctx.route("**/vendor/tubes1.min.js*", lambda route: route.abort())
        page = ctx.new_page()
        if SLOW > 1:
            ctx.new_cdp_session(page).send("Emulation.setCPUThrottlingRate", {"rate": SLOW})
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.on("console", lambda m: page.errors.append(m.text) if m.type == "error" else None)
        page.goto(self.base + path, wait_until="load")
        page.wait_for_timeout(settle)
        return page

    @staticmethod
    def close(page):
        page.context.close()


def scroll_to(page, y):
    """Jump to y instantly, through ScrollSmoother when it runs, and let triggers fire."""
    page.evaluate(
        """y => { const sm = window.ScrollSmoother && ScrollSmoother.get();
        if (sm && document.documentElement.classList.contains('pinned')) sm.scrollTo(y, false); else window.scrollTo(0, y);
        window.ScrollTrigger && ScrollTrigger.update() }""",
        y,
    )


def max_scroll(page):
    return page.evaluate("Math.max(document.documentElement.scrollHeight - innerHeight, window.ScrollTrigger ? ScrollTrigger.maxScroll(window) : 0)")


def knob_center(page):
    b = page.locator(".pullcord-knob").bounding_box()
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


def theme(page):
    return page.evaluate("document.documentElement.dataset.theme")


def wait_for(page, js, arg=None, timeout=15000):
    """Wait until js(arg) is truthy (CI machines are slow; never rely on fixed sleeps).
    Polls on a timer (animation frames starve on a loaded machine) and checks once
    more directly before giving up."""
    try:
        page.wait_for_function(js, arg=arg, timeout=timeout, polling=100)
        return True
    except Exception:  # noqa: BLE001 - the caller asserts with a clear message
        try:
            return bool(page.evaluate(js, arg))
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------- page health


@test
def no_console_errors_on_any_page(site):
    """Every page, both themes, desktop and phone: no JS errors."""
    for device_name, device in (("desktop", DESKTOP), ("phone", PHONE)):
        for t in ("dark", "light"):
            for path in PAGES:
                page = site.open(path, device, theme=t, settle=900, tubes=True)
                assert not page.errors, f"{path} ({device_name}, {t}): {page.errors[:3]}"
                Site.close(page)


@test
def loading_screen_hidden_after_load_and_previewable(site):
    """59c0a6b / dcc0f9a: loader only while loading; skeleton, not dots; ?loading keeps it."""
    page = site.open("/")
    assert page.evaluate("document.documentElement.classList.contains('loaded')"), "html.loaded missing after load"
    assert page.evaluate("getComputedStyle(document.getElementById('loader')).display") == "none"
    Site.close(page)
    page = site.open("/?loading", settle=1000)
    assert wait_for(page, "getComputedStyle(document.getElementById('loader')).visibility === 'visible'"), "?loading did not keep the loader"
    assert page.locator("#loader .sk-hero").count() == 1, "home skeleton missing"
    Site.close(page)
    page = site.open("/faq.html?loading", settle=1000)
    assert page.locator("#loader .sk-page").count() == 1, "sub-page skeleton missing"
    Site.close(page)


@test
def phone_has_no_horizontal_overflow(site):
    """Fit on mobile and narrow screens."""
    for path in PAGES:
        page = site.open(path, PHONE, settle=600)
        over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert over <= 0, f"{path}: page is {over}px wider than the phone screen"
        Site.close(page)


# ---------------------------------------------------------------- pull cord


@test
def cord_switches_theme_on_release_not_while_held(site):
    """171df4b: nothing changes while the cord is held down; release switches."""
    page = site.open("/", theme="dark")
    x, y = knob_center(page)
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 11):
        page.mouse.move(x, y + i * 14)
        page.wait_for_timeout(16)
    page.wait_for_timeout(400)
    assert theme(page) == "dark", "theme switched while the cord was still held"
    page.mouse.up()
    assert wait_for(page, "document.documentElement.dataset.theme === 'light'"), "release did not switch the theme"
    assert page.evaluate("localStorage.getItem('campustech-theme')") == "light", "theme not remembered"
    Site.close(page)


@test
def cord_svg_holds_the_whole_swing(site):
    """iPhone: a wide swing showed the rope cut off mid-way with no knob. The SVG was 64px wide
    and drew the swing outside its box (overflow: visible), which iOS WebKit may clip. The rope
    and knob must stay inside the SVG's own box at every frame of a hard swing."""
    page = site.open("/", theme="dark")
    x, y = knob_center(page)
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 13):
        page.mouse.move(x - i * 22, y + i * 6)
        page.wait_for_timeout(16)
    page.mouse.up()
    worst = page.evaluate(
        """() => new Promise(done => {
          const svg = document.querySelector('.pullcord svg'), box = () => svg.getBoundingClientRect()
          let worst = 1e9, n = 0
          const tick = () => {
            const s = box()
            for (const el of svg.querySelectorAll('path, circle')) {
              const r = el.getBoundingClientRect()
              worst = Math.min(worst, r.left - s.left, s.right - r.right, s.bottom - r.bottom)
            }
            if (++n < 90) requestAnimationFrame(tick); else done(Math.round(worst))
          }
          tick()
        })"""
    )
    assert worst >= 0, f"rope or knob drawn {-worst}px outside the cord's SVG box (iOS clips it)"
    Site.close(page)


@test
def cord_click_plays_a_pull_and_switches(site):
    """d3d9249: a click animates a real pull (and switches on release)."""
    page = site.open("/", theme="light")
    page.locator(".pullcord-knob").click()
    assert wait_for(page, "document.documentElement.dataset.theme === 'dark'"), "click did not switch the theme"
    Site.close(page)


@test
def cord_is_on_top_and_grabbable_everywhere(site):
    """171df4b: on phones the cord was covered by the text area; the grab area runs up the rope."""
    for device_name, device in (("desktop", DESKTOP), ("phone", PHONE)):
        page = site.open("/", device)
        for target in ("top", "products", "join", "team", "contact"):
            page.evaluate(f"document.getElementById('{target}').scrollIntoView()")
            page.wait_for_timeout(300)
            x, y = knob_center(page)
            hit = page.evaluate(f"document.elementFromPoint({x}, {y})?.className || ''")
            assert "pullcord-knob" in hit, f"{device_name} @{target}: knob covered by {hit!r}"
            if device_name == "phone":
                above = page.evaluate(f"document.elementFromPoint({x}, {y - 50})?.className || ''")
                assert "pullcord-knob" in above, f"phone @{target}: rope above the knob is not grabbable ({above!r})"
        Site.close(page)


# ---------------------------------------------------------------- themes and trail


@test
def theme_switching_keeps_both_effects_working(site):
    """d3d9249 / NaN bug / 'light to dark no more cursor focus': effects survive switching."""
    page = site.open("/", theme="dark", tubes=True)
    for expected in ("light", "dark", "light", "dark"):
        page.locator(".pullcord-knob").click()
        assert wait_for(page, "t => document.documentElement.dataset.theme === t", expected), f"click did not switch to {expected}"
        page.wait_for_timeout(300)
        bg = page.evaluate("getComputedStyle(document.querySelector('.bg')).display")
        trail = page.evaluate("getComputedStyle(document.getElementById('trail')).display")
        if expected == "light":
            assert bg == "none" and trail == "block", f"light: tubes {bg}, trail {trail}"
        else:
            assert bg != "none" and trail == "none", f"dark: tubes {bg}, trail {trail}"
            w = page.evaluate("document.querySelector('.bg canvas').width")
            assert w > 0, "tubes canvas has zero size after switching back to dark"
    assert not page.errors, page.errors[:3]
    Site.close(page)


@test
def light_trail_keeps_its_colour_and_layers(site):
    """b1908a1: original trail colour; text under it turns white via two overlay layers below the cord."""
    page = site.open("/", theme="light")
    layers = page.evaluate(
        """[...document.querySelectorAll('.trail')].map(c => [c.className, getComputedStyle(c).mixBlendMode, +getComputedStyle(c).zIndex])"""
    )
    names = {l[0]: l for l in layers}
    assert names.get("trail trail-flip", [None, None])[1] == "difference", f"inverting layer missing: {layers}"
    assert names.get("trail trail-dodge", [None, None])[1] == "color-dodge", f"brightening layer missing: {layers}"
    cord_z = int(page.evaluate("getComputedStyle(document.querySelector('.pullcord')).zIndex"))
    assert all(l[2] < cord_z for l in layers), "a trail layer sits above the pull cord"
    # Sweep the pointer across the hero and look for the trail's own colour on screen.
    box = page.locator(".hero-text").bounding_box()
    for i in range(30):
        page.mouse.move(box["x"] + box["width"] * i / 29, box["y"] + box["height"] * 0.5)
        page.wait_for_timeout(16)
    shot = page.screenshot(clip={"x": box["x"] - 80, "y": box["y"] - 80, "width": box["width"] + 160, "height": box["height"] + 160})
    from io import BytesIO

    from PIL import Image

    img = Image.open(BytesIO(shot)).convert("RGB")
    px = list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())
    near = lambda p, c, tol=14: all(abs(a - b) <= tol for a, b in zip(p, c))
    trail = sum(near(p, (0x69, 0x58, 0xD5)) for p in px)
    white = sum(min(p) > 235 for p in px)
    assert trail > 200, f"trail colour #6958d5 barely on screen ({trail} px): colours drifted"
    assert white > 200, "no white pixels near the trail"
    Site.close(page)


@test
def phones_skip_the_trail(site):
    """0aee37d: the trail follows a mouse only; touch phones must not composite its layers."""
    page = site.open("/", PHONE, theme="light")
    assert page.locator(".trail-flip, .trail-dodge").count() == 0, "trail overlays exist on a touch phone"
    Site.close(page)


# ---------------------------------------------------------------- scrolling and nav


@test
def smooth_scroll_on_desktop_native_on_phones(site):
    """'GSAP disappeared' / phone jank: smoother pins on desktop, phones scroll natively with a band behind the nav."""
    page = site.open("/")
    assert page.evaluate("document.documentElement.classList.contains('pinned')"), "ScrollSmoother not active on desktop"
    # Desktop scroll stutter: the moving content needs its own GPU layer.
    assert "transform" in page.evaluate("getComputedStyle(document.querySelector('#smooth-content')).willChange"), \
        "#smooth-content lost will-change: transform (desktop scroll stutter)"
    Site.close(page)
    page = site.open("/", PHONE)
    assert not page.evaluate("document.documentElement.classList.contains('pinned')"), "phones must scroll natively"
    assert page.evaluate("getComputedStyle(document.querySelector('#smooth-content')).willChange") == "auto", \
        "phones scroll natively; no extra GPU layer for the page"
    page.evaluate("window.scrollTo(0, 120)")
    page.wait_for_timeout(300)
    assert page.evaluate("document.querySelector('.nav').classList.contains('under')"), "no band behind the nav after scrolling on a phone"
    Site.close(page)


@test
def nav_hides_while_scrolling_and_returns(site):
    """'navigate should vanish when scrolling': hidden while scrolling, back when idle."""
    page = site.open("/", PHONE)
    page.evaluate("window.scrollTo(0, 400)")
    page.wait_for_timeout(80)
    assert not page.evaluate("document.querySelector('.nav').classList.contains('show')"), "nav still shown while scrolling"
    assert wait_for(page, "document.querySelector('.nav').classList.contains('show')", timeout=5000), "nav did not come back when idle"
    Site.close(page)


@test
def nav_layout_is_adaptive(site):
    """295ae34 / f675685 / 75618e4: one row on the title's axis when it fits, clear of the cord; wraps from the left."""
    for width in (1280, 1440, 2000):
        page = site.open("/", width=width)
        r = page.evaluate(
            """(() => { const n = document.querySelector('.nav-links').getBoundingClientRect();
            const h = document.querySelector('.hero-text').getBoundingClientRect();
            const c = document.querySelector('.pullcord-knob').getBoundingClientRect();
            return { mid: (n.left + n.right) / 2, axis: h.left + h.width / 2, right: n.right, cord: c.left, h: n.height } })()"""
        )
        assert r["h"] < 30, f"{width}px: nav wrapped although it fits"
        assert abs(r["mid"] - r["axis"]) <= 2, f"{width}px: nav centre {r['mid']:.0f} off the title axis {r['axis']:.0f}"
        assert r["right"] < r["cord"] - 8, f"{width}px: nav runs into the cord"
        Site.close(page)
    page = site.open("/", PHONE)
    r = page.evaluate(
        """(() => { const links = [...document.querySelectorAll('.nav-links a')].map(a => a.getBoundingClientRect());
        const c = document.querySelector('.pullcord-knob').getBoundingClientRect();
        return { left: Math.min(...links.map(l => l.left)), right: Math.max(...links.map(l => l.right)), cord: c.left } })()"""
    )
    assert abs(r["left"] - 16) <= 2, f"phone: wrapped nav should start at the left edge (got {r['left']:.0f})"
    assert r["right"] < r["cord"], "phone: nav runs into the cord"
    Site.close(page)


@test
def in_page_links_jump(site):
    """84 / 6b7d68a / next links: nav, tagline 'products' and next-section links jump to their section."""
    page = site.open("/")
    page.locator(".tagline a").click()
    wait_for(page, "Math.abs(document.getElementById('products').getBoundingClientRect().top) < 120")
    top = page.evaluate("document.getElementById('products').getBoundingClientRect().top")
    assert abs(top) < 120, f"tagline link did not reach Products (top {top:.0f})"
    color = page.evaluate("[getComputedStyle(document.querySelector('.tagline a')).color, getComputedStyle(document.querySelector('.tagline')).color]")
    assert color[0] == color[1], f"tagline link colour {color[0]} differs from the tagline {color[1]} (#app a specificity bug)"
    Site.close(page)
    page = site.open("/")
    page.locator(".hero .next").click()
    wait_for(page, "Math.abs(document.getElementById('products').getBoundingClientRect().top) < 120")
    top = page.evaluate("document.getElementById('products').getBoundingClientRect().top")
    assert abs(top) < 120, f"next link did not reach Products (top {top:.0f})"
    Site.close(page)


@test
def refresh_starts_at_the_top(site):
    """Refresh jumped back to Contact: in-page links wrote #contact into the address bar."""
    page = site.open("/")
    page.locator(".nav-links a[href='#contact']").click()
    wait_for(page, "Math.abs(document.getElementById('contact').getBoundingClientRect().top) < 150")
    assert page.evaluate("location.hash") == "", "an in-page link wrote its hash into the address bar"
    page.reload(wait_until="load")
    page.wait_for_timeout(1200)
    top = page.evaluate("document.getElementById('top').getBoundingClientRect().top")
    assert abs(top) < 5, f"refresh did not start at the top (hero top {top:.0f})"
    Site.close(page)
    page = site.open("/#join")
    assert wait_for(page, "Math.abs(document.getElementById('join').getBoundingClientRect().top) < 150"), "a shared /#join link did not land on Join"
    assert page.evaluate("location.hash") == "", "the shared hash stayed in the address bar (a refresh would jump again)"
    Site.close(page)


@test
def nothing_expensive_runs_while_scrolling(site):
    """Scroll stutter: no page-wide mask while scrolling; the idle light trail does no work."""
    page = site.open("/")
    for i in range(1, 25):
        scroll_to(page, i * 40)
        page.wait_for_timeout(40)
    mask = page.evaluate("getComputedStyle(document.getElementById('smooth-wrapper')).maskImage || getComputedStyle(document.getElementById('smooth-wrapper')).webkitMaskImage")
    assert mask in ("none", "", None), f"the page layer is masked while scrolling ({mask[:40]})"
    assert wait_for(page, "document.documentElement.classList.contains('nav-masked')", timeout=5000), "mask never returned with the nav"
    Site.close(page)
    page = site.open("/", theme="light")
    page.wait_for_timeout(1500)
    vis = page.evaluate("[...document.querySelectorAll('.trail-flip, .trail-dodge')].map(c => getComputedStyle(c).visibility)")
    assert vis and all(v == "hidden" for v in vis), f"idle trail layers are still composited: {vis}"
    page.mouse.move(400, 400)
    page.mouse.move(500, 420)
    assert wait_for(page, "[...document.querySelectorAll('.trail-flip')].every(c => getComputedStyle(c).visibility === 'visible')", timeout=3000), "trail layers did not come back on mouse move"
    Site.close(page)


# ---------------------------------------------------------------- line animation


def step_scroll(page, direction, step=80):
    """Scroll the whole page in small steps, entirely inside the page so the
    observation right after each step does not depend on machine speed (round
    trips on a slow CI runner let animations finish before they were seen).
    Returns (lines dropped while on screen, lines seen, hidden lines first seen
    already fully visible); page.early lists the latter."""
    res = page.evaluate(
        f"""async ([dir, step]) => {{
        const lines = {LINES_JS};
        const wasHidden = new Set(lines.filter(el => +getComputedStyle(el).opacity < 0.05));
        const sm = window.ScrollSmoother && ScrollSmoother.get(); const pinned = document.documentElement.classList.contains('pinned');
        const max = Math.max(document.documentElement.scrollHeight - innerHeight, window.ScrollTrigger ? ScrollTrigger.maxScroll(window) : 0);
        const ys = []; if (dir === 'down') for (let y = 0; y <= max; y += step) ys.push(y); else for (let y = max; y >= 0; y -= step) ys.push(y);
        const last = new Map(), seen = new Set(), dropped = [], early = [];
        for (const y of ys) {{
          if (sm && pinned) sm.scrollTo(y, false); else window.scrollTo(0, y);
          ScrollTrigger.update();
          for (const el of lines) {{
            const r = el.getBoundingClientRect(); const on = r.bottom > 0 && r.top < innerHeight; const o = +getComputedStyle(el).opacity;
            const prev = last.get(el);
            if (on && prev && prev.on && o < prev.o - 0.05) dropped.push(el.textContent.trim().slice(0, 20));
            if (on && !seen.has(el)) {{ seen.add(el); if (o > 0.95 && wasHidden.has(el)) early.push(el.textContent.trim().slice(0, 18) + ' top=' + Math.round(r.top)) }}
            last.set(el, {{ on, o }});
          }}
          await new Promise(r => setTimeout(r, 60));
        }}
        return [dropped, seen.size, early];
      }}""",
        [direction, step],
    )
    page.early = res[2]
    return res[0], res[1], len(res[2])


def visible_lines_ok(page, timeout=10000):
    """True once every line on screen is fully visible (waits for slow animations)."""
    return wait_for(
        page,
        # Lines in the outer 8% strips are correctly still hidden: they animate once 8% in.
        f"""() => {LINES_JS}.filter(el => {{ const r = el.getBoundingClientRect(); return r.bottom > innerHeight * 0.1 && r.top < innerHeight * 0.9 }})
        .every(el => +getComputedStyle(el).opacity > 0.99)""",
        timeout=timeout,
    )


def stuck_lines(page):
    """Diagnostics: lines inside the 10-90% band that are not fully visible."""
    return page.evaluate(
        f"""{LINES_JS}.filter(el => {{ const r = el.getBoundingClientRect(); return r.bottom > innerHeight * 0.1 && r.top < innerHeight * 0.9 }})
        .filter(el => +getComputedStyle(el).opacity <= 0.99)
        .map(el => el.textContent.trim().slice(0, 18) + ' op=' + (+getComputedStyle(el).opacity).toFixed(2) + ' top=' + Math.round(el.getBoundingClientRect().top))"""
    )


@test
def lines_animate_in_view_both_directions(site):
    """9b61173 / c4ec5e5 / 1d62937: lines animate as they enter (also scrolling up), never vanish on screen."""
    for device_name, device in (("desktop", DESKTOP), ("phone", PHONE)):
        page = site.open("/", device)
        dropped, _, _ = step_scroll(page, "down")
        assert not dropped, f"{device_name} scrolling down: lines faded while on screen: {dropped[:5]}"
        page.wait_for_timeout(1200)
        assert visible_lines_ok(page), f"{device_name}: lines on screen still invisible after scrolling down"
        dropped, seen, seen_visible = step_scroll(page, "up")
        assert not dropped, f"{device_name} scrolling up: lines faded while on screen: {dropped[:5]}"
        assert seen >= 20, f"{device_name}: only {seen} lines checked"
        # Of the lines hidden when the upward pass starts, none may have finished animating before it appears.
        assert seen_visible <= 1, f"{device_name} scrolling up: {seen_visible} of {seen} lines had already finished animating before they came on screen: {page.early}"
        page.wait_for_timeout(1200)
        assert visible_lines_ok(page), f"{device_name}: lines on screen still invisible after scrolling up"
        Site.close(page)


@test
def text_never_stays_hidden_even_without_scroll_triggers(site):
    """0bd241b: 'text exists but is invisible' on phones; the safety net shows on-screen text anyway."""
    page = site.open("/", PHONE)
    page.evaluate(
        f"""ScrollTrigger.getAll().forEach(t => t.disable(false)); const j = document.getElementById('join');
        gsap.set({LINES_JS}.filter(e => j.contains(e)), {{ opacity: 0, y: 40 }}); j.scrollIntoView()"""
    )
    page.wait_for_timeout(2200)
    assert visible_lines_ok(page), "on-screen text stayed invisible when ScrollTrigger missed it"
    Site.close(page)


@test
def nav_jumps_show_the_section_and_keep_it_shown(site):
    """Phone: tapping Contact left its heading, email and icons invisible. The jump entered all
    25 lines at once, the stagger made Contact wait ~2s, and the late stagger reset it to
    invisible after the safety net had shown it. Lines must show fast and stay shown."""
    on_screen = """sel => [...document.querySelectorAll(sel)].filter(e => {
        const r = e.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight })
        .map(e => +getComputedStyle(e).opacity)"""
    for device in (PHONE, DESKTOP):
        page = site.open("/", device)
        for target, sel in (("#contact", "#contact > *"), ("#products", "#products li"), ("#team", "#team li"), ("#contact", "#contact > *")):
            page.evaluate("t => document.querySelector('.nav-links a[href=\"' + t + '\"]').click()", target)
            ok = wait_for(page, f"({on_screen})({sel!r}).every(o => o > 0.98)", timeout=6000)
            assert ok, f"{target}: lines on screen not shown after the jump: {page.evaluate(on_screen, sel)}"
            page.wait_for_timeout(2500)  # the old stagger reset lines ~2s after the jump
            ops = page.evaluate(on_screen, sel)
            assert ops and all(o > 0.98 for o in ops), f"{target}: lines went invisible again after the jump: {ops}"
        Site.close(page)


@test
def lines_never_fight_the_scroll_direction(site):
    """Phone: 'scrolling up and down is fighting'. A line still rising into place kept rising
    after the page reversed (and dropping lines kept dropping), so text moved against the
    finger. Flick down and up 6 times; at most one frame per reversal may move against it."""
    page = site.open("/", PHONE)
    result = page.evaluate(
        """async () => {
          const lines = [...document.querySelectorAll('.sections section > :not(.next), .sections section > ul > li')].filter(e => e.tagName !== 'UL')
          const ty = e => new DOMMatrix(getComputedStyle(e).transform).m42
          const frame = () => new Promise(r => requestAnimationFrame(r))
          let px = 0, frames = 0, prev = lines.map(ty), prevY = scrollY
          const sample = () => {
            const now = lines.map(ty), dS = scrollY - prevY
            if (Math.abs(dS) > 0.5) {
              let f = 0
              lines.forEach((e, i) => {
                const r = e.getBoundingClientRect(); if (r.bottom < 0 || r.top > innerHeight) return
                const dT = now[i] - prev[i]
                if (Math.sign(dT) === Math.sign(dS) && Math.abs(dT) > 0.5) f += Math.abs(dT)
              })
              if (f) { px += f; frames++ }
            }
            prev = now; prevY = scrollY
          }
          window.scrollTo(0, 900); for (let i = 0; i < 40; i++) { await frame(); sample() }
          for (let k = 0; k < 6; k++) for (let i = 0; i < 10; i++) { window.scrollBy(0, (k % 2 ? -1 : 1) * 45); await frame(); sample() }
          for (let i = 0; i < 60; i++) { await frame(); sample() }
          return { px: Math.round(px), frames }
        }"""
    )
    assert result["frames"] <= 10, f"lines moved against the scroll on {result['frames']} frames ({result['px']}px)"
    Site.close(page)


@test
def reading_pages_animate_once(site):
    """d6a1080: articles must not replay or fade out when scrolling back and forth."""
    page = site.open("/articles/pitch-your-idea.html")
    page.evaluate("window.__lines = [...document.querySelector('.prose').children]")
    lowest = 1.0
    top = max_scroll(page)
    for y in list(range(0, top + 1, 60)) + list(range(top, -1, -60)) + list(range(0, top + 1, 60)):
        scroll_to(page, y)
        page.wait_for_timeout(50)
    ok = wait_for(page, "() => window.__lines.every(e => +getComputedStyle(e).opacity > 0.99)")
    lowest = min(page.evaluate("window.__lines.map(e => +getComputedStyle(e).opacity)"))
    assert ok, f"a reading-page line is not fully visible after scrolling back and forth ({lowest})"
    Site.close(page)


# ---------------------------------------------------------------- layout


@test
def hero_left_by_default_toggle_centres_and_remembers(site):
    """7141a85 / cc0e583 / TECH-left bug: three lines share a left edge; centred mode centres TECH under CAMPUS."""
    glyph_box = """sel => { const r = document.createRange(); r.selectNodeContents(document.querySelector(sel)); const b = r.getBoundingClientRect(); return [b.left, b.right] }"""
    page = site.open("/")
    campus = page.evaluate("document.querySelector('.hero h1').firstChild.parentNode.getBoundingClientRect().left")
    tech = page.evaluate(glyph_box, ".hero-sub")
    tagline = page.evaluate(glyph_box, ".tagline")
    assert abs(tech[0] - campus) <= 2 and abs(tagline[0] - campus) <= 2, f"lines not left-aligned: {campus:.0f}, {tech[0]:.0f}, {tagline[0]:.0f}"
    page.locator("#hero-align").click()
    page.wait_for_timeout(300)
    h1 = page.evaluate("(() => { const b = document.querySelector('.hero h1').getBoundingClientRect(); return [b.left, b.right] })()")
    tech = page.evaluate(glyph_box, ".hero-sub")
    assert abs((tech[0] + tech[1]) / 2 - (h1[0] + h1[1]) / 2) <= 3, "centred mode: TECH is not centred under CAMPUS"
    page.reload(wait_until="load")
    page.wait_for_timeout(600)
    assert not page.evaluate("document.documentElement.classList.contains('hero-left')"), "alignment choice not remembered"
    Site.close(page)


HERO_INK_JS = """async () => {
  await document.fonts.ready
  const bearing = (weight, ch) => {  // left side bearing / font size, by pixel scan at 1000px
    const size = 1000, pad = 200, cv = document.createElement('canvas')
    cv.width = size * 2; cv.height = size * 1.6
    const c = cv.getContext('2d'); c.font = `${weight} ${size}px Montserrat`; c.fillText(ch, pad, size * 1.2)
    const d = c.getImageData(0, 0, cv.width, cv.height).data
    let left = cv.width
    for (let y = 0; y < cv.height; y++) for (let x = 0; x < left; x++) if (d[(y * cv.width + x) * 4 + 3] > 127) { left = x; break }
    return (left - pad) / size
  }
  const h1 = document.querySelector('.hero h1'), sub = h1.querySelector('.hero-sub'), tag = document.querySelector('.hero .tagline')
  const ink = (el, node) => {
    const s = getComputedStyle(el), r = document.createRange(), size = parseFloat(s.fontSize)
    r.setStart(node, 0); r.setEnd(node, 1)
    return { x: r.getBoundingClientRect().left + bearing(s.fontWeight, node.textContent.trim()[0].toUpperCase()) * size, size }
  }
  const C = ink(h1, h1.firstChild), T = ink(sub, sub.firstChild), W = ink(tag, tag.firstChild)
  return { overshootEm: (T.x - C.x) / C.size, techVsTagline: T.x - W.x }
}"""


@test
def hero_lines_share_an_optical_left_edge(site):
    """Skylar's review: left-aligned, CAMPUS looked indented. Each size has its own side bearing
    (the bold C starts 0.039em in), and a round C needs to overshoot a straight T. The ink of TECH
    and the tagline must line up, with the C 0.01-0.03em past them, at every screen width."""
    for width in (360, 768, 1280, 1920):
        page = site.open("/", width=width)
        r = page.evaluate(HERO_INK_JS)
        assert abs(r["techVsTagline"]) <= 0.6, f"{width}px: TECH and the tagline start {r['techVsTagline']:.2f}px apart"
        assert 0.01 <= r["overshootEm"] <= 0.03, f"{width}px: CAMPUS's C overshoots by {r['overshootEm']:.3f}em (want 0.01-0.03)"
        Site.close(page)


@test
def type_is_fluid(site):
    """d76c474: font sizes scale down on narrow screens."""
    big = site.open("/", width=1280)
    small = site.open("/", PHONE)
    size = lambda p, sel: float(p.evaluate(f"getComputedStyle(document.querySelector('{sel}')).fontSize").rstrip("px"))
    for sel in (".hero h1", ".tagline", ".sections h2"):
        assert size(small, sel) < size(big, sel), f"{sel} does not shrink on a phone"
    Site.close(big)
    Site.close(small)


@test
def team_rows_follow_screen_width(site):
    """31b8077: 1 per row on phones, then 2, 3, 4 (4 + 3)."""
    expected = {375: "1+1+1+1+1+1+1", 700: "2+2+2+1", 900: "3+3+1", 1280: "4+3"}
    for width, rows in expected.items():
        page = site.open("/", PHONE if width < 560 else DESKTOP, width=width, settle=700)
        got = page.evaluate(
            """(() => { const rows = {}; document.querySelectorAll('#team li').forEach(li => { const t = Math.round(li.offsetTop); rows[t] = (rows[t] || 0) + 1 });
            return Object.keys(rows).sort((a, b) => a - b).map(k => rows[k]).join('+') })()"""
        )
        assert got == rows, f"{width}px: team rows {got}, expected {rows}"
        Site.close(page)


@test
def link_preview_centres_on_the_link_text(site):
    """'preview is not centered': the hover card sits centred over the hovered text."""
    page = site.open("/")
    scroll_to(page, page.evaluate("document.getElementById('products').offsetTop + document.querySelector('.sections').offsetTop"))
    # Wait for scrolling to settle (the nav returns when idle); scrolling hides previews.
    wait_for(page, "document.querySelector('.nav').classList.contains('show')", timeout=8000)
    li_js = "[...document.querySelectorAll('#products li')].find(li => li.textContent.includes('AI Chat'))"
    ok = wait_for(page, f"+getComputedStyle({li_js}).opacity > 0.95")
    assert ok, f"the AI Chat line never became visible (opacity {page.evaluate(f'getComputedStyle({li_js}).opacity')})"
    box = page.locator("#products a", has_text="AI Chat").first.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    wait_for(page, "+getComputedStyle(document.querySelector('.preview')).opacity > 0.9", timeout=5000)
    r = page.evaluate(
        """(() => { const p = document.querySelector('.preview').getBoundingClientRect();
        const r = document.createRange(); r.selectNodeContents([...document.querySelectorAll('#products a')].find(a => a.textContent.includes('AI Chat')));
        const t = r.getBoundingClientRect(); return { op: +getComputedStyle(document.querySelector('.preview')).opacity, p: (p.left + p.right) / 2, t: (t.left + t.right) / 2 } })()"""
    )
    assert r["op"] > 0.5, "no preview card on hover"
    assert abs(r["p"] - r["t"]) <= 4, f"preview centre {r['p']:.0f} vs link text centre {r['t']:.0f}"
    Site.close(page)


@test
def rso_websites_previews_cases_and_cases_show_the_sites(site):
    """'rso website加悬浮预览' / 'should preview cases': hovering 'RSO websites' previews the Cases
    page it links to. 'cases should show the cases' / 'recording?': each card plays a demo clip
    while on screen (poster first), hovering it pops up no second preview, and with reduced
    motion the clips stay on their posters."""
    page = site.open("/")
    link = page.locator("#products a", has_text="RSO websites").first
    link.scroll_into_view_if_needed()
    wait_for(page, "document.querySelector('.nav').classList.contains('show')", timeout=8000)
    li = "[...document.querySelectorAll('#products li')].find(li => li.textContent.includes('RSO websites'))"
    assert wait_for(page, f"+getComputedStyle({li}).opacity > 0.95"), "the RSO websites line never became visible"
    box = link.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    assert wait_for(page, "+getComputedStyle(document.querySelector('.preview')).opacity > 0.9", timeout=5000), "no preview on RSO websites"
    src = page.evaluate("document.querySelector('.preview img').src")
    assert "campustech-cases" in src, f"RSO websites previews {src}, not the Cases page it links to"
    assert wait_for(page, "document.querySelector('.preview img').naturalWidth > 0", timeout=5000), "the preview image did not load"
    Site.close(page)

    page = site.open("/cases.html")
    clip = page.locator(".case-video").first
    clip.scroll_into_view_if_needed()
    assert wait_for(page, "+getComputedStyle(document.querySelector('.cases')).opacity > 0.95"), "the cases gallery never became visible"
    w = page.evaluate("document.querySelector('.case-video').getBoundingClientRect().width")
    assert w >= 300, f"the case clip is only {w:.0f}px wide"
    assert "caaciorg.com" in page.evaluate("document.querySelector('.case-shot').href"), "the CAACI card does not open caaciorg.com"
    playing = "(() => { const v = document.querySelector('.case-video'); return !v.paused && v.readyState >= 2 && v.currentTime > 0.3 })()"
    state = "(() => { const v = document.querySelector('.case-video'); return {paused: v.paused, ready: v.readyState, t: v.currentTime, src: v.currentSrc, err: v.error && v.error.code} })()"
    assert wait_for(page, playing, timeout=10000), f"the CAACI clip does not play on screen: {page.evaluate(state)}"
    box = clip.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(600)
    op = page.evaluate("(() => { const p = document.querySelector('.preview'); return p ? +getComputedStyle(p).opacity : 0 })()")
    assert op < 0.1, "hovering a case clip popped up a second preview"
    page.set_viewport_size({"width": 1280, "height": 360})  # short window: at the top, the gallery is off screen
    page.evaluate("scrollTo(0, 0)")
    assert wait_for(page, "document.querySelector('.case-video').getBoundingClientRect().top > innerHeight", timeout=5000), "could not move the clip off screen"
    assert wait_for(page, "document.querySelector('.case-video').paused", timeout=5000), "the clip keeps playing off screen"
    Site.close(page)

    page = site.open("/cases.html", reduced_motion=True)
    page.locator(".case-video").first.scroll_into_view_if_needed()
    page.wait_for_timeout(1500)
    assert page.evaluate("[...document.querySelectorAll('.case-video')].every(v => v.paused)"), "with reduced motion the clips must not autoplay"
    Site.close(page)


def main():
    httpd, base = serve()
    failed = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        site = Site(browser, base)
        only = set(sys.argv[1:])
        for fn in TESTS:
            if only and fn.__name__ not in only:
                continue
            started = time.monotonic()
            try:
                fn(site)
                print(f"  ok    {fn.__name__} ({time.monotonic() - started:.0f}s)", flush=True)
            except Exception as e:  # noqa: BLE001 - report every failure, keep going
                failed.append(fn.__name__)
                print(f"  FAIL  {fn.__name__} ({time.monotonic() - started:.0f}s): {e}", flush=True)
                if not isinstance(e, AssertionError):
                    traceback.print_exc()
        browser.close()
    httpd.shutdown()
    if failed:
        print(f"\n{len(failed)} test(s) failed: {', '.join(failed)}")
        sys.exit(1)
    print("\nall browser tests passed")


if __name__ == "__main__":
    main()
