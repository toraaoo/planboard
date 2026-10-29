import * as React from "react"
import type { Announcements, DragEndEvent, UniqueIdentifier } from "@dnd-kit/core"
import { Link } from "@tanstack/react-router"
import {
  DotsSixVerticalIcon,
  DotsThreeIcon,
  KanbanIcon,
} from "@phosphor-icons/react"

import type { PlanPayload, Task, TaskStatus } from "@/lib/api"
import { position, refLabel, STATUS_LABEL, TASK_STATUSES, waitingOn } from "@/lib/plan"
import { useSetTaskStatus } from "@/lib/queries"
import { Inline } from "@/components/inline"
import { STATUS_ICON } from "@/components/status"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Kanban,
  KanbanBoard,
  KanbanColumn,
  KanbanItem,
  KanbanItemHandle,
  KanbanOverlay,
} from "@/components/ui/kanban"

interface CardTask {
  task: Task
  index: number
}

type Columns = Record<TaskStatus, CardTask[]>

function toColumns(payload: PlanPayload): Columns {
  const columns: Columns = { todo: [], doing: [], blocked: [], done: [] }
  payload.plan.tasks.forEach((task, index) => columns[task.status].push({ task, index }))
  return columns
}

function sorted(columns: Columns): Columns {
  const byIndex = (a: CardTask, b: CardTask) => a.index - b.index
  return {
    todo: [...columns.todo].sort(byIndex),
    doing: [...columns.doing].sort(byIndex),
    blocked: [...columns.blocked].sort(byIndex),
    done: [...columns.done].sort(byIndex),
  }
}

function columnOf(columns: Columns, id: UniqueIdentifier): TaskStatus | null {
  if (id in columns) return id as TaskStatus
  return TASK_STATUSES.find((status) => columns[status].some((card) => card.task.id === id)) ?? null
}

