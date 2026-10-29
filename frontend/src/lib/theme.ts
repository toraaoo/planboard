import * as React from "react"

function subscribe(callback: () => void) {
  const observer = new MutationObserver(callback)
  observer.observe(document.documentElement, { attributeFilter: ["class"] })
  return () => observer.disconnect()
}

/** "dark" or "light" as currently applied to <html> by the ThemeProvider. */
export function useResolvedTheme() {
  return React.useSyncExternalStore(subscribe, () =>
    document.documentElement.classList.contains("dark") ? "dark" : "light"
  )
}

let context: CanvasRenderingContext2D | null = null

/**
 * A CSS custom property as #rrggbb, for libraries that cannot parse oklch().
 * Translucent tokens are flattened onto the page background.
 */
export function tokenHex(name: string) {
  const style = getComputedStyle(document.documentElement)
  const value = style.getPropertyValue(name).trim()
  context ??= document.createElement("canvas").getContext("2d", { willReadFrequently: true })
  if (!context) return value
  context.fillStyle = style.getPropertyValue("--background").trim() || "#fff"
  context.fillRect(0, 0, 1, 1)
  context.fillStyle = value
  context.fillRect(0, 0, 1, 1)
  const [r, g, b] = context.getImageData(0, 0, 1, 1).data
  return `#${[r, g, b].map((channel) => channel.toString(16).padStart(2, "0")).join("")}`
}
