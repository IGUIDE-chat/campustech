// Light-mode cursor trail: a few thin coloured ribbons drawn on a 2D canvas.
// The neon tubes rely on glow and metal reflections, which only read on a dark
// background, so light mode swaps them for this lighter treatment: same motion
// (follow the cursor, drift along an idle loop when it leaves), drawn as fine
// lines in the tubes' colours with no glow. Each ribbon is drawn glossy: a soft
// shadow beneath it for depth, a lighter sheen down its centre, and a crisp
// pure white highlight that sweeps along it like light catching satin.

const COLORS = ["#f967fb", "#6958d5", "#53bc28", "#ff008a", "#60aed5"]
const POINTS = 26 // points per ribbon; more = longer tail
const ENTER_RATE = 2.2 // cursor arrives: idle loop -> cursor
const LEAVE_RATE = 1.2 // cursor leaves: cursor -> idle loop
const TOUCH_RELEASE_MS = 1400
const SHEEN = 0.55 // how far the centre sheen is lightened towards white
const SHIMMER_SPEED = 5 // how fast the shine travels along the ribbon
const HIGHLIGHT_COLOR = "#ffffff" // pure white shine
const HIGHLIGHT_SPEED = 9 // how fast the highlight sweeps along the ribbon
const HIGHLIGHT_SHARPNESS = 14 // higher = shorter, crisper glints
const SHADOW = "rgba(45, 46, 54, 0.22)" // soft shadow under the ribbons (page ink)

/** Mix a #rrggbb colour towards white by `amount` (0..1). */
function lighten(hex, amount) {
  const n = parseInt(hex.slice(1), 16)
  const mix = (c) => Math.round(c + (255 - c) * amount)
  return `rgb(${mix(n >> 16)}, ${mix((n >> 8) & 255)}, ${mix(n & 255)})`
}

function ease(value, goal, rate, dt) {
  return value + (goal - value) * (1 - Math.exp(-rate * dt))
}