function MoveMenu({
  card,
  onMove,
}: {
  card: CardTask
  onMove: (status: TaskStatus) => void
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label={`Move ${card.task.title}`}
          />
        }
      >
        <DotsThreeIcon />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuGroup>
          <DropdownMenuLabel>Move to</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={card.task.status}
            onValueChange={(value) => onMove(value as TaskStatus)}
          >
            {TASK_STATUSES.map((status) => {
              const StatusGlyph = STATUS_ICON[status]
              return (
                <DropdownMenuRadioItem key={status} value={status}>
                  <StatusGlyph />
                  {STATUS_LABEL[status]}
                </DropdownMenuRadioItem>
              )
            })}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function TaskCard({
  card,
  payload,
  onMove,
  overlay = false,
}: {
  card: CardTask
  payload: PlanPayload
  onMove?: (status: TaskStatus) => void
  overlay?: boolean
}) {
  const { task, index } = card
  const waits = waitingOn(task, payload)
  return (
    <Card size="sm" className="gap-2 bg-card">
      <CardHeader>
        <p className="flex items-center gap-1 font-mono text-[0.7rem] text-muted-foreground">
          <KanbanItemHandle
            aria-label={`Drag ${task.title}`}
            aria-describedby="board-hint"
            className="-ml-1 inline-flex items-center p-0.5 text-muted-foreground hover:text-foreground"
          >
            <DotsSixVerticalIcon aria-hidden="true" />
          </KanbanItemHandle>
          {position(index)} · {task.id}
        </p>
        <CardTitle>
          {overlay ? (
            task.title
          ) : (
            <Link
              to="/plan/$"
              params={{ _splat: payload.id }}
              search={(prev) => ({ ...prev, task: task.id })}
              className="after:absolute after:inset-0 hover:underline focus-visible:outline-none"
            >
              {task.title}
            </Link>
          )}
        </CardTitle>
        {onMove ? (
          <CardAction className="relative z-10">
            <MoveMenu card={card} onMove={onMove} />
          </CardAction>
        ) : null}
        {task.summary ? (
          <CardDescription className="line-clamp-3">
            <Inline text={task.summary} planId={payload.id} />
          </CardDescription>
        ) : null}
      </CardHeader>
      {(task.status === "blocked" && task.note) || waits.length ? (
        <CardFooter className="flex flex-col items-start gap-1.5 border-t py-2">
          {task.status === "blocked" && task.note ? (
            <p className="text-xs text-destructive">
              <Inline text={task.note} planId={payload.id} />
            </p>
          ) : null}
          {waits.length ? (
            <p className="text-xs text-muted-foreground">
              Waits on {waits.map((ref) => refLabel(ref, payload)).join(", ")}
            </p>
          ) : null}
        </CardFooter>
      ) : null}
    </Card>
  )
}

export function BoardView({ payload }: { payload: PlanPayload }) {
  const setStatus = useSetTaskStatus(payload.id)
  const [columns, setColumns] = React.useState(() => toColumns(payload))
  const dragging = React.useRef(false)

  React.useEffect(() => {
    if (!dragging.current) setColumns(toColumns(payload))
  }, [payload])

  const titleOf = React.useCallback(
    (id: UniqueIdentifier) =>
      payload.plan.tasks.find((task) => task.id === id)?.title ?? String(id),
    [payload]
  )

  const move = React.useCallback(
    (taskId: string, status: TaskStatus) => {
      const task = payload.plan.tasks.find((candidate) => candidate.id === taskId)
      if (task && task.status !== status) setStatus.mutate({ taskId, status })
    },
    [payload, setStatus]
  )

  const onDragEnd = (event: DragEndEvent) => {
    dragging.current = false
    // Keyboard drags report only where they ended; pointer drags already moved the card.
    const status = columnOf(columns, event.over?.id ?? event.active.id)
    if (status) move(String(event.active.id), status)
    // Cards keep build order: put the dropped card back in its place.
    setColumns(sorted(columns))
  }

  const announcements = React.useMemo<Announcements>(() => {
    const label = (id: UniqueIdentifier) => {
      const status = columnOf(columns, id)
      return status ? STATUS_LABEL[status] : String(id)
    }
    return {
      onDragStart: ({ active }) => `Picked up ${titleOf(active.id)}, in ${label(active.id)}.`,
      onDragOver: ({ active, over }) =>
        over ? `${titleOf(active.id)} is over ${label(over.id)}.` : undefined,
      onDragEnd: ({ active, over }) =>
        over ? `${titleOf(active.id)} moved to ${label(over.id)}.` : `${titleOf(active.id)} was not moved.`,
      onDragCancel: ({ active }) => `Cancelled. ${titleOf(active.id)} stays where it was.`,
    }
  }, [columns, titleOf])

  if (!payload.plan.tasks.length) {
    return (
      <Empty className="border border-dashed">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <KanbanIcon />
          </EmptyMedia>
          <EmptyTitle>No tasks yet</EmptyTitle>
          <EmptyDescription>
            Add the build order to the plan’s <code>tasks</code> list.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p id="board-hint" className="text-xs text-muted-foreground">
        Drag a card by its handle, or press Space on the handle and use the arrow keys.
        The menu on each card moves it too.
      </p>
      <Kanban
        value={columns}
        onValueChange={(next) => setColumns(next as Columns)}
        getItemValue={(card) => card.task.id}
        // Order inside a column is the build order, not something to drag.
        onMove={() => undefined}
        onDragStart={() => {
          dragging.current = true
        }}
        onDragEnd={onDragEnd}
        onDragCancel={() => {
          dragging.current = false
          setColumns(toColumns(payload))
        }}
        accessibility={{ announcements }}
      >
        <div className="-mx-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
          <KanbanBoard className="min-w-max sm:min-w-0">
            {TASK_STATUSES.map((status) => {
              const StatusGlyph = STATUS_ICON[status]
              const cards = columns[status]
              return (
                <KanbanColumn
                  key={status}
                  value={status}
                  aria-labelledby={`column-${status}`}
                  className="h-auto min-h-48 w-72 shrink-0 sm:w-auto sm:flex-1"
                >
                  <header className="flex items-center justify-between gap-2 px-0.5">
                    <h2 id={`column-${status}`} className="flex items-center gap-1.5 text-xs font-medium">
                      <StatusGlyph aria-hidden="true" />
                      {STATUS_LABEL[status]}
                    </h2>
                    <Badge variant="secondary" aria-label={`${cards.length} tasks`}>
                      {cards.length}
                    </Badge>
                  </header>
                  <ul className="flex flex-col gap-2">
                    {cards.map((card) => (
                      <KanbanItem key={card.task.id} value={card.task.id} render={<li />} className="relative">
                        <TaskCard card={card} payload={payload} onMove={(next) => move(card.task.id, next)} />
                      </KanbanItem>
                    ))}
                  </ul>
                  {cards.length ? null : (
                    <p className="flex flex-1 items-center justify-center border border-dashed p-4 text-center text-xs text-muted-foreground">
                      Drop a card here to mark it {STATUS_LABEL[status].toLowerCase()}.
                    </p>
                  )}
                </KanbanColumn>
              )
            })}
          </KanbanBoard>
        </div>
        <KanbanOverlay>
          {({ value }) => {
            const status = columnOf(columns, value)
            const card = status ? columns[status].find((candidate) => candidate.task.id === value) : undefined
            return card ? (
              <KanbanItem value={card.task.id}>
                <TaskCard card={card} payload={payload} overlay />
              </KanbanItem>
            ) : null
          }}
        </KanbanOverlay>
      </Kanban>
    </div>
  )
}
