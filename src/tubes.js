// Neon tubes background, built on the TubesCursor component from
// threejs-components by Kevin Levron (https://codepen.io/soju22/pen/qEbdVjK,
// CC BY-NC-SA 4.0: credit the author, non-commercial use only).
//
// The stock component snaps its target between two sources: the cursor while
// the pointer is over the page, and an idle orbit otherwise. Leaving the window
// teleports the tubes onto the orbit, and coming back teleports them onto the
// cursor. Here the component's per-frame hook is replaced: the target is a
// smoothstep blend of orbit and cursor whose weight eases in and out, then the
// tubes follow that blend through an exponential filter, so there is no frame
// where the target jumps.

// Local copy of https://cdn.jsdelivr.net/npm/threejs-components@0.0.19/build/cursors/tubes1.min.js
// (byte-identical to the original page's vendor/tubes1.min.js).
// Not preloaded from <head>: a modulepreload holds back the load event, and with it the
// loading screen (+1.8s on a slow phone network) to show the tubes only ~0.5s sooner.
// The static haze (body::before) covers the wait instead.
const TUBES_URL = new URL("../vendor/tubes1.min.js", import.meta.url).href

/** Frames the tubes draw before the page calls them live (the bloom settles in). */
const READY_FRAMES = 3

/** Seconds-scale rates for the exponential easing (higher is faster). */
const ENTER_RATE = 2.2 // pointer arrives: orbit -> cursor
const LEAVE_RATE = 1.2 // pointer leaves: cursor -> orbit, slower so it drifts away
const FOLLOW_RATE = 9 // target chasing the blended point
const TOUCH_RELEASE_MS = 1400

// The original page's colours.
const COLORS = ["#f967fb", "#53bc28", "#6958d5"]
const LIGHT_COLORS = ["#83f36e", "#fe8a2e", "#ff008a", "#60aed5"]

// Per-theme rendering. Any bloom above 0 makes the canvas output opaque black,
// so light mode turns bloom off (transparent canvas over the white page). The
// stock tubes are fully metallic, which renders black wherever no light hits;
// light mode makes them matte and tints them with their own colour instead.
// With no bloom to light up the head, light mode moves the four coloured lights
// around the tubes' head instead, so the point under the cursor is the brightest
// part of the scene (a focus without any glow or halo on white).
const THEMES = {
  // The original effect's values: four fixed lights at the corners.
  dark: { bloom: 1.5, intensity: 200, metalness: 1, roughness: 0.25, glow: 0, followHead: false },
  // Calm on white: a colour floor so no edge turns black, lights close to the head.
  // (A flat, self-lit "glass" variant was tried and read as more plastic.)
  light: { bloom: 0, intensity: 30, metalness: 0.45, roughness: 0.32, glow: 0.32, followHead: true },
}
const HEAD_LIGHT_OFFSET = 1.4 // world units from the head, one light per corner
const HEAD_LIGHT_Z = 1.6

/** Approach `goal` from `value` at `rate` per second, frame-rate independent. */
function ease(value, goal, rate, dt) {
  return value + (goal - value) * (1 - Math.exp(-rate * dt))
}

/**
 * Start the tubes on `canvas`. Resolves to a controller, or rejects when the
 * component cannot load (missing file, no WebGL/WebGPU).
 */
