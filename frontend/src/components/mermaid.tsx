import * as React from "react"

import { tokenHex, useResolvedTheme } from "@/lib/theme"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"

type Mermaid = typeof import("mermaid").default

let loading: Promise<Mermaid> | undefined
let queue: Promise<unknown> = Promise.resolve()
let renders = 0

function loadMermaid() {
  loading ??= import("mermaid").then((module) => module.default)
  return loading
}

function configure(mermaid: Mermaid) {
  const ink = tokenHex("--foreground")
  const muted = tokenHex("--muted-foreground")
  const sheet = tokenHex("--background")
  const raised = tokenHex("--card")
  const subtle = tokenHex("--muted")
  const rule = tokenHex("--border")
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "base",
    fontFamily: "'Inter Variable', system-ui, sans-serif",
    flowchart: { curve: "basis", padding: 12, htmlLabels: true },
    sequence: { mirrorActors: false, messageFontWeight: 400 },
    themeVariables: {
      fontSize: "13px",
      background: sheet,
      primaryColor: raised,
      primaryBorderColor: muted,
      primaryTextColor: ink,
      secondaryColor: subtle,
      tertiaryColor: sheet,
      lineColor: muted,
      textColor: ink,
      mainBkg: raised,
      nodeBorder: muted,
      clusterBkg: subtle,
      clusterBorder: rule,
      titleColor: ink,
      edgeLabelBackground: sheet,
      actorBkg: raised,
      actorBorder: muted,
      actorTextColor: ink,
      actorLineColor: rule,
      signalColor: muted,
      signalTextColor: ink,
      labelBoxBkgColor: raised,
      labelBoxBorderColor: rule,
      labelTextColor: ink,
      loopTextColor: ink,
      noteBkgColor: subtle,
      noteBorderColor: muted,
      noteTextColor: ink,
      attributeBackgroundColorOdd: raised,
      attributeBackgroundColorEven: subtle,
    },
  })
}

/** Mermaid renders one diagram at a time; calls wait their turn. */
function render(source: string) {
  const next = queue.then(async () => {
    const mermaid = await loadMermaid()
    configure(mermaid)
    renders += 1
    const { svg } = await mermaid.render(`mermaid-${renders}`, source)
    return svg
  })
  queue = next.catch(() => undefined)
  return next
}

type State =
  | { kind: "loading" }
  | { kind: "ready"; svg: string }
  | { kind: "error"; message: string }

export function useMermaid(source: string) {
  const theme = useResolvedTheme()
  const [state, setState] = React.useState<State>({ kind: "loading" })

  React.useEffect(() => {
    let current = true
    render(source).then(
      (svg) => current && setState({ kind: "ready", svg }),
      (error: unknown) =>
        current &&
        setState({
          kind: "error",
          message: error instanceof Error ? error.message : String(error),
        })
    )
    return () => {
      current = false
    }
  }, [source, theme])

  return state
}

export function MermaidCanvas({
  state,
  label,
  className,
}: {
  state: State
  label: string
  className?: string
}) {
  if (state.kind === "loading") {
    return <Skeleton className={cn("h-48 w-full", className)} />
  }
  if (state.kind === "error") {
    return (
      <p role="alert" className="text-xs text-destructive">
        This diagram could not be drawn: {state.message}
      </p>
    )
  }
  return (
    <div
      role="img"
      aria-label={label}
      className={cn("flex justify-center [&_svg]:h-auto [&_svg]:max-w-full", className)}
      // Mermaid output, rendered with securityLevel "strict".
      dangerouslySetInnerHTML={{ __html: state.svg }}
    />
  )
}
