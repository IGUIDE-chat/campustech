import { startDither } from "./dither.js?v=1854ce10a1"
import { startTubes } from "./tubes.js?v=aec2ea1b7f"

// ---- Background (original script.js, with the smoothed cursor from tubes.js) ----

const canvas = document.getElementById("canvas")
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches

// Light mode draws a dithered pixel trail instead of the neon tubes (the tubes'
// glow and metal only read on dark). CSS hides the tubes' layer in light mode,
// which also pauses its renderer (it stops when its canvas leaves the screen).
const isLight = () => document.documentElement.dataset.theme === "light"
const trailCanvas = document.getElementById("trail")
let trail = null
let tubesApp = null
// The trail follows a mouse or pen only, so touch-only phones skip it (two
// full-screen layers they would composite on every scroll for nothing).
const canHover = window.matchMedia("(hover: hover)").matches
if (!reduceMotion && trailCanvas && canHover) {
  trail = startDither(trailCanvas)
  const sync = () => trail.setActive(isLight())
  sync()
  new MutationObserver(sync).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  })
}

// As in the original effect: a click picks new colours. In light mode it recolours
// the dither trail, in dark mode the tubes. Links and the pull cord keep their own
// behaviour.
document.body.addEventListener("click", (event) => {
  if (event.target.closest("a, #cord, #hero-align")) return
  if (isLight()) {
    trail?.setColor(randomInk())
  } else if (tubesApp) {
    tubesApp.tubes.setColors(randomColors(3))
    tubesApp.tubes.setLightsColors(randomColors(4))
    tubesApp.setTheme("dark")
  }
})

/** A random saturated colour that reads well on white. */
function randomInk() {
  const h = Math.random() * 360
  const s = 0.7
  const l = 0.48
  const f = (n) => {
    const k = (n + h / 30) % 12
    const c = l - s * Math.min(l, 1 - l) * Math.max(-1, Math.min(k - 3, 9 - k, 1))
    return Math.round(c * 255).toString(16).padStart(2, "0")
  }
  return `#${f(0)}${f(8)}${f(4)}`
}

if (reduceMotion || !canvas) {
  document.body.classList.add("no-tubes")
} else {
  startTubes(canvas)
    .then((app) => {
      // Follow the light/dark theme set by the pull cord. The background fades out
      // for the swap so the bloom change never shows as a flash.
      const bg = document.querySelector(".bg")
      let swapTimer = 0
      const applyTheme = (animate) => {
        const theme = document.documentElement.dataset.theme
        if (!animate) return app.setTheme(theme)
        bg.style.opacity = "0"
        clearTimeout(swapTimer)
        swapTimer = setTimeout(() => {
          app.setTheme(theme)
          bg.style.opacity = ""
        }, 250)
      }
      applyTheme(false)
      new MutationObserver(() => applyTheme(true)).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-theme"],
      })

      tubesApp = app
    })
    .catch((error) => {
      console.warn("Tubes background unavailable, using the static fallback.", error)
      document.body.classList.add("no-tubes")
    })
}

function randomColors(count) {
  return new Array(count)
    .fill(0)
    .map(() => "#" + Math.floor(Math.random() * 16777215).toString(16).padStart(6, "0"))
}

// ---- Smooth scrolling (GSAP ScrollSmoother) ----

const { gsap, ScrollTrigger, ScrollSmoother } = window
let smoother = null

