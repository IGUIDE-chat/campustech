import { startDither } from "./dither.js"
import { startTubes } from "./tubes.js"

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
if (!reduceMotion && trailCanvas) {
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
  if (event.target.closest("a, #cord")) return
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
    smoothTouch: false, // phones keep their native momentum scrolling
  })

  // Each section's lines rise in as they come into view.
  gsap.utils.toArray(".sections section").forEach((section) => {
    gsap.from(section.children, {
      y: 40,
      opacity: 0,
      duration: 1,
      ease: "power3.out",
      stagger: 0.08,
      scrollTrigger: { trigger: section, start: "top 75%" },
    })
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
// Nav position, measured rather than set per breakpoint: centred on the page
// when the links fit there, otherwise shifted left just enough to clear the pull
// cord, and wrapped onto two rows only when they can't fit on one line at all.
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
  let left = (vw - w) / 2 // centred on the page
  if (left + w > maxRight) left = maxRight - w // shift clear of the cord
  left = Math.max(EDGE, left) // and never off the left edge (then it wraps)
  // When it has to wrap, rows start at the left edge (second row under the first).
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
  document.documentElement.classList.toggle("nav-scrolled", scrolled)
  // The mask only lines up with the nav when ScrollSmoother pins the content layer.
  document.documentElement.classList.toggle(
    "pinned",
    !!wrapper && getComputedStyle(wrapper).position === "fixed",
  )
}

function onScroll() {
  updateBackdrop()
  nav.classList.remove("show")
  clearTimeout(settleTimer)
  settleTimer = setTimeout(() => {
    highlight()
    nav.classList.add("show")
  }, SETTLE_MS)
}

window.addEventListener("scroll", onScroll, { passive: true })
highlight()
updateBackdrop()
nav.classList.add("show")

// ---- Link previews: hovering an outbound link shows a screenshot of the site ----
// Screenshots come from tools/previews/capture.py (most sites refuse iframes).

if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
  // Resolved from this script, so pages in sub folders (articles/) find it too.
  const siteRoot = new URL("../", import.meta.url)
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
    const src = link && manifest[link.href]
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
