import * as React from "react"
import { Link } from "@tanstack/react-router"
import { HashIcon, ListIcon } from "@phosphor-icons/react"

import type { PlanPayload, Task } from "@/lib/api"
import { plural, position, waitingOn } from "@/lib/plan"
import { cn } from "@/lib/utils"
import { Blocks, diagramAnchors } from "@/components/blocks"
import { Inline } from "@/components/inline"
import { StatusIcon, TaskStatusLabel } from "@/components/status"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item"
import { toast } from "@/components/ui/toast"

interface Entry {
  id: string
  title: string
}

/** The id of the section nearest the top of the viewport. */
function useActiveSection(ids: string[]) {
  const [active, setActive] = React.useState(ids[0])
  React.useEffect(() => {
    const visible = new Map<string, boolean>()
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          visible.set(entry.target.id.replace(/^section-/, ""), entry.isIntersecting)
        }
        const first = ids.find((id) => visible.get(id))
        if (first) setActive(first)
      },
      { rootMargin: "-80px 0px -60% 0px" }
    )
    for (const id of ids) {
      const element = document.getElementById(`section-${id}`)
      if (element) observer.observe(element)
    }
    return () => observer.disconnect()
  }, [ids])
  return active
}

function Toc({
  entries,
  planId,
  active,
}: {
  entries: Entry[]
  planId: string
  active?: string
}) {
  return (
    <ol className="flex flex-col border-l">
      {entries.map((entry) => (
        <li key={entry.id}>
          <Link
            to="/plan/$"
            params={{ _splat: planId }}
            search={(prev) => ({ ...prev, at: entry.id })}
            aria-current={entry.id === active ? "location" : undefined}
            className={cn(
              "-ml-px block border-l border-transparent py-1 pl-3 text-xs text-muted-foreground transition-colors hover:text-foreground",
              "aria-[current=location]:border-foreground aria-[current=location]:text-foreground"
            )}
          >
            {entry.title}
          </Link>
        </li>
      ))}
    </ol>
  )
}

function SectionHeading({
  id,
  title,
  planId,
}: {
  id: string
  title: string
  planId: string
}) {
  return (
    <header className="group flex items-baseline justify-between gap-4 border-b pb-2">
      <h2 id={`heading-${id}`} tabIndex={-1} className="font-heading text-lg font-semibold outline-none">
        {title}
      </h2>
      <Link
        to="/plan/$"
        params={{ _splat: planId }}
        search={(prev) => ({ ...prev, at: id })}
        aria-label={`Link to ${title}`}
        className="flex items-center gap-0.5 font-mono text-[0.7rem] text-muted-foreground uppercase opacity-60 group-hover:opacity-100 hover:text-foreground focus-visible:opacity-100"
      >
        <HashIcon aria-hidden="true" />
        {id}
      </Link>
    </header>
  )
}

function TaskList({ payload }: { payload: PlanPayload }) {
  return (
    <ItemGroup className="border">
      {payload.plan.tasks.map((task, index) => {
        const waits = waitingOn(task, payload)
        return (
          <Item
            key={task.id}
            className="border-b last:border-b-0"
            render={
              <Link
                to="/plan/$"
                params={{ _splat: payload.id }}
                search={(prev) => ({ ...prev, task: task.id })}
              />
            }
          >
            <ItemMedia className="font-mono text-muted-foreground tabular-nums">
              {position(index)}
            </ItemMedia>
            <ItemContent>
              <ItemTitle>{task.title}</ItemTitle>
              {task.summary ? (
                <ItemDescription>
                  <Inline text={task.summary} planId={payload.id} />
                </ItemDescription>
              ) : null}
              {waits.length ? (
                <ItemDescription>Waits on {plural(waits.length, "task")}</ItemDescription>
              ) : null}
            </ItemContent>
            <ItemActions>
              <TaskStatusLabel status={task.status} />
            </ItemActions>
          </Item>
        )
      })}
    </ItemGroup>
  )
}

function BuiltBy({ builders, planId }: { builders: Array<{ task: Task; index: number }>; planId: string }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="font-mono text-[0.7rem] text-muted-foreground uppercase">Built by</span>
      {builders.map(({ task, index }) => (
        <Badge
          key={task.id}
          variant="outline"
          render={
            <Link
              to="/plan/$"
              params={{ _splat: planId }}
              search={(prev) => ({ ...prev, task: task.id })}
              aria-label={`${position(index)} ${task.title}`}
            />
          }
        >
          <StatusIcon status={task.status} />
          {position(index)} {task.title}
        </Badge>
      ))}
    </div>
  )
}

