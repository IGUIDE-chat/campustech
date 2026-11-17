// Light-mode cursor trail: a dithered pixel trail.
//
// Inspired by "DitherCursor" by Eniyan Raja (x.com/_eniyanrajaa_), a Framer
// component. That component's code carries no licence, so this is an
// independent implementation of the same idea using the standard technique:
// a soft trail field behind the cursor, turned into crisp single-colour dots
// with an 8x8 ordered (Bayer) dither. Dense at the head, breaking into specks
// at the edges; when the pointer rests the trail freezes and drops out dot by dot.
//
// Text the trail passes under flips to a light colour so it stays readable. Two
// layers draw the same dots: this canvas behind the page, in the complement of
// the trail colour, and a second one on top of the page in white with
// mix-blend-mode: difference. On the page background the two cancel out to the
// trail colour itself; on text the top layer inverts the dark ink to light.

const START_COLOR = "#6958d5" // the purple from the tubes' palette; a click picks a new colour
const DOT = 3 // CSS px per dot; every dot is a crisp square
const POINTS = 20 // links in the chain behind the cursor
const FOLLOW = 0.28 // how tightly each link follows the one ahead (lower = longer tail)
const HEAD_RATE = 22 // how fast the head catches the pointer (per second)
const RADIUS = 70 // CSS px half-width of the trail at the head
const TAPER = 0.6 // how much narrower the tail end is (0..1)
const TAIL_FADE = 0.75 // how much weaker the tail end is (0..1)
const RISE = 9 // energy rise per second while moving
const FADE = 0.9 // seconds for the trail to dissolve after the pointer rests

// 8x8 Bayer matrix as thresholds in (0, 1).
const BAYER = Float32Array.from(
  [
    0, 32, 8, 40, 2, 34, 10, 42, 48, 16, 56, 24, 50, 18, 58, 26, 12, 44, 4, 36, 14, 46, 6, 38, 60,
    28, 52, 20, 62, 30, 54, 22, 3, 35, 11, 43, 1, 33, 9, 41, 51, 19, 59, 27, 49, 17, 57, 25, 15, 47,
    7, 39, 13, 45, 5, 37, 63, 31, 55, 23, 61, 29, 53, 21,
  ],
  (v) => (v + 0.5) / 64,
)

/** Parse #rrggbb into a packed little-endian RGBA pixel (as ImageData stores it). */
function packColor(hex) {
  const n = parseInt(hex.slice(1), 16)
  return ((255 << 24) | ((n & 255) << 16) | (((n >> 8) & 255) << 8) | (n >> 16)) >>> 0
}

/** The complement (white minus the colour) of #rrggbb, packed: see the note above. */
function packComplement(hex) {
  const n = 0xffffff - parseInt(hex.slice(1), 16)
  return packColor("#" + n.toString(16).padStart(6, "0"))
}

