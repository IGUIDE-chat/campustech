"""Static regression checks: fast, no browser. Run: python tools/ci/check_static.py

Every check guards a bug this site has actually had (the commit or issue is
named in each check). Exits non-zero and lists every failure.
"""

import hashlib
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
SITE = "https://campustech.iguide.chat/"
PAGES = sorted(p for p in ROOT.rglob("*.html") if not {"tools", ".git", "node_modules"} & set(p.parts))
NOINDEX = {"404.html", "coming-soon.html"}
TEXT_FILES = [
    p
    for p in ROOT.rglob("*")
    if p.is_file()
    and not {".git", "node_modules"} & set(p.parts)
    and p.suffix in {".html", ".css", ".js", ".jsx", ".py", ".md", ".txt", ".xml", ".json", ".yml"}
    and "vendor" not in p.parts
]

failures = []


def fail(check, msg):
    failures.append(f"[{check}] {msg}")


def rel(p):
    return p.relative_to(ROOT).as_posix()


class Page(HTMLParser):
    """Collects what the checks need from one HTML file."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.meta = {}
        self.links = []  # (rel, href)
        self.refs = []  # every local href/src
        self.h1 = 0
        self.nav_links = []  # (href, class)
        self._in_nav = False
        self.ld = []
        self._in_ld = False
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = a.get("name") or a.get("property")
            if key:
                self.meta[key] = a.get("content", "")
        elif tag == "link":
            self.links.append((a.get("rel", ""), a.get("href", "")))
        elif tag == "h1":
            self.h1 += 1
        elif tag == "nav":
            self._in_nav = True
        elif tag == "a" and self._in_nav:
            self.nav_links.append((a.get("href", ""), a.get("class", "")))
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
            self.ld.append("")
        for attr in ("href", "src"):
            v = a.get(attr)
            if v and not urlparse(v).scheme and not v.startswith(("#", "mailto:", "//")):
                self.refs.append(v)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "nav":
            self._in_nav = False
        elif tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self.ld[-1] += data


# --- Generated files are up to date (any edit to build_pages.py or src/ must be
#     rebuilt and re-stamped before committing; stale output shipped twice).
before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
subprocess.run([sys.executable, str(ROOT / "tools" / "pages" / "build_pages.py")], cwd=ROOT, check=True, capture_output=True)
after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
if after != before:
    fail("generated-up-to-date", "running tools/pages/build_pages.py changed files; rebuild and commit:\n" + after)

parsed = {}
for p in PAGES:
    pg = Page()
    pg.feed(p.read_text(encoding="utf-8"))
    parsed[p] = pg

# --- 84a1f5c: Cloudflare caches CSS/JS for 4h, so every local CSS/JS URL must
#     carry the current content hash, or returning visitors get stale files.
def digest(path):
    # Line endings normalised: a Windows checkout (CRLF) and the Linux CI /
    # Cloudflare checkout (LF) must agree on the hash.
    return hashlib.sha1(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:10]


for p, pg in parsed.items():
    for ref in pg.refs:
        m = re.match(r"^(?:\./|/|(?:\.\./)+)?((?:src|vendor)/[\w.-]+\.(?:js|css))(\?v=([0-9a-f]+))?$", ref)
        if not m:
            continue
        if not m.group(3):
            fail("asset-version", f"{rel(p)}: {ref} has no ?v= hash")
        elif m.group(3) != digest(ROOT / m.group(1)):
            fail("asset-version", f"{rel(p)}: {ref} hash is stale (run tools/stamp_assets.py)")
main_js = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
for name, v in re.findall(r'from "\./([\w.-]+\.js)\?v=([0-9a-f]+)"', main_js):
    if v != digest(ROOT / "src" / name):
        fail("asset-version", f"src/main.js imports {name} with a stale hash")
if re.search(r'from "\./[\w.-]+\.js"', main_js):
    fail("asset-version", "src/main.js imports a module without ?v= hash")

# --- Every local href/src points at a file that exists.
for p, pg in parsed.items():
    for ref in pg.refs:
        path = urlparse(ref).path
        if not path:
            continue
        target = (ROOT / path.lstrip("/")) if path.startswith("/") else (p.parent / path)
        target = target.resolve()
        if path.endswith("/"):
            target = target / "index.html"
        if not target.exists() and not target.with_suffix(".html").exists():
            fail("broken-link", f"{rel(p)}: {ref} does not exist")

# --- cc0e583: sub pages marked Products/Join/Team/Contact as the current page.
#     In-page home links (#...) are never "active" on any page.
for p, pg in parsed.items():
    for href, cls in pg.nav_links:
        if "#" in href and "active" in cls.split():
            fail("nav-active", f"{rel(p)}: in-page link {href} is marked active")
    if sum("active" in c.split() for _, c in pg.nav_links) > 1:
        fail("nav-active", f"{rel(p)}: more than one nav link is marked active")

# --- SEO basics on every page (titles target "Campus Tech at UIUC"; 92fd9a6),
#     one h1, a description, and a clean canonical URL (5c3b927).
for p, pg in parsed.items():
    name = rel(p)
    if "Campus Tech at UIUC" not in pg.title:
        fail("seo-title", f"{name}: title {pg.title!r} lacks 'Campus Tech at UIUC'")
    if not pg.meta.get("description"):
        fail("seo-description", f"{name}: no meta description")
    if pg.h1 != 1:
        fail("seo-h1", f"{name}: {pg.h1} h1 elements (want 1)")
    canon = [h for r, h in pg.links if r == "canonical"]
    if name not in NOINDEX:
        if len(canon) != 1:
            fail("seo-canonical", f"{name}: {len(canon)} canonical links")
        elif canon[0].endswith(".html") or not canon[0].startswith(SITE):
            fail("seo-canonical", f"{name}: canonical {canon[0]} is not a clean {SITE} URL")
    robots = pg.meta.get("robots", "")
    if name in NOINDEX and "noindex" not in robots:
        fail("seo-noindex", f"{name}: should be noindex")
    if name not in NOINDEX and "noindex" in robots:
        fail("seo-noindex", f"{name}: is noindex but should be indexed")
    for block in pg.ld:
        try:
            json.loads(block)
        except json.JSONDecodeError as e:
            fail("json-ld", f"{name}: invalid JSON-LD ({e})")
    icons = [h for r, h in pg.links if r == "icon"]
    if not icons:
        fail("favicon", f"{name}: no favicon link")

# --- Search Console ownership tag must stay on the home page (removing it
#     un-verifies the site).
if "google-site-verification" not in parsed[ROOT / "index.html"].meta:
    fail("search-console", "index.html lost its google-site-verification meta tag")

# --- Sitemap, robots, llms: clean URLs only (5c3b927), noindex pages excluded.
sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
locs = re.findall(r"<loc>([^<]+)</loc>", sitemap)
if not locs:
    fail("sitemap", "sitemap.xml has no URLs")
for loc in locs:
    if loc.endswith(".html") or not loc.startswith(SITE):
        fail("sitemap", f"{loc} is not a clean {SITE} URL")
    if any(n.removesuffix(".html") in loc for n in NOINDEX):
        fail("sitemap", f"{loc} is noindex and must not be in the sitemap")
if f"Sitemap: {SITE}sitemap.xml" not in (ROOT / "robots.txt").read_text(encoding="utf-8"):
    fail("robots", "robots.txt does not point at the sitemap")
for llm in ("llms.txt", "llms-full.txt"):
    if re.search(r"campustech\.iguide\.chat/[\w/-]+\.html", (ROOT / llm).read_text(encoding="utf-8")):
        fail("llms", f"{llm} links a .html URL instead of the clean one")

# --- A stray backspace once ended up inside a regex (/[?&]loading\x08/): no
#     control characters in any text file.
for f in TEXT_FILES:
    text = f.read_text(encoding="utf-8", errors="replace")
    bad = re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text)
    if bad:
        line = text.count("\n", 0, bad.start()) + 1
        fail("control-char", f"{rel(f)}:{line} contains control character {bad.group()!r}")

# --- The loading-screen preview flag must be a real check (it once became
#     /[?&]loadingb/ and never matched).
for p in PAGES:
    t = p.read_text(encoding="utf-8")
    if 'id="loader"' in t and 'URLSearchParams(location.search).has("loading")' not in t:
        fail("loader", f"{rel(p)}: loading-screen preview check is missing or broken")
    if 'id="loader"' in t and "loader-dot" in t:
        fail("loader", f"{rel(p)}: three-dot loader is back (dcc0f9a: skeleton only)")

# --- A line starting with ( or [ glues onto the previous statement when that
#     one has no semicolon: `x = "manual"` + `(function () {...})()` became
#     "manual"(...) and broke the head script (theme, hero alignment).
for p in PAGES:
    for script in re.findall(r"<script>(.*?)</script>", p.read_text(encoding="utf-8"), re.S):
        code = [l.strip() for l in script.splitlines()]
        code = [l for l in code if l and not l.startswith("//")]
        for prev, line in zip(code, code[1:]):
            if line[0] in "([" and not prev.endswith((";", "{", "}", "(", ",", "[")):
                fail("asi", f"{rel(p)}: inline script line {line[:40]!r} follows {prev[-40:]!r} without a semicolon")

# --- No 100% black anywhere in the page colours (design rule; masks excepted,
#     where #000 only means "opaque").
for line_no, line in enumerate((ROOT / "src" / "style.css").read_text(encoding="utf-8").splitlines(), 1):
    if "mask" in line:
        continue
    if re.search(r"#000\b|#000000\b|rgb\(0,\s*0,\s*0\)|:\s*black\b", line, re.I):
        fail("no-pure-black", f"src/style.css:{line_no}: {line.strip()}")

# --- Credits and licences: the tubes are CC BY-NC-SA (credit required) and the
#     vendor file must stay byte-identical to the original effect.
for p in PAGES:
    if "Kevin Levron" not in p.read_text(encoding="utf-8"):
        fail("credit", f"{rel(p)}: missing the Kevin Levron credit")
TUBES_SHA256 = "676abd6ccd18742a36dcb4ffce66a2052a4f203f240cd8cf97c6ea33a181f81b"
if hashlib.sha256((ROOT / "vendor" / "tubes1.min.js").read_bytes().replace(b"\r\n", b"\n")).hexdigest() != TUBES_SHA256:
    fail("vendor-tubes", "vendor/tubes1.min.js is no longer the original file")

# --- Privacy: the officers' private emails must never be published. Only
#     hashes are stored here, so this file does not leak them either.
PRIVATE = {
    "6cc2c8d307bc6f91ed6cdd308cdd2f31c2d60140eca2e28adece04074bb3c4fb",
    "07d1f2fd12acc1856eb8dd79928d270b2bd6140c11ad2b3f05736a612a679281",
}
for f in TEXT_FILES:
    for email in set(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", f.read_text(encoding="utf-8", errors="replace"))):
        if hashlib.sha256(email.lower().encode()).hexdigest() in PRIVATE:
            fail("privacy", f"{rel(f)} contains a private email address")

# --- Hero markup: one h1 "Campus Tech" with TECH inside it, the tagline links
#     "products" to the Products section (6b7d68a), next-section links exist.
index = (ROOT / "index.html").read_text(encoding="utf-8")
if not re.search(r'<h1>Campus<span class="hero-sub">Tech</span></h1>', index):
    fail("hero", "hero h1 markup changed")
if 'We build <a href="#products">products</a> for campus life.' not in index:
    fail("hero", "tagline link to #products is missing")
for target in ("products", "join", "team", "contact"):
    if f'class="next" href="#{target}"' not in index:
        fail("next-links", f"next-section link to #{target} is missing")

if failures:
    print(f"{len(failures)} static check(s) failed:\n")
    print("\n".join(failures))
    sys.exit(1)
print(f"static checks passed ({len(PAGES)} pages, {len(TEXT_FILES)} text files)")