if (gsap && ScrollTrigger && ScrollSmoother && !reduceMotion) {
  gsap.registerPlugin(ScrollTrigger, ScrollSmoother)
  smoother = ScrollSmoother.create({
    wrapper: "#smooth-wrapper",
    content: "#smooth-content",
    smooth: 1.2, // seconds for the content to catch up with the native scroll
    effects: true,
    // Phones keep native momentum scrolling: smoothing on touch made scrolling
    // stutter. Without it nothing masks content under the nav, so a band in the
    // page colour goes behind the links once the page scrolls (.nav.under).
    smoothTouch: false,
  })

  // Every line (heading, paragraph, list item) animates on its own as it enters
  // or leaves the screen, in the scroll direction, so the motion is always seen
  // where it happens, also on tall phone sections and when scrolling back up.
  // Scrolling down: lines rise in from below, top first. Scrolling up: lines drop
  // in from above, bottom first. A line only fades out once it is nearly off
  // screen. Lines that arrive together are batched into one staggered cascade.
  // Phones resize the page when the address bar shows or hides; re-measuring on
  // every one of those could leave a line hidden mid-scroll.
  ScrollTrigger.config({ ignoreMobileResize: true })
  const linesOf = (section) =>
    [...section.children]
      .filter((el) => !el.matches(".next"))
      .flatMap((el) => (el.tagName === "UL" ? [...el.children] : [el]))
  const sections = gsap.utils.toArray(".sections section")
  // Reading pages (articles, FAQ, privacy, terms: .prose) animate each line once,
  // the first time it comes into view; after that the text simply stays put.
  const isProse = (el) => !!el.closest(".prose")
  const lines = sections.flatMap(linesOf)
  const repeatLines = lines.filter((el) => !isProse(el))
  const onScreen = (el) => {
    const r = el.getBoundingClientRect()
    return r.bottom > 0 && r.top < window.innerHeight
  }
  const invisible = (el) => Number(getComputedStyle(el).opacity) < 0.5
  gsap.set(lines, { opacity: 0, y: 40 })
  // Lines currently hidden (waiting to animate in). Only these animate in, so a
  // line that is already visible never replays on a small scroll reversal.
  const hidden = new Set(lines)
  const show = (els, fromY, from) => {
    const todo = els.filter((el) => hidden.has(el))
    todo.forEach((el) => hidden.delete(el))
    if (todo.length)
      gsap.fromTo(
        todo,
        { opacity: 0, y: fromY },
        { opacity: 1, y: 0, duration: 0.8, ease: "power3.out", stagger: { each: 0.08, from }, overwrite: true },
      )
  }
  // A line is hidden again only once it is completely off screen (instantly; no
  // one sees it), ready to animate in the next time it comes into view.
  const hide = (els, y) => {
    els.forEach((el) => hidden.add(el))
    gsap.set(els, { opacity: 0, y, overwrite: true })
  }
  // Entering: as soon as a line is 8% into the screen, in either direction.
  ScrollTrigger.batch(lines, {
    start: "top 92%",
    end: "bottom 8%",
    interval: 0.1,
    onEnter: (els) => show(els, 40, "start"),
    onEnterBack: (els) => show(els, -40, "end"),
  })
  // Leaving: only once fully off screen. Reading pages (.prose) keep their text.
  if (repeatLines.length)
    ScrollTrigger.batch(repeatLines, {
      start: "top bottom",
      end: "bottom top",
      onLeave: (els) => hide(els, -40),
      onLeaveBack: (els) => hide(els, 40),
    })
  // Fail-safe: after any re-measure, lines on screen are shown.
  ScrollTrigger.addEventListener("refresh", () => {
    const stuck = lines.filter((el) => onScreen(el) && invisible(el))
    stuck.forEach((el) => hidden.delete(el))
    if (stuck.length) gsap.set(stuck, { opacity: 1, y: 0, overwrite: true })
  })
  // Second safety net, independent of ScrollTrigger: if a section is on screen
  // and some of its lines on screen are still invisible a second later (a missed
  // trigger on some phone browser), fade them in. Text must never stay hidden.
  sections.forEach((section) => {
    const own = linesOf(section)
    let check = 0
    new IntersectionObserver(
      ([entry]) => {
        clearTimeout(check)
        if (!entry.isIntersecting) return
        check = setTimeout(() => {
          const stuck = own.filter((el) => onScreen(el) && invisible(el))
          stuck.forEach((el) => hidden.delete(el))
          if (stuck.length) gsap.to(stuck, { opacity: 1, y: 0, duration: 0.4, overwrite: true })
        }, 1000)
      },
      { threshold: [0, 0.25, 0.5, 0.75, 1] },
    ).observe(section)
  })
}

