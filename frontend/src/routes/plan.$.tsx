import * as React from "react"
import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, notFound } from "@tanstack/react-router"
import { FileTextIcon, GraphIcon, KanbanIcon, WarningCircleIcon } from "@phosphor-icons/react"
import { z } from "zod"

import { ApiError, type BrokenPayload } from "@/lib/api"
import { planQuery } from "@/lib/queries"
import { DocumentView } from "@/components/document-view"
import { Code } from "@/components/inline"
import { PlanHeader } from "@/components/plan-header"
import { TaskSheet } from "@/components/task-sheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const BoardView = React.lazy(() =>
  import("@/components/board-view").then((module) => ({ default: module.BoardView }))
)
const GraphView = React.lazy(() =>
  import("@/components/graph-view").then((module) => ({ default: module.GraphView }))
)

const VIEWS = ["document", "board", "graph"] as const
type View = (typeof VIEWS)[number]

const searchSchema = z.object({
  view: z.enum(VIEWS).optional().catch(undefined),
  task: z.string().optional().catch(undefined),
  at: z.string().optional().catch(undefined),
})

export const Route = createFileRoute("/plan/$")({
  validateSearch: searchSchema,
  loader: async ({ params, context: { queryClient } }) => {
    try {
      return await queryClient.ensureQueryData(planQuery(params._splat ?? ""))
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) throw notFound()
      throw error
    }
  },
  head: ({ loaderData }) => ({
    meta: [
      {
        title:
          loaderData?.kind === "plan" ? `${loaderData.plan.title} · planboard` : "planboard",
      },
    ],
  }),
  pendingComponent: PlanPending,
  component: PlanPage,
})

function PlanPage() {
  const { _splat: planId = "" } = Route.useParams()
  const { view = "document", task, at } = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data: payload } = useSuspenseQuery(planQuery(planId))

  if (payload.kind === "broken") return <BrokenPlan payload={payload} />

  return (
    <div className="flex flex-col gap-8">
      <PlanHeader payload={payload} />
      <Tabs
        value={view}
        onValueChange={(next: View) =>
          void navigate({ search: (prev) => ({ ...prev, view: next, at: undefined }) })
        }
        className="gap-6"
      >
        <TabsList variant="line" aria-label="Plan views" className="w-full justify-start border-b">
          <TabsTrigger value="document">
            <FileTextIcon data-icon="inline-start" />
            Document
          </TabsTrigger>
          <TabsTrigger value="board">
            <KanbanIcon data-icon="inline-start" />
            Board
          </TabsTrigger>
          <TabsTrigger value="graph">
            <GraphIcon data-icon="inline-start" />
            Graph
          </TabsTrigger>
        </TabsList>
        <TabsContent value="document">
          <DocumentView payload={payload} at={at} />
        </TabsContent>
        <TabsContent value="board">
          <React.Suspense fallback={<Skeleton className="h-96" />}>
            <BoardView payload={payload} />
          </React.Suspense>
        </TabsContent>
        <TabsContent value="graph">
          <React.Suspense fallback={<Skeleton className="h-96" />}>
            <GraphView payload={payload} />
          </React.Suspense>
        </TabsContent>
      </Tabs>
      <TaskSheet payload={payload} taskId={task} />
    </div>
  )
}

function BrokenPlan({ payload }: { payload: BrokenPayload }) {
  return (
    <Alert variant="destructive">
      <WarningCircleIcon />
      <AlertTitle>
        <span className="font-mono">data/{payload.path}</span> can’t be read
      </AlertTitle>
      <AlertDescription>
        <p>
          Fix the problems below and save the file; this page reloads on its own.{" "}
          <Code>planboard validate</Code> shows the same list.
        </p>
        <ul className="list-disc pl-4">
          {payload.errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  )
}

function PlanPending() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-4 w-48" />
      <Skeleton className="h-8 w-96 max-w-full" />
      <Skeleton className="h-16 w-full max-w-2xl" />
      <Skeleton className="h-8 w-72" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
