# AGENTS.md

Instructions for coding agents (Claude Code, Codex, Cursor, Copilot) and for
humans who work like one. Read this before you change anything; the
[README](README.md) is the short tour.

## The repo in one paragraph

A static landing page for Campus Tech at UIUC, live at
<https://campustech.iguide.chat>. Plain HTML, CSS and ES modules with no build
step. Cloudflare Pages deploys every push to `main` in about 20 seconds, and
nothing gates the deploy, so **`main` is production**. Python scripts under
`tools/` generate the sub pages, stamp cache hashes, render images and run CI.

## Rules

1. **Every bug gets a CI check in the same commit.** Static checks go in
   `tools/ci/check_static.py`, browser checks in `tools/ci/test_site.py`.
   Name the bug in the check's docstring or message. Before you call a fix
   done, re-introduce the bug and confirm the check fails.
2. **Stamp assets after touching `src/` or `vendor/`.** Run
   `python tools/stamp_assets.py`. Cloudflare caches CSS and JS for 4 hours, so
   every local CSS/JS URL carries a content hash (`?v=...`). CI fails on a stale
   hash.
3. **Don't hand-edit generated files.** `cases.html`, `past.html`, `faq.html`,
   `privacy.html`, `terms.html`, `articles/*`, `404.html`, `coming-soon.html`,
   `sitemap.xml`, `llms.txt` and `llms-full.txt` come from
   `tools/pages/build_pages.py`. Edit the script, then run it; CI rebuilds and
   fails if the output differs from what you committed. `index.html` is
   hand-written.
4. **Keep the Search Console tag.** The `google-site-verification` meta in
   `index.html` keeps the property verified.
5. **Never publish personal email addresses.** CI checks hashes of known
   private addresses; don't add any personal contact details to the repo.
6. **Leave licensed code intact.** `vendor/tubes1.min.js` stays byte-identical
   (CI checks its sha256), and every page credits Kevin Levron (CC BY-NC-SA 4.0,
   so the site stays non-commercial).
7. **Inline scripts end statements with `;`.** A head-script line without one
   glued onto the next IIFE once and broke the theme and hero. CI checks this.
8. **No control characters, LF line endings.** Some agent shells turn `\b`,
   `\1` or `\n` inside heredocs into real control characters; use a file-edit
   tool for text with backslashes. CI scans every text file.
9. **No pure black** (`#000`) outside masks; the dark theme uses near-black.
10. **Ask before changing the look.** Colours, the light-mode trail, the pull
    cord's behaviour and the animation feel were tuned with the owner.

## Commands

| Task | Command |
| --- | --- |
| Serve locally | `python -m http.server 5180`, then open <http://localhost:5180> (ES modules don't load from `file://`) |
| Rebuild sub pages, sitemap, llms files and hashes | `python tools/pages/build_pages.py` |
| Re-stamp CSS/JS hashes only | `python tools/stamp_assets.py` |
| Static checks (no browser, seconds) | `python tools/ci/check_static.py` |
| Browser tests (Playwright, ~3 min) | `python tools/ci/test_site.py` |
| One browser test | `python tools/ci/test_site.py <test_name>` |
| Simulate a slow CPU | `SLOW=4 python tools/ci/test_site.py` |
| One CI shard (CI runs 3 in parallel) | `python tools/ci/test_site.py --shard 2/3` (`--list` to see its tests) |
| Would this change run the browser tests on CI? | `python tools/ci/changes.py HEAD~1` |
| Change CI Python packages | edit `tools/ci/requirements.in`, then the `uv pip compile` line at its top |
| Logo, favicons | `python tools/images/logo.py` |
| Link preview (`og.jpg`, from the real hero) | `python tools/images/og_capture.py`, then `python tools/images/og_capture.py <n>` to keep candidate n |
| Coming-soon cards | `python tools/images/render.py` |
| Link-preview screenshots | `python tools/previews/capture.py` (needs Chrome and Pillow) |
| Case screenshots and the Cases page preview | `python tools/previews/capture.py --cases` |
| Ping IndexNow (Bing, Yandex…) after a deploy is live | `python tools/seo/indexnow.py` (all sitemap URLs) or `python tools/seo/indexnow.py /cases /faq` |
| Rebuild the pull cord bundle | `cd tools/pullcord && npm install && npm run build` |
| Find placeholders | `grep -n "TODO(campustech)" index.html` |

