export type TaskStatus = "todo" | "doing" | "blocked" | "done"
export type PlanStatus = "draft" | "approved" | "archived"
export type RefState = "done" | "pending" | "missing"

export type Inline = string

export interface Task {
  id: string
  title: string
  status: TaskStatus
  summary?: Inline
  note?: Inline
  dependsOn: string[]
  sections: string[]
  diagrams: string[]
}

export interface ListItem {
  text: Inline
  items?: Array<Inline | ListItem>
}

export interface Diagram {
  plan_id: string
  diagram_id: string
  plan_title?: string
  alt: string
  file?: string
  source?: string
  error?: string
}

export type Block =
  | { type: "heading"; text: string }
  | { type: "text"; text: Inline }
  | { type: "list"; ordered?: boolean; items: Array<Inline | ListItem> }
  | { type: "table"; columns: string[]; rows: Array<Array<Inline | null>>; caption?: Inline }
  | { type: "callout"; tone: "note" | "warning"; title: string; text: Inline }
  | { type: "code"; language?: string; code: string; caption?: Inline }
  | { type: "diagram"; ref: string; caption?: Inline; diagram: Diagram }

export interface Section {
  id: string
  title: string
  blocks: Block[]
}

export interface Plan {
  title: string
  summary: Inline
  status: PlanStatus
  updated?: string
  branch?: string
  tags: string[]
  dependsOn: string[]
  tasks: Task[]
  sections: Section[]
}

export interface Resolution {
  ref: string
  plan_id: string
  task_id: string | null
  title: string | null
  plan_title: string | null
  state: RefState
}

export interface Dependent {
  plan_id: string
  plan_title: string
  task_id: string | null
  title: string
  target: string | null
}

export interface PlanPayload {
  kind: "plan"
  id: string
  folder: string
  path: string
  plan: Plan
  resolved: Record<string, Resolution>
  dependents: Dependent[]
  problems: string[]
}

export interface BrokenPayload {
  kind: "broken"
  id: string
  path: string
  errors: string[]
}

export interface PlanSummary {
  id: string
  folder: string
  title: string
  summary: Inline
  status: PlanStatus
  tags: string[]
  updated: string | null
  tasks: Array<Pick<Task, "id" | "title" | "status">>
  problems: string[]
}

export interface BrokenSummary {
  id: string
  folder: string
  errors: string[]
}

export interface PlanList {
  plans: PlanSummary[]
  broken: BrokenSummary[]
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
    },
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    const message =
      typeof detail === "string"
        ? detail
        : (detail?.message ?? `Request failed with ${response.status}.`)
    throw new ApiError(response.status, message)
  }
  return body as T
}

export function encodePlanId(planId: string) {
  return planId.split("/").map(encodeURIComponent).join("/")
}

export const api = {
  version: () => request<{ version: string }>("/api/version"),
  plans: () => request<PlanList>("/api/plans"),
  plan: (planId: string) =>
    request<PlanPayload | BrokenPayload>(`/api/plans/${encodePlanId(planId)}`),
  setTaskStatus: (planId: string, taskId: string, status: TaskStatus) =>
    request<{ version: string }>(
      `/api/plans/${encodePlanId(planId)}/tasks/${encodeURIComponent(taskId)}`,
      { method: "PATCH", body: JSON.stringify({ status }) }
    ),
}