export async function startTubes(canvas) {
  const { default: TubesCursor } = await import(/* @vite-ignore */ TUBES_URL)
  const app = TubesCursor(canvas, {
    tubes: { colors: COLORS, lights: { intensity: 200, colors: LIGHT_COLORS } },
  })
  const { three, tubes, options } = app
  const camera = three.camera
  const cornerLights = tubes.lights.map((light) => light.position.clone())
  let followHead = false

  // The bundle does not export three.js, so borrow its Vector3 from the camera.
  const ray = camera.position.clone()
  const cursor = camera.position.clone().set(0, 0, 0)
  const desired = cursor.clone()

  let hovering = false
  let hasCursor = false
  let weight = 0
  let lastElapsed = null
  let touchTimer = 0
  let drawn = 0
  let markReady
  const ready = new Promise((resolve) => (markReady = resolve))

  // Project the pointer onto the z = 0 plane the tubes live on.
  function setCursor(clientX, clientY) {
    const rect = canvas.getBoundingClientRect()
    // Hidden (light mode): no size to project onto, and dividing by 0 gives NaN.
    if (!rect.width || !rect.height) return
    const nx = ((clientX - rect.left) / rect.width) * 2 - 1
    const ny = -((clientY - rect.top) / rect.height) * 2 + 1
    camera.updateMatrixWorld()
    ray.set(nx, ny, 0.5).unproject(camera).sub(camera.position).normalize()
    if (Math.abs(ray.z) < 1e-6) return
    cursor.copy(camera.position).addScaledVector(ray, -camera.position.z / ray.z)
    hasCursor = true
  }

  function track(clientX, clientY, isTouch) {
    setCursor(clientX, clientY)
    hovering = true
    if (isTouch) {
      // Fingers have no hover: keep following briefly after lift, then drift back.
      clearTimeout(touchTimer)
      touchTimer = setTimeout(() => (hovering = false), TOUCH_RELEASE_MS)
    }
  }
  const onMove = (event) => track(event.clientX, event.clientY, event.pointerType === "touch")
  // Pointer events stop with pointercancel once a touch turns into a page scroll;
  // touch events keep firing during the scroll, so the tubes follow the finger.
  const onTouch = (event) => {
    const touch = event.touches[0]
    if (touch) track(touch.clientX, touch.clientY, true)
  }
  const onLeave = () => (hovering = false)
  const onOut = (event) => {
    if (!event.relatedTarget) hovering = false
  }

  window.addEventListener("pointermove", onMove, { passive: true })
  window.addEventListener("pointerdown", onMove, { passive: true })
  window.addEventListener("touchstart", onTouch, { passive: true })
  window.addEventListener("touchmove", onTouch, { passive: true })
  document.documentElement.addEventListener("pointerleave", onLeave)
  document.addEventListener("pointerout", onOut)
  window.addEventListener("blur", onLeave)

  three.onBeforeRender = (time) => {
    const elapsed = time.elapsed
    // Clamp so a backgrounded tab does not resume with one giant step.
    const dt = lastElapsed === null ? 0 : Math.min(Math.max(elapsed - lastElapsed, 0), 0.1)
    lastElapsed = elapsed

    const goal = hovering && hasCursor ? 1 : 0
    weight = ease(weight, goal, goal ? ENTER_RATE : LEAVE_RATE, dt)
    const k = weight * weight * (3 - 2 * weight)

    // While the canvas is hidden (light mode, display: none) the renderer sizes
    // itself to 0x0, and when it comes back it restarts a few frames before its
    // debounced resize. Skip those frames: dividing by a 0 width would put NaN
    // into the target, and the tubes never recover from a NaN position.
    const { width, height, wWidth } = three.size
    if (!width || !height || !wWidth) return
    const scale = wWidth / width
    const radiusX = Math.min(options.sleepRadiusX, width * 0.32) * scale
    const radiusY = Math.min(options.sleepRadiusY, height * 0.2) * scale
    const orbitX = radiusX * Math.cos(elapsed * options.sleepTimeScale1)
    const orbitY = radiusY * Math.sin(elapsed * options.sleepTimeScale2)
    desired.set(orbitX + (cursor.x - orbitX) * k, orbitY + (cursor.y - orbitY) * k, 0)

    if (dt === 0 || !Number.isFinite(tubes.target.x) || !Number.isFinite(tubes.target.y)) {
      tubes.target.copy(desired)
    } else {
      tubes.target.lerp(desired, 1 - Math.exp(-FOLLOW_RATE * dt))
    }
    tubes.update(time)
    // This hook runs before each render, so by call READY_FRAMES + 1 that many frames are on screen.
    if (++drawn === READY_FRAMES + 1) markReady()

    if (followHead) {
      tubes.lights.forEach((light, i) => {
        light.position.set(
          tubes.target.x + (i < 2 ? -HEAD_LIGHT_OFFSET : HEAD_LIGHT_OFFSET),
          tubes.target.y + (i % 2 === 0 ? -HEAD_LIGHT_OFFSET : HEAD_LIGHT_OFFSET),
          HEAD_LIGHT_Z,
        )
      })
    }
  }

  // `?debug` exposes internals for checking the motion from the console.
  if (new URLSearchParams(location.search).has("debug")) window.__tubes = { app, three, tubes }

  return {
    tubes,
    /** Resolves once the tubes have drawn a few real frames (never while the canvas is hidden). */
    ready,
    /**
     * Switch the rendering between the "dark" and "light" looks. Call again after
     * changing tube colours so the light-mode tint follows the new colours.
     */
    setTheme(theme) {
      const look = THEMES[theme] ?? THEMES.dark
      // Coming back from light mode the canvas was display: none and the renderer
      // sized itself to 0x0; measure again now instead of waiting for its
      // debounced resize, so the tubes reappear at full size straight away.
      if (theme !== "light" && !three.size.width) three.resize()
      if (app.bloomPass) app.bloomPass.strength.value = look.bloom
      tubes.setLightsIntensity(look.intensity)
      followHead = look.followHead
      if (!followHead) tubes.lights.forEach((light, i) => light.position.copy(cornerLights[i]))
      for (const tube of tubes.tubes) {
        const m = tube.material
        m.metalness = look.metalness
        m.roughness = look.roughness
        m.emissive.copy(m.color)
        m.emissiveIntensity = look.glow
      }
    },
    dispose() {
      clearTimeout(touchTimer)
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerdown", onMove)
      window.removeEventListener("touchstart", onTouch)
      window.removeEventListener("touchmove", onTouch)
      document.documentElement.removeEventListener("pointerleave", onLeave)
      document.removeEventListener("pointerout", onOut)
      window.removeEventListener("blur", onLeave)
      app.dispose()
    },
  }
}
