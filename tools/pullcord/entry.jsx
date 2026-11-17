// Light-mode pull cord: pullcord 0.1.0 (MIT, Sarthak Navalekar / mortspace)
// https://www.npmjs.com/package/pullcord · https://github.com/mortspace/pullcord
// Same wiring as web-effects/pullcord/src/main.jsx, without the demo panel.
// Rebuild with `npm install && npm run build`; output goes to ../../vendor/.
import { useEffect, useState } from "react"
import { createRoot } from "react-dom/client"
// Local copy of the component: clicks animate a real pull (see PullCord.js).
import { PullCord } from "./PullCord.js"
import "pullcord/pullcord.css"

const KEY = "campustech-theme"

function readTheme() {
  try {
    return localStorage.getItem(KEY) === "light" ? "light" : "dark"
  } catch {
    return "dark"
  }
}

function Cord() {
  const [dark, setDark] = useState(() => readTheme() === "dark")

  useEffect(() => {
    const theme = dark ? "dark" : "light"
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(KEY, theme)
    } catch {
      // Private mode or blocked storage: the theme just won't be remembered.
    }
  }, [dark])

  // Lower sleep threshold: let the swing die down further before it snaps straight.
  return <PullCord onPull={() => setDark((d) => !d)} pulled={!dark} ariaLabel="Toggle light mode" config={{ sleepVelocity: 0.05 }} />
}

const root = document.getElementById("cord")
if (root) createRoot(root).render(<Cord />)