Browser tests need `pip install -r tools/ci/requirements.txt` (the hashed lockfile)
and `python -m playwright install chromium`. Shards are balanced by
`tools/ci/test_times.json` (CI seconds per test; new tests count as 3s): refresh it
from a CI log when one shard runs much longer than the others.

CI has two kinds of check. Necessary: the static checks, on every push and pull
request. Conditional: the browser tests, only when a changed file can affect what
the browser loads; docs, `_headers`, SEO text files and generator scripts under
`tools/` (not `tools/ci/`) skip them. The rules are `SKIP` in `tools/ci/changes.py`;
anything not listed runs the tests, and `check_static.py` pins examples of both.

## Done means

1. `python tools/ci/check_static.py` passes.
2. `python tools/ci/test_site.py` passes. A single `ERR_CONNECTION_FAILED` on a
   Google Fonts request is network noise: rerun that test alone.
3. You looked at the change in a browser, desktop and phone width, dark and
   light theme, if it's visible.
4. After pushing, the GitHub Actions run is green (`gh run watch`).

## CI

`.github/workflows/ci.yml` runs both suites on every push and pull request, on
`ubuntu-24.04` (Playwright 1.58 can't install Chromium on 26.04) with a
40-minute timeout.

- The runner has no GPU, and the neon tubes in software WebGL starve the page.
  Browser tests block `vendor/tubes1.min.js` unless a test opts in with
  `tubes=True`.
- Wait with `wait_for(page, js)` (polls every 100 ms), not fixed sleeps; the
  runner is several times slower than a laptop.
- Scroll with `step_scroll`, which scrolls and observes inside the page, so
  timing checks don't depend on round trips.

## Files

| Path | What it is |
| --- | --- |
| `index.html` | Home page: hero, sections, nav, pull-cord mount, structured data (hand-written) |
| `src/style.css` | The original effect's CSS verbatim at the top, Campus Tech additions below |
| `src/main.js` | Smooth scroll, line animations, nav, hero toggle, link previews, theme |
| `src/tubes.js` | Starts the tubes and replaces their per-frame cursor logic |
| `src/dither.js` | Light-mode cursor trail (8x8 Bayer dither, three blend layers) |
| `src/ribbons.js` | Earlier light-mode trail, not loaded |
| `vendor/` | GSAP 3.13.0 (ScrollTrigger, ScrollSmoother), the original tubes file, the pull-cord bundle, licences |
| `tools/pages/build_pages.py` | Template and content for every sub page and article (`ARTICLES`) |
| `tools/stamp_assets.py` | Writes content hashes into CSS/JS URLs |
| `tools/ci/` | `check_static.py` and `test_site.py` |
| `tools/images/` | Logo, favicons, social card |
| `tools/previews/` | Link-preview screenshots plus `assets/previews/manifest.json` |
| `tools/pullcord/` | Source of the pull-cord bundle in `vendor/` |
| `assets/` | Images, icons, previews |

## How it works

- **Tubes.** The stock component jumps between the cursor and an idle orbit in
  one frame when the pointer leaves or re-enters the page; `tubes.js` crossfades
  and eases instead (`ENTER_RATE`, `LEAVE_RATE`, `FOLLOW_RATE`). On small
  screens the orbit shrinks and touch drives the tubes. The canvas parent
  (`.bg`) sits outside the scroll content, because ScrollSmoother's transform
  breaks `position: fixed` inside it.
- **Smooth scroll.** GSAP ScrollSmoother (`smooth: 1.2`) on desktop, with
  `will-change: transform` on `#smooth-content` so the GPU slides the page
  instead of Chrome re-rasterising it every frame. Phones scroll natively
  (smoothing on touch stuttered), and a page-coloured band goes behind the nav
  once the page scrolls (`.nav.under`).
- **Line animation.** Each heading, paragraph and list item animates on its own
  with `ScrollTrigger.batch`, in the scroll direction: up from below when
  scrolling down, down from above (bottom first) when scrolling up. A line hides
  again only once it is fully off screen, with an 80px buffer. Fail-safes: lines
  on screen are shown after every refresh, and an IntersectionObserver fades in
  anything still invisible after a second. Reading pages (articles, FAQ,
  privacy, terms) animate each line once.
- **Nav.** Centred on the title's axis when one row fits clear of the cord,
  otherwise centred in the space left of the cord, otherwise wrapped from the
  left. Hidden while scrolling, back half a second after scrolling stops. The
  fade mask on the page applies only while the nav shows (`html.nav-masked`).
- **Refresh.** `history.scrollRestoration = "manual"` in the head, and in-page
  links never write a hash, so a refresh starts at the top. A shared `#hash`
  still jumps there once, then is removed from the URL.
- **Hero.** Left-aligned by default; the icon at the bottom left of the first
  screen toggles centred (saved in `localStorage`). `?hero=left` or
  `?hero=center` overrides it for one visit.
- **Team.** One column on phones, 2 per row from 560px, 3 from 820px, 4 from
  1080px; the last row is centred.
- **Light mode.** The pull cord switches theme on release, never while held. On
  touch screens its grab area is wider and runs up the rope. Light mode swaps
  the tubes for the dither trail: the canvas draws under the page, then a white
  `difference` layer and a grey `color-dodge` layer above it turn the text under
  the trail white (grey copy included) while the trail keeps its colour. Idle
  frames are skipped and the overlays hidden. Touch-only devices skip the trail.
- **Loading screen.** A skeleton (grey blocks with a shimmer), shown only when
  loading takes longer than ~0.35 s. `?loading` keeps it on for previewing.
- **Fallbacks.** Without WebGL, or with reduced motion, a static gradient
  replaces the effect and smooth scroll is off. `?debug` exposes the tubes as
  `window.__tubes`.

## SEO

- Target query: "campus tech at uiuc". Every title contains "Campus Tech at
  UIUC"; the JSON-LD `alternateName` list carries the variants.
- Every page: unique title and description, clean canonical (no `.html`), Open
  Graph and Twitter tags, `assets/og.jpg`, one `h1`. 404 and coming-soon are
  `noindex`.
- Structured data: `Organization` and `WebSite` on the home page (with officers
  and products), `BreadcrumbList` on sub pages, `Article` on articles, `FAQPage`
  on the FAQ and recruiting article. Facts in the markup match the visible text.
- `robots.txt` allows all crawlers and names the AI ones explicitly (CI checks the main ones). `llms.txt` is
  a plain summary and `llms-full.txt` the full text of every indexed page.
- Cases has `CollectionPage`/`ItemList` markup; the sitemap lists images; `articles/feed.xml` (Atom) is linked from every page; the FAQ, `llms.txt` and the Organization's `disambiguatingDescription` say we are not UIUC Technology Services. IndexNow key: the hex-named `.txt` at the root.
- Google Search Console owns the property `https://campustech.iguide.chat/`
  (meta-tag verified) with the sitemap submitted.

## Deploy

- Cloudflare Pages project `campustech` (account techadmin@iguide.chat),
  connected to this repo. No build command; the output directory is the repo
  root.
- Production: <https://campustech.iguide.chat> (proxied CNAME to
  `campustech.pages.dev`). Fallback: <https://campustech.pages.dev>.
- Pages serves extensionless URLs (`/faq.html` redirects to `/faq`), so
  canonicals, the sitemap and llms files use that form. `404.html` serves
  unknown paths.
- HTML is always revalidated; CSS and JS are cached 4 hours, hence rule 2.

## Credits and licences

- Tubes Cursor by Kevin Levron, CC BY-NC-SA 4.0: credit required on every page,
  non-commercial only.
- pullcord 0.1.0 by Sarthak Navalekar (mortspace), MIT, with motion (MIT):
  `vendor/LICENSE-pullcord.txt`, `vendor/LICENSE-motion.txt`.
- GSAP 3.13.0 under the GreenSock standard no-charge licence
  (<https://gsap.com/standard-license>).
- The dither trail is an independent implementation inspired by "DitherCursor"
  by Eniyan Raja; no code was copied.
