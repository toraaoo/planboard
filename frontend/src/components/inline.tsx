import * as React from "react"
import { Link } from "@tanstack/react-router"

const INLINE = /`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)\s]+)\)/g
const SLUG = "[a-z0-9]+(?:-[a-z0-9]+)*"
const PLAN_REF = new RegExp(`^(${SLUG}(?:/${SLUG})*)?(?:#(${SLUG}))?$`)

const linkClass = "font-medium underline underline-offset-4 hover:text-foreground"

export function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="bg-muted px-1 py-0.5 font-mono text-[0.9em]">
      {children}
    </code>
  )
}

function InlineLink({
  label,
  href,
  planId,
}: {
  label: string
  href: string
  planId: string
}) {
  if (/^(https?:|mailto:)/.test(href)) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={linkClass}>
        {label}
      </a>
    )
  }
  const match = href.match(PLAN_REF)
  if (match && (match[1] || match[2])) {
    return (
      <Link
        to="/plan/$"
        params={{ _splat: match[1] ?? planId }}
        search={{ at: match[2] }}
        className={linkClass}
      >
        {label}
      </Link>
    )
  }
  return <>{label}</>
}

/** The plan format's inline markup: `code`, **bold** and [label](href). */
export function Inline({ text, planId }: { text: string; planId: string }) {
  const parts: React.ReactNode[] = []
  let cursor = 0
  for (const match of text.matchAll(INLINE)) {
    parts.push(text.slice(cursor, match.index))
    const [, code, bold, label, href] = match
    const key = match.index
    if (code !== undefined) parts.push(<Code key={key}>{code}</Code>)
    else if (bold !== undefined) parts.push(<strong key={key} className="font-semibold">{bold}</strong>)
    else parts.push(<InlineLink key={key} label={label} href={href} planId={planId} />)
    cursor = match.index + match[0].length
  }
  parts.push(text.slice(cursor))
  return <>{parts}</>
}
