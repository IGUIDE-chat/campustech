<p align="center">
  <a href="https://campustech.iguide.chat"><img alt="Live at campustech.iguide.chat" src="https://img.shields.io/badge/live-campustech.iguide.chat-E84A27.svg?style=for-the-badge&labelColor=000000" /></a>
  <a href="https://github.com/IGUIDE-chat/campustech/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/IGUIDE-chat/campustech/ci.yml?branch=main&style=for-the-badge&label=CI&labelColor=000000" /></a>
  <img alt="Cloudflare Pages" src="https://img.shields.io/badge/Cloudflare%20Pages-F38020.svg?style=for-the-badge&logo=cloudflarepages&logoColor=white&labelColor=000000" />
  <img alt="GSAP" src="https://img.shields.io/badge/GSAP%203.13-0AE448.svg?style=for-the-badge&logo=greensock&logoColor=white&labelColor=000000" />
  <img alt="No build step" src="https://img.shields.io/badge/build-none-555555.svg?style=for-the-badge&labelColor=000000" />
</p>

# Campus Tech

The landing page for **Campus Tech at UIUC**, a student organization at the
University of Illinois that builds products for campus life:
[campustech.iguide.chat](https://campustech.iguide.chat). Neon tubes follow the
cursor in dark mode, a pull cord switches to light mode, and every line of copy
animates in the direction you scroll.

Plain HTML, CSS and ES modules with no build step. Push to `main` and Cloudflare
Pages ships it in about 20 seconds.

## 🤖 Agents start here

This repo is set up for coding agents first. Read **[AGENTS.md](AGENTS.md)**
before you touch anything: rules, commands, the definition of done, and how
every effect works. `CLAUDE.md` points Claude Code there too.

The short version:

```bash
python tools/stamp_assets.py      # after any change in src/ or vendor/ (CSS/JS are cached 4h)
python tools/ci/check_static.py   # seconds, no browser
python tools/ci/test_site.py      # Playwright, desktop + phone, ~3 min
```

`main` is production, and every bug this site has had has a CI check. Fix a
bug, add its check in the same commit.

## Quick start

```bash
python -m http.server 5180        # then open http://localhost:5180
```

ES modules don't load from `file://`. Sub pages and articles live in
`tools/pages/build_pages.py`; edit there, then run it.

## How the page is made

| Piece | How |
| --- | --- |
| Smooth scroll | GSAP ScrollSmoother on desktop, with its content on its own GPU layer; phones scroll natively |
| Line animation | `ScrollTrigger.batch` per heading, paragraph and list item, in the scroll direction, with fail-safes so text is never left invisible |
| Dark mode | Tubes Cursor by Kevin Levron, eased on enter and leave (`src/tubes.js`) |
| Light mode | A dithered pixel trail; text under it turns white through two blend layers (`src/dither.js`) |
| Theme switch | A pull cord that switches on release, like a real one |
| Loading | A skeleton of the page, shown only on slow loads (`?loading` previews it) |
| SEO / GEO | One template for every page, JSON-LD, sitemap, `llms.txt` and `llms-full.txt` |

```js
// src/main.js
smoother = ScrollSmoother.create({
  wrapper: "#smooth-wrapper",
  content: "#smooth-content",
  smooth: 1.2, // seconds for the content to catch up with the native scroll
  effects: true,
  smoothTouch: false, // phones keep native momentum scrolling
})
```

## Repository layout

| Path | What lives there |
| --- | --- |
| [`index.html`](index.html) | The home page, hand-written |
| [`src/`](src) | `style.css`, `main.js`, `tubes.js`, `dither.js` |
| [`vendor/`](vendor) | GSAP, the original tubes file (byte-identical), the pull-cord bundle |
| [`tools/pages/`](tools/pages) | Generator for every sub page, article, the sitemap and llms files |
| [`tools/ci/`](tools/ci) | Static checks and Playwright browser tests |
| [`tools/images/`](tools/images) · [`tools/previews/`](tools/previews) | Logo, favicons and social card · link-preview screenshots |
| [`tools/pullcord/`](tools/pullcord) | Source of the pull-cord bundle |
| [`assets/`](assets) | Images, icons, previews |

## Deploy

Cloudflare Pages, project `campustech`, connected to this repo: every push to
`main` deploys with no build command. Production is
[campustech.iguide.chat](https://campustech.iguide.chat), with
[campustech.pages.dev](https://campustech.pages.dev) as the fallback. HTML is
always revalidated; CSS and JS carry content hashes. Details in
[AGENTS.md](AGENTS.md#deploy).

## Credits

- **Tubes Cursor** by Kevin Levron, CC BY-NC-SA 4.0: credited on every page,
  non-commercial use only.
- **pullcord** by Sarthak Navalekar, MIT, with motion (MIT).
- **GSAP 3.13** under the GreenSock standard no-charge licence.
- The dither trail is inspired by Eniyan Raja's DitherCursor; no code was
  copied.