export function DocumentView({ payload, at }: { payload: PlanPayload; at?: string }) {
  const { plan } = payload
  const entries = React.useMemo<Entry[]>(
    () => [
      ...plan.sections.map((section) => ({ id: section.id, title: section.title })),
      ...(plan.tasks.length ? [{ id: "tasks", title: "Tasks" }] : []),
    ],
    [plan.sections, plan.tasks.length]
  )
  const ids = React.useMemo(() => entries.map((entry) => entry.id), [entries])
  const active = useActiveSection(ids)
  const builders = React.useMemo(() => {
    const map = new Map<string, Array<{ task: Task; index: number }>>()
    plan.tasks.forEach((task, index) => {
      for (const sectionId of task.sections) {
        map.set(sectionId, [...(map.get(sectionId) ?? []), { task, index }])
      }
    })
    return map
  }, [plan.tasks])
  const anchors = React.useMemo(
    () => diagramAnchors(payload.id, plan.sections),
    [payload.id, plan.sections]
  )

  useScrollToAnchor(at)

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_14rem]">
      <div className="flex min-w-0 flex-col gap-12">
        <Collapsible className="border lg:hidden">
          <CollapsibleTrigger
            render={<Button variant="ghost" className="w-full justify-start" />}
          >
            <ListIcon data-icon="inline-start" />
            On this page
          </CollapsibleTrigger>
          <CollapsibleContent className="px-3 pb-3">
            <Toc entries={entries} planId={payload.id} active={active} />
          </CollapsibleContent>
        </Collapsible>
        {plan.sections.map((section, sectionIndex) => (
          <section
            key={section.id}
            id={`section-${section.id}`}
            aria-labelledby={`heading-${section.id}`}
            className="flex scroll-mt-20 flex-col gap-4"
          >
            <SectionHeading id={section.id} title={section.title} planId={payload.id} />
            {builders.has(section.id) ? (
              <BuiltBy builders={builders.get(section.id)!} planId={payload.id} />
            ) : null}
            <div className="flex max-w-[72ch] flex-col gap-4 text-sm/7">
              <Blocks
                blocks={section.blocks}
                anchors={anchors[sectionIndex]}
                context={{ planId: payload.id }}
              />
            </div>
          </section>
        ))}
        {plan.tasks.length ? (
          <section
            id="section-tasks"
            aria-labelledby="heading-tasks"
            className="flex scroll-mt-20 flex-col gap-4"
          >
            <SectionHeading id="tasks" title="Tasks" planId={payload.id} />
            <TaskList payload={payload} />
          </section>
        ) : null}
      </div>
      <aside aria-label="On this page" className="hidden lg:block">
        <nav className="sticky top-20 flex flex-col gap-3">
          <p className="font-mono text-[0.7rem] text-muted-foreground uppercase">On this page</p>
          <Toc entries={entries} planId={payload.id} active={active} />
        </nav>
      </aside>
    </div>
  )
}

/**
 * Scrolls to ?at= once its section or diagram is on the page, and keeps it in
 * place while diagrams above it finish drawing, until the reader scrolls.
 */
function useScrollToAnchor(at?: string) {
  React.useEffect(() => {
    if (!at) return
    const find = () =>
      document.getElementById(`section-${at}`) ?? document.getElementById(`diagram-${at}`)
    let stopped = false
    const stop = () => {
      stopped = true
    }
    const align = () => {
      if (!stopped) find()?.scrollIntoView({ block: "start" })
    }
    const timers = [0, 150, 500, 1000, 2000].map((delay) => setTimeout(align, delay))
    const first = setTimeout(() => {
      const target = find()
      if (!target) {
        toast.add({ type: "error", title: `Nothing called “${at}” in this plan.` })
        return
      }
      const focusable = target.querySelector<HTMLElement>("h2") ?? target
      if (focusable === target) target.tabIndex = -1
      focusable.focus({ preventScroll: true })
      if (target.id.startsWith("diagram-")) {
        target.dataset.highlight = "true"
        setTimeout(() => delete target.dataset.highlight, 2200)
      }
    }, 0)
    const events = ["wheel", "touchstart", "keydown", "pointerdown"] as const
    for (const name of events) window.addEventListener(name, stop, { passive: true })
    return () => {
      for (const timer of [...timers, first]) clearTimeout(timer)
      for (const name of events) window.removeEventListener(name, stop)
    }
  }, [at])
}
