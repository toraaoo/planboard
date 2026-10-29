import { Link, useNavigate } from "@tanstack/react-router"
import { WarningIcon } from "@phosphor-icons/react"

import type { PlanPayload, RefState, TaskStatus } from "@/lib/api"
import {
  localTask,
  neededBy,
  position,
  refLabel,
  STATUS_LABEL,
  TASK_STATUSES,
  taskIndex,
} from "@/lib/plan"
import { useSetTaskStatus } from "@/lib/queries"
import { Code, Inline } from "@/components/inline"
import { STATUS_ICON, TaskStatusLabel } from "@/components/status"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

const REF_STATE: Record<RefState, { label: string; variant: "secondary" | "outline" | "destructive" }> = {
  done: { label: "Done", variant: "secondary" },
  pending: { label: "Pending", variant: "outline" },
  missing: { label: "Missing", variant: "destructive" },
}

const linkClass =
  "text-left underline decoration-muted-foreground/50 underline-offset-4 hover:decoration-foreground"

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="font-mono text-[0.7rem] text-muted-foreground uppercase">{label}</h3>
      {children}
    </section>
  )
}

function TaskDetails({ payload, taskId }: { payload: PlanPayload; taskId: string }) {
  const setStatus = useSetTaskStatus(payload.id)
  const index = taskIndex(payload, taskId)
  const task = payload.plan.tasks[index]
  const sections = new Map(payload.plan.sections.map((section) => [section.id, section.title]))
  const needed = neededBy(task, payload)
  const planLink = { to: "/plan/$", params: { _splat: payload.id } } as const

  return (
    <>
      <SheetHeader className="gap-1 pr-12">
        <p className="font-mono text-[0.7rem] text-muted-foreground uppercase">
          {position(index)} · {task.id}
        </p>
        <SheetTitle className="text-base">{task.title}</SheetTitle>
        <SheetDescription className="sr-only">
          Status, dependencies and the sections this task builds.
        </SheetDescription>
      </SheetHeader>
      <Separator />
      <div className="flex flex-col gap-6 overflow-y-auto p-4 text-sm/relaxed">
        <Group label="Status">
          <ToggleGroup
            aria-label="Status"
            variant="outline"
            spacing={0}
            value={[task.status]}
            onValueChange={(value: string[]) => {
              const status = value[0] as TaskStatus | undefined
              if (status && status !== task.status) {
                setStatus.mutate({ taskId: task.id, status })
              }
            }}
            className="w-full"
          >
            {TASK_STATUSES.map((status) => {
              const StatusGlyph = STATUS_ICON[status]
              return (
                <ToggleGroupItem key={status} value={status} className="flex-1">
                  <StatusGlyph data-icon="inline-start" />
                  {STATUS_LABEL[status]}
                </ToggleGroupItem>
              )
            })}
          </ToggleGroup>
        </Group>
        {task.summary ? (
          <p className="text-pretty">
            <Inline text={task.summary} planId={payload.id} />
          </p>
        ) : null}
        {task.note ? (
          <Alert role="note">
            <WarningIcon />
            <AlertDescription>
              <Inline text={task.note} planId={payload.id} />
            </AlertDescription>
          </Alert>
        ) : null}
        {task.dependsOn.length ? (
          <Group label="Depends on">
            <ul className="flex flex-col gap-2">
              {task.dependsOn.map((ref) => {
                const resolution = payload.resolved[ref]
                const state = REF_STATE[resolution?.state ?? "missing"]
                const local = localTask(ref, payload)
                return (
                  <li key={ref} className="flex items-baseline gap-2">
                    <Badge variant={state.variant} className="shrink-0">
                      {state.label}
                    </Badge>
                    {local ? (
                      <Link {...planLink} search={(prev) => ({ ...prev, task: local.id })} className={linkClass}>
                        {refLabel(ref, payload)}
                      </Link>
                    ) : resolution && resolution.state !== "missing" ? (
                      <Link
                        to="/plan/$"
                        params={{ _splat: resolution.plan_id }}
                        search={{ task: resolution.task_id ?? undefined }}
                        className={linkClass}
                      >
                        {refLabel(ref, payload)}
                      </Link>
                    ) : (
                      <Code>{ref}</Code>
                    )}
                  </li>
                )
              })}
            </ul>
          </Group>
        ) : null}
        {needed.local.length || needed.remote.length ? (
          <Group label="Needed by">
            <ul className="flex flex-col gap-2">
              {needed.local.map(({ task: candidate, index: at }) => (
                <li key={candidate.id} className="flex items-baseline gap-2">
                  <TaskStatusLabel status={candidate.status} />
                  <Link {...planLink} search={(prev) => ({ ...prev, task: candidate.id })} className={linkClass}>
                    {position(at)} {candidate.title}
                  </Link>
                </li>
              ))}
              {needed.remote.map((dependent) => (
                <li key={`${dependent.plan_id}#${dependent.task_id}`}>
                  <Link
                    to="/plan/$"
                    params={{ _splat: dependent.plan_id }}
                    search={{ task: dependent.task_id ?? undefined }}
                    className={linkClass}
                  >
                    {dependent.plan_title}
                    {dependent.task_id ? ` · ${dependent.title}` : ""}
                  </Link>
                </li>
              ))}
            </ul>
          </Group>
        ) : null}
        {task.sections.length || task.diagrams.length ? (
          <Group label="Builds">
            <ul className="flex flex-col gap-2">
              {task.sections.map((sectionId) => (
                <li key={sectionId}>
                  <Link {...planLink} search={{ view: "document", at: sectionId }} className={linkClass}>
                    {sections.get(sectionId) ?? sectionId}
                  </Link>
                </li>
              ))}
              {task.diagrams.map((diagramId) => (
                <li key={diagramId}>
                  <Link {...planLink} search={{ view: "document", at: diagramId }} className={linkClass}>
                    Fig · {diagramId}
                  </Link>
                </li>
              ))}
            </ul>
          </Group>
        ) : null}
      </div>
    </>
  )
}

/** Task details as a side panel; the open task lives in the ?task= search param. */
export function TaskSheet({ payload, taskId }: { payload: PlanPayload; taskId?: string }) {
  const navigate = useNavigate()
  const exists = taskId !== undefined && taskIndex(payload, taskId) >= 0

  return (
    <Sheet
      open={exists}
      onOpenChange={(open) => {
        if (!open) {
          void navigate({
            to: "/plan/$",
            params: { _splat: payload.id },
            search: (prev) => ({ ...prev, task: undefined }),
            replace: true,
          })
        }
      }}
    >
      <SheetContent className="w-full gap-0 sm:max-w-md data-[side=right]:sm:max-w-md">
        {exists ? <TaskDetails payload={payload} taskId={taskId} /> : null}
      </SheetContent>
    </Sheet>
  )
}