/** Scroll to an in-page target, through the smoother when it is running. */
function scrollToTarget(target, animate = true) {
  if (smoother) smoother.scrollTo(target, animate, "top top")
  else target.scrollIntoView({ behavior: animate && !reduceMotion ? "smooth" : "auto" })
}

document.addEventListener("click", (event) => {
  const link = event.target.closest('a[href^="#"]')
  const target = link && document.querySelector(link.getAttribute("href"))
  if (!target) return
  event.preventDefault()
  scrollToTarget(target)
  history.replaceState(null, "", link.getAttribute("href"))
})

// A shared link like /#join lands on that section.
const initial = location.hash && document.querySelector(location.hash)
if (initial) requestAnimationFrame(() => scrollToTarget(initial, false))

// ---- Nav: shown while the page is still, fades out while scrolling ----

const nav = document.querySelector(".nav")
// Only in-page links take part in the active-section highlight; links to other
// pages (./, ./past.html) keep whatever class the markup gives them.
const links = [...document.querySelectorAll('.nav-links a[href^="#"]')]
const sections = links.map((link) => document.querySelector(link.getAttribute("href")))
const SETTLE_MS = 500 // how long scrolling must pause before the nav comes back
let settleTimer = 0

/** Page offset of an element, unaffected by ScrollSmoother's transform. */
function pageTop(el) {
  let top = 0
  for (let node = el; node; node = node.offsetParent) top += node.offsetTop
  return top
}

function highlight() {
  const mid = window.scrollY + window.innerHeight / 2
  sections.forEach((section, i) => {
    const top = pageTop(section)
    links[i].classList.toggle("active", mid >= top && mid < top + section.offsetHeight)
  })
}

// Backdrop behind the nav once the first screen has scrolled away (sub pages
// have no hero, so they always get it).
const hasHero = !!document.querySelector(".hero")
const wrapper = document.getElementById("smooth-wrapper")
// Nav position, measured rather than set per breakpoint: on one line it is
// centred in the free space left of the pull cord; when it can't fit on one line
// it wraps, with both rows starting at the left edge.
const navLinks = nav.querySelector(".nav-links")
const EDGE = 16 // min gap to the left edge of the screen
const CORD_GAP = 24 // min gap between the last link and the cord
function layoutNav() {
  const root = document.documentElement
  const vw = root.clientWidth
  const cordBox = document.querySelector("#cord > *")?.getBoundingClientRect()
  const cordX = cordBox && cordBox.width ? cordBox.left + cordBox.width / 2 : vw
  // Natural one-line width of the links.
  navLinks.style.flexWrap = "nowrap"
  navLinks.style.width = "max-content"
  const w = Math.ceil(navLinks.getBoundingClientRect().width) + 2 // + slack for sub-pixel rounding
  navLinks.style.flexWrap = ""
  navLinks.style.width = ""
  const maxRight = cordX - CORD_GAP // the links must end before this
  // One row, room to spare: centred on the page, on the same axis as the title.
  // One row, but centring would run into the cord: centred in the free space
  // between the left edge and the cord. Two rows: start at the left edge.
  const hero = document.querySelector(".hero-text")?.getBoundingClientRect()
  const axis = hero && hero.width ? hero.left + hero.width / 2 : vw / 2
  const free = maxRight - EDGE
  const left =
    axis + w / 2 <= maxRight && axis - w / 2 >= EDGE
      ? axis - w / 2
      : w <= free
        ? EDGE + (free - w) / 2
        : EDGE
  root.style.setProperty("--nav-left", `${Math.round(left)}px`)
  root.style.setProperty("--nav-right", `${Math.max(EDGE, Math.round(vw - maxRight))}px`)
  // Keep the content fade under the nav as tall as the nav.
  root.style.setProperty("--nav-h", `${nav.offsetHeight}px`)
}
window.addEventListener("resize", layoutNav)
document.fonts?.ready.then(layoutNav)
// The cord mounts a moment after load (React); lay out again once it is there.
new MutationObserver(layoutNav).observe(document.getElementById("cord") || document.body, { childList: true })
layoutNav()
function updateBackdrop() {
  const scrolled = !hasHero || window.scrollY > window.innerHeight * 0.5
  nav.classList.toggle("scrolled", scrolled)
  nav.classList.toggle("under", window.scrollY > 4) // content can now sit under the nav
  document.documentElement.classList.toggle("nav-scrolled", scrolled)
  // The mask only lines up with the nav when ScrollSmoother pins the content layer.
  document.documentElement.classList.toggle(
    "pinned",
    !!wrapper && getComputedStyle(wrapper).position === "fixed",
  )
}

