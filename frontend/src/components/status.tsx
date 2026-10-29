import type { Icon } from "@phosphor-icons/react"
import {
  CheckCircleIcon,
  CircleDashedIcon,
  CircleHalfIcon,
  ProhibitIcon,
} from "@phosphor-icons/react"
import { Link } from "@tanstack/react-router"

import type { PlanStatus, Task, TaskStatus } from "@/lib/api"
import {
  PLAN_STATUS_LABEL,
  position,
  STATUS_LABEL,
  summarizeTasks,
  TASK_STATUSES,
} from "@/lib/plan"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

export const STATUS_ICON: Record<TaskStatus, Icon> = {
  todo: CircleDashedIcon,
  doing: CircleHalfIcon,
  blocked: ProhibitIcon,
  done: CheckCircleIcon,
}

const STATUS_BADGE = {
  todo: "outline",
  doing: "secondary",
  blocked: "destructive",
  done: "default",
} as const

/** Fill for progress segments, from the theme's own tokens. */
const SEGMENT: Record<TaskStatus, string> = {
  todo: "bg-border",
  doing: "bg-muted-foreground",
  blocked: "bg-destructive",
  done: "bg-primary",
}

export function StatusIcon({ status }: { status: TaskStatus }) {
  const StatusGlyph = STATUS_ICON[status]
  return <StatusGlyph aria-hidden="true" data-icon="inline-start" />
}

export function TaskStatusLabel({ status }: { status: TaskStatus }) {
  const StatusGlyph = STATUS_ICON[status]
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <StatusGlyph aria-hidden="true" />
      {STATUS_LABEL[status]}
    </span>
  )
}

export function TaskStatusBadge({ status }: { status: TaskStatus }) {
  return (
    <Badge variant={STATUS_BADGE[status]}>
      <StatusIcon status={status} />
      {STATUS_LABEL[status]}
    </Badge>
  )
}

const PLAN_VARIANT = {
  draft: "outline",
  approved: "default",
  archived: "secondary",
} as const

export function PlanStatusBadge({ status }: { status: PlanStatus }) {
  return <Badge variant={PLAN_VARIANT[status]}>{PLAN_STATUS_LABEL[status]}</Badge>
}

type StripTask = Pick<Task, "id" | "title" | "status">

/** One segment per task in build order. Interactive when given a plan id. */
export function ProgressStrip({
  tasks,
  planId,
  className,
}: {
  tasks: StripTask[]
  planId?: string
  className?: string
}) {
  if (!planId) {
    return (
      <div
        role="img"
        aria-label={summarizeTasks(tasks)}
        className={cn("flex h-1.5 gap-px", className)}
      >
        {tasks.map((task) => (
          <span key={task.id} className={cn("flex-1", SEGMENT[task.status])} />
        ))}
      </div>
    )
  }
  return (
    <div
      role="group"
      aria-label="Tasks in build order"
      className={cn("flex h-2.5 gap-px", className)}
    >
      {tasks.map((task, index) => {
        const label = `${position(index)} ${task.title} · ${STATUS_LABEL[task.status]}`
        return (
          <Tooltip key={task.id}>
            <TooltipTrigger
              render={
                <Link
                  to="/plan/$"
                  params={{ _splat: planId }}
                  search={(prev) => ({ ...prev, task: task.id })}
                  aria-label={label}
                  className={cn(
                    "flex-1 transition-opacity hover:opacity-70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                    SEGMENT[task.status]
                  )}
                />
              }
            />
            <TooltipContent>{label}</TooltipContent>
          </Tooltip>
        )
      })}
    </div>
  )
}

export function Tally({ tasks }: { tasks: StripTask[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {TASK_STATUSES.map((status) => (
        <li key={status} className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className={cn("size-2", SEGMENT[status])} />
          {tasks.filter((task) => task.status === status).length}{" "}
          {STATUS_LABEL[status].toLowerCase()}
        </li>
      ))}
    </ul>
  )
}