/** Start the dither trail on `canvas`. Returns { setActive(bool), setColor(hex) }. */
export function startDither(canvas) {
  const ctx = canvas.getContext("2d")
  // The inverting layer sits on top of the page (outside the scroll content).
  const flip = document.createElement("canvas")
  flip.className = "trail trail-flip"
  flip.setAttribute("aria-hidden", "true")
  document.body.appendChild(flip)
  const fctx = flip.getContext("2d")
  const grid = document.createElement("canvas") // one pixel per dot, scaled up crisply
  const gctx = grid.getContext("2d")
  let cols = 0
  let rows = 0
  let image = null
  let pixels = null // Uint32 view of `image`
  let ink = packComplement(START_COLOR)

  const chain = Array.from({ length: POINTS }, () => ({ x: 0, y: 0 }))
  let pointerX = 0
  let pointerY = 0
  let seen = false
  let lastMove = -1
  let energy = 0
  let active = false
  let raf = 0
  let last = 0

  function resize() {
    const w = window.innerWidth
    const h = window.innerHeight
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    for (const c of [canvas, flip]) {
      c.width = Math.round(w * dpr)
      c.height = Math.round(h * dpr)
      c.style.width = `${w}px`
      c.style.height = `${h}px`
    }
    cols = Math.ceil(w / DOT)
    rows = Math.ceil(h / DOT)
    grid.width = cols
    grid.height = rows
    image = gctx.createImageData(cols, rows)
    pixels = new Uint32Array(image.data.buffer)
  }

  // Mouse, trackpad and pen only: on touch screens a finger scrolls the page.
  window.addEventListener(
    "pointermove",
    (e) => {
      if (e.pointerType === "touch") return
      pointerX = e.clientX
      pointerY = e.clientY
      if (!seen) {
        // Start the whole chain at the pointer so it doesn't sweep in from 0,0.
        for (const p of chain) {
          p.x = pointerX
          p.y = pointerY
        }
        seen = true
      }
      lastMove = performance.now()
    },
    { passive: true },
  )
  window.addEventListener("resize", resize)

  function frame(now) {
    // A frame already queued when light mode turned off must not draw again.
    if (!active) return
    const dt = last ? Math.min((now - last) / 1000, 0.05) : 1 / 60
    last = now
    const moving = seen && now - lastMove < 80

    // Energy rises fast while moving and falls over FADE seconds at rest, so dots
    // drop out one by one (the dither thresholds) rather than the trail going see-through.
    energy = moving ? Math.min(1, energy + RISE * dt) : Math.max(0, energy - dt / FADE)

    // While moving: the head eases to the pointer and each link chases the one ahead.
    // At rest the chain freezes, so the trail dissolves where it was drawn.
    if (moving) {
      const head = chain[0]
      const k = 1 - Math.exp(-HEAD_RATE * dt)
      head.x += (pointerX - head.x) * k
      head.y += (pointerY - head.y) * k
      for (let i = 1; i < POINTS; i++) {
        chain[i].x += (chain[i - 1].x - chain[i].x) * FOLLOW
        chain[i].y += (chain[i - 1].y - chain[i].y) * FOLLOW
      }
    }

    render()
    raf = active ? requestAnimationFrame(frame) : 0
  }

  function render() {
    pixels.fill(0)
    if (energy > 0.001) {
      // Only work inside the trail's bounding box (in dot units).
      let minX = Infinity
      let minY = Infinity
      let maxX = -Infinity
      let maxY = -Infinity
      for (const p of chain) {
        minX = Math.min(minX, p.x)
        maxX = Math.max(maxX, p.x)
        minY = Math.min(minY, p.y)
        maxY = Math.max(maxY, p.y)
      }
      const x0 = Math.max(0, Math.floor((minX - RADIUS) / DOT))
      const x1 = Math.min(cols - 1, Math.ceil((maxX + RADIUS) / DOT))
      const y0 = Math.max(0, Math.floor((minY - RADIUS) / DOT))
      const y1 = Math.min(rows - 1, Math.ceil((maxY + RADIUS) / DOT))

      for (let gy = y0; gy <= y1; gy++) {
        const py = (gy + 0.5) * DOT
        for (let gx = x0; gx <= x1; gx++) {
          const px = (gx + 0.5) * DOT
          // Field: each link is a capsule with a soft edge, narrower and weaker toward the tail.
          let field = 0
          for (let i = 0; i < POINTS - 1; i++) {
            const a = chain[i]
            const b = chain[i + 1]
            const abx = b.x - a.x
            const aby = b.y - a.y
            const len2 = abx * abx + aby * aby || 1e-6
            let t = ((px - a.x) * abx + (py - a.y) * aby) / len2
            t = t < 0 ? 0 : t > 1 ? 1 : t
            const dx = px - (a.x + abx * t)
            const dy = py - (a.y + aby * t)
            const along = (i + t) / (POINTS - 1)
            const r = RADIUS * (1 - TAPER * along)
            const d = Math.sqrt(dx * dx + dy * dy) / r
            if (d >= 1) continue
            // Dense, fairly flat core that thins out to single specks at the edge.
            const soft = 1 - d * d
            const v = soft * soft * (1 - TAIL_FADE * along)
            if (v > field) field = v
          }
          field *= energy * 1.15
          if (field > BAYER[(gx & 7) + ((gy & 7) << 3)]) pixels[gx + gy * cols] = ink
        }
      }
    }
    gctx.putImageData(image, 0, 0)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.imageSmoothingEnabled = false // scale up without smoothing: crisp square dots
    const dw = cols * DOT * (canvas.width / window.innerWidth)
    const dh = rows * DOT * (canvas.height / window.innerHeight)
    ctx.drawImage(grid, 0, 0, dw, dh)
    // Same dots in white on the inverting layer.
    fctx.globalCompositeOperation = "source-over"
    fctx.clearRect(0, 0, flip.width, flip.height)
    fctx.imageSmoothingEnabled = false
    fctx.drawImage(grid, 0, 0, dw, dh)
    fctx.globalCompositeOperation = "source-in"
    fctx.fillStyle = "#fff"
    fctx.fillRect(0, 0, flip.width, flip.height)
  }

  resize()

  return {
    setActive(on) {
      if (on === active) return
      active = on
      if (on) {
        // Fresh start every time light mode turns on: no leftover trail, and the
        // chain re-seeds at the pointer on the next move instead of sweeping in
        // from wherever it was when the theme last changed.
        energy = 0
        seen = false
        last = 0
        resize()
        raf = requestAnimationFrame(frame)
      } else {
        cancelAnimationFrame(raf)
        raf = 0
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        fctx.clearRect(0, 0, flip.width, flip.height)
      }
    },
    setColor(hex) {
      ink = packComplement(hex)
    },
  }
}