/** Show or hide the nav; the content mask under it follows (html.nav-shown). */
function setNavShown(shown) {
  nav.classList.toggle("show", shown)
  document.documentElement.classList.toggle("nav-shown", shown)
}

function onScroll() {
  updateBackdrop()
  setNavShown(false)
  clearTimeout(settleTimer)
  settleTimer = setTimeout(() => {
    highlight()
    setNavShown(true)
  }, SETTLE_MS)
}

window.addEventListener("scroll", onScroll, { passive: true })
highlight()
updateBackdrop()
setNavShown(true)

// ---- Link previews: hovering an outbound link shows a screenshot of the site ----
// Screenshots come from tools/previews/capture.py (most sites refuse iframes).

const siteRoot = new URL("../", import.meta.url)
if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
  // Resolved from this script, so pages in sub folders (articles/) find it too.
  fetch(new URL("assets/previews/manifest.json", siteRoot))
    .then((response) => (response.ok ? response.json() : {}))
    .then((manifest) => {
      for (const url in manifest) manifest[url] = new URL(manifest[url], siteRoot).href
      setUpPreviews(manifest)
    })
    .catch(() => {})
}

function setUpPreviews(manifest) {
  const card = document.createElement("div")
  card.className = "preview"
  card.setAttribute("aria-hidden", "true")
  const img = document.createElement("img")
  img.alt = ""
  img.decoding = "async"
  card.append(img)
  document.body.append(card)

  const GAP = 12 // px between the link text and the preview
  let active = null

  /** Centre the preview on the link text: above it, or below when there is no room. */
  function place(link) {
    const r = link.getBoundingClientRect()
    const w = card.offsetWidth
    const h = card.offsetHeight
    let x = r.left + r.width / 2 - w / 2
    let y = r.top - GAP - h
    if (y < 8) y = r.bottom + GAP
    x = Math.min(Math.max(8, x), window.innerWidth - w - 8)
    card.style.transform = `translate3d(${x}px, ${y}px, 0)`
  }

  document.addEventListener("pointerover", (event) => {
    const link = event.target.closest("a[href]")
    // data-preview (e.g. the coming-soon cards) wins over the screenshot manifest.
    const src = link && (link.dataset.preview ? new URL(link.dataset.preview, siteRoot).href : manifest[link.href])
    if (!src || link === active) return
    active = link
    img.src = src
    place(link)
    card.classList.add("show")
  })

  document.addEventListener("pointerout", (event) => {
    if (!active || active.contains(event.relatedTarget)) return
    if (event.target.closest("a[href]") !== active) return
    active = null
    card.classList.remove("show")
  })

  // Scrolling or leaving the window should never leave a stale preview behind.
  const hide = () => {
    active = null
    card.classList.remove("show")
  }
  window.addEventListener("scroll", hide, { passive: true })
  window.addEventListener("blur", hide)
}

// Hero alignment toggle: centred <-> left, remembered across visits.
const heroAlign = document.getElementById("hero-align")
if (heroAlign) {
  const root = document.documentElement
  const label = () =>
    heroAlign.setAttribute("aria-label", root.classList.contains("hero-left") ? "Centre title" : "Align title left")
  label()
  heroAlign.addEventListener("click", (e) => {
    e.stopPropagation() // not a background click: keep the trail colour
    const left = root.classList.toggle("hero-left")
    try {
      localStorage.setItem("campustech-hero", left ? "left" : "center")
    } catch (err) {}
    label()
  })
}