/** Start the ribbons on `canvas`. Returns { setActive(bool) }. Inactive = no drawing. */
export function startRibbons(canvas) {
  const ctx = canvas.getContext("2d")
  let width = 0
  let height = 0
  let active = false
  let raf = 0
  let last = 0
  let elapsed = 0

  let cursorX = 0
  let cursorY = 0
  let hasCursor = false
  let hovering = false
  let weight = 0
  let touchTimer = 0

  // Each ribbon chases the target with its own springiness, so they fan out
  // while the cursor moves and gather when it stops.
  const ribbons = COLORS.map((color, i) => ({
    color,
    sheen: lighten(color, SHEEN),
    phase: i * 1.3,
    stiffness: 70 + i * 22,
    damping: 11 + i * 1.5,
    lineWidth: i % 2 ? 3.2 : 4.6,
    offset: (i - (COLORS.length - 1) / 2) * 7,
    vx: 0,
    vy: 0,
    pts: [],
  }))

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    width = window.innerWidth
    height = window.innerHeight
    canvas.width = Math.round(width * dpr)
    canvas.height = Math.round(height * dpr)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  function reset(x, y) {
    for (const r of ribbons) {
      r.vx = 0
      r.vy = 0
      r.pts = Array.from({ length: POINTS }, () => ({ x, y }))
    }
  }

  function track(x, y, isTouch) {
    cursorX = x
    cursorY = y
    hasCursor = true
    hovering = true
    if (isTouch) {
      clearTimeout(touchTimer)
      touchTimer = setTimeout(() => (hovering = false), TOUCH_RELEASE_MS)
    }
  }

  window.addEventListener("pointermove", (e) => track(e.clientX, e.clientY, e.pointerType === "touch"), { passive: true })
  window.addEventListener("pointerdown", (e) => track(e.clientX, e.clientY, e.pointerType === "touch"), { passive: true })
  window.addEventListener(
    "touchmove",
    (e) => {
      const t = e.touches[0]
      if (t) track(t.clientX, t.clientY, true)
    },
    { passive: true },
  )
  document.documentElement.addEventListener("pointerleave", () => (hovering = false))
  document.addEventListener("pointerout", (e) => {
    if (!e.relatedTarget) hovering = false
  })
  window.addEventListener("blur", () => (hovering = false))
  window.addEventListener("resize", () => {
    resize()
    if (active) draw()
  })

  function frame(now) {
    const dt = last ? Math.min((now - last) / 1000, 0.05) : 1 / 60
    last = now
    elapsed += dt

    // Target: cursor while it is over the page, else the same idle loop as the
    // tubes (shrunk on narrow screens), crossfaded so it never jumps.
    weight = ease(weight, hovering && hasCursor ? 1 : 0, hovering ? ENTER_RATE : LEAVE_RATE, dt)
    const k = weight * weight * (3 - 2 * weight)
    const loopX = width / 2 + Math.min(300, width * 0.32) * Math.cos(elapsed)
    const loopY = height / 2 + Math.min(150, height * 0.2) * Math.sin(elapsed * 2)
    const tx = loopX + (cursorX - loopX) * k
    const ty = loopY + (cursorY - loopY) * k

    for (const r of ribbons) {
      const head = r.pts[0]
      // Damped spring towards the target (offset sideways so the lines sit apart).
      const ax = (tx + r.offset - head.x) * r.stiffness - r.vx * r.damping
      const ay = (ty + r.offset * 0.4 - head.y) * r.stiffness - r.vy * r.damping
      r.vx += ax * dt
      r.vy += ay * dt
      head.x += r.vx * dt
      head.y += r.vy * dt
      // Each point eases towards the one ahead: a soft trailing tail.
      for (let i = 1; i < r.pts.length; i++) {
        const p = r.pts[i]
        const q = r.pts[i - 1]
        p.x += (q.x - p.x) * 0.45
        p.y += (q.y - p.y) * 0.45
      }
    }

    draw()
    raf = active ? requestAnimationFrame(frame) : 0
  }

  function draw() {
    ctx.clearRect(0, 0, width, height)
    ctx.lineCap = "round"
    ctx.lineJoin = "round"
    // Shadow pass: one soft shadow per ribbon (cheap: five shadowed paths a frame).
    ctx.save()
    ctx.shadowColor = SHADOW
    ctx.shadowBlur = 8
    ctx.shadowOffsetY = 4
    ctx.globalAlpha = 0.35
    for (const r of ribbons) {
      const pts = r.pts
      ctx.lineWidth = r.lineWidth * 0.8
      ctx.strokeStyle = r.color
      ctx.beginPath()
      ctx.moveTo(pts[0].x, pts[0].y)
      for (let i = 1; i < pts.length - 1; i++) {
        ctx.quadraticCurveTo(pts[i].x, pts[i].y, (pts[i].x + pts[i + 1].x) / 2, (pts[i].y + pts[i + 1].y) / 2)
      }
      ctx.stroke()
    }
    ctx.restore()

    for (const r of ribbons) {
      const pts = r.pts
      // Taper: full width and opacity at the head, fading towards the tail.
      for (let i = 1; i < pts.length - 1; i++) {
        const t = 1 - i / (pts.length - 1)
        ctx.globalAlpha = 0.3 + 0.7 * t
        ctx.lineWidth = r.lineWidth * (0.45 + 0.55 * t)
        ctx.strokeStyle = r.color
        ctx.beginPath()
        const a = pts[i - 1]
        const b = pts[i]
        const c = pts[i + 1]
        ctx.moveTo((a.x + b.x) / 2, (a.y + b.y) / 2)
        ctx.quadraticCurveTo(b.x, b.y, (b.x + c.x) / 2, (b.y + c.y) / 2)
        ctx.stroke()
        // Gloss: a thinner, lighter strip down the centre of the same curve. Its
        // strength ripples along the ribbon over time, so the ribbon shimmers.
        const shimmer = 0.45 + 0.55 * Math.pow(0.5 + 0.5 * Math.sin(i * 0.55 - elapsed * SHIMMER_SPEED + r.phase), 3)
        const base = ctx.globalAlpha
        ctx.globalAlpha = base * shimmer
        ctx.lineWidth = r.lineWidth * (0.45 + 0.55 * t) * 0.38
        ctx.strokeStyle = r.sheen
        ctx.stroke()
        // Highlight: a crisp white glint travelling along the ribbon.
        const glint = Math.pow(0.5 + 0.5 * Math.sin(i * 0.42 - elapsed * HIGHLIGHT_SPEED + r.phase * 2), HIGHLIGHT_SHARPNESS)
        if (glint > 0.02) {
          ctx.globalAlpha = Math.min(1, glint * 1.6)
          ctx.lineWidth = r.lineWidth * (0.45 + 0.55 * t) * 0.34
          ctx.strokeStyle = HIGHLIGHT_COLOR
          ctx.stroke()
        }
      }
    }
    ctx.globalAlpha = 1
  }

  resize()
  reset(width / 2, height / 2)

  return {
    setActive(on) {
      if (on === active) return
      active = on
      if (on) {
        last = 0
        raf = requestAnimationFrame(frame)
      } else {
        cancelAnimationFrame(raf)
        raf = 0
      }
    },
  }
}
