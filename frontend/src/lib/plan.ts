import type { PlanPayload, PlanStatus, Task, TaskStatus } from "@/lib/api"

export const TASK_STATUSES: TaskStatus[] = ["todo", "doing", "blocked", "done"]
export const PLAN_STATUSES: PlanStatus[] = ["draft", "approved", "archived"]

export const STATUS_LABEL: Record<TaskStatus, string> = {
  todo: "To do",
  doing: "Doing",
  blocked: "Blocked",
  done: "Done",
}

export const PLAN_STATUS_LABEL: Record<PlanStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  archived: "Archived",
}

export function position(index: number) {
  return String(index + 1).padStart(2, "0")
}

export function plural(count: number, word: string) {
  return `${count} ${word}${count === 1 ? "" : "s"}`
}

export function summarizeTasks(tasks: Array<Pick<Task, "status">>) {
  const done = tasks.filter((task) => task.status === "done").length
  return `${done} of ${tasks.length} tasks done`
}

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
})

export function formatDate(iso: string) {
  return dateFormat.format(new Date(`${iso}T00:00:00Z`))
}

/** References this task still waits on: none once it is done. */
export function waitingOn(task: Task, payload: PlanPayload) {
  if (task.status === "done") return []
  return task.dependsOn.filter((ref) => payload.resolved[ref]?.state !== "done")
}

export function taskIndex(payload: PlanPayload, taskId: string) {
  return payload.plan.tasks.findIndex((task) => task.id === taskId)
}

/** A reference as people read it: "03 Devices" here, "Plan · Task" elsewhere. */
export function refLabel(ref: string, payload: PlanPayload) {
  const resolution = payload.resolved[ref]
  if (!resolution) return ref
  if (resolution.plan_id === payload.id && resolution.task_id) {
    const index = taskIndex(payload, resolution.task_id)
    return index >= 0 ? `${position(index)} ${resolution.title}` : ref
  }
  if (!resolution.title) return ref
  return resolution.task_id
    ? `${resolution.plan_title} · ${resolution.title}`
    : (resolution.plan_title ?? ref)
}

/** The task a reference points at, when it is one in this plan. */
export function localTask(ref: string, payload: PlanPayload) {
  const resolution = payload.resolved[ref]
  if (resolution?.plan_id !== payload.id || !resolution.task_id) return null
  return payload.plan.tasks.find((task) => task.id === resolution.task_id) ?? null
}

export function neededBy(task: Task, payload: PlanPayload) {
  const local = payload.plan.tasks
    .map((candidate, index) => ({ task: candidate, index }))
    .filter(({ task: candidate }) =>
      candidate.dependsOn.some((ref) => localTask(ref, payload)?.id === task.id)
    )
  const remote = payload.dependents.filter(
    (dependent) => dependent.target === task.id || dependent.target === null
  )
  return { local, remote }
}
