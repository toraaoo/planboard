import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { FolderOpenIcon, MagnifyingGlassIcon, WarningCircleIcon } from "@phosphor-icons/react"
import { z } from "zod"

import type { BrokenSummary, PlanList, PlanSummary } from "@/lib/api"
import { formatDate, PLAN_STATUS_LABEL, PLAN_STATUSES, plural, summarizeTasks } from "@/lib/plan"
import { plansQuery } from "@/lib/queries"
import { Code, Inline } from "@/components/inline"
import { PlanStatusBadge, ProgressStrip } from "@/components/status"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

const STATUS_FILTERS = ["all", ...PLAN_STATUSES] as const
type StatusFilter = (typeof STATUS_FILTERS)[number]

const searchSchema = z.object({
  q: z.string().optional().catch(undefined),
  status: z.enum(STATUS_FILTERS).optional().catch(undefined),
})

export const Route = createFileRoute("/")({
  validateSearch: searchSchema,
  loader: ({ context: { queryClient } }) => queryClient.ensureQueryData(plansQuery),
  head: () => ({ meta: [{ title: "Plans · planboard" }] }),
  pendingComponent: IndexPending,
  component: IndexPage,
})

function matches(plan: PlanSummary, text: string, status: StatusFilter) {
  if (status !== "all" && plan.status !== status) return false
  const haystack = [plan.id, plan.title, plan.summary, ...plan.tags].join(" ").toLowerCase()
  return text
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word))
}

function group(plans: PlanSummary[], broken: BrokenSummary[]) {
  const folders = new Map<string, { plans: PlanSummary[]; broken: BrokenSummary[] }>()
  const entry = (folder: string) => {
    const key = folder || "(top level)"
    if (!folders.has(key)) folders.set(key, { plans: [], broken: [] })
    return folders.get(key)!
  }
  for (const plan of plans) entry(plan.folder).plans.push(plan)
  for (const plan of broken) entry(plan.folder).broken.push(plan)
  return [...folders.entries()].sort(([a], [b]) => a.localeCompare(b))
}

function IndexPage() {
  const { q = "", status = "all" } = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data } = useSuspenseQuery(plansQuery)
  const filtering = q.trim() !== "" || status !== "all"
  const plans = data.plans.filter((plan) => matches(plan, q, status))
  const broken = filtering ? [] : data.broken
  const folderCount = new Set(data.plans.map((plan) => plan.folder)).size

  const setSearch = (next: { q?: string; status?: StatusFilter }) =>
    navigate({
      search: (prev) => {
        const merged = { ...prev, ...next }
        return {
          q: merged.q || undefined,
          status: merged.status === "all" ? undefined : merged.status,
        }
      },
      replace: true,
    })

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex flex-col gap-2">
          <h1 className="font-heading text-2xl font-semibold tracking-tight">Plans</h1>
          <p className="text-sm text-muted-foreground">
            {data.plans.length
              ? `${plural(data.plans.length, "plan")} in ${plural(folderCount, "folder")}. Each one is a JSON file in the data folder.`
              : "Each plan is one JSON file in the data folder."}
          </p>
        </div>
        <div role="search" className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <InputGroup className="sm:w-72">
            <InputGroupAddon>
              <MagnifyingGlassIcon />
            </InputGroupAddon>
            <InputGroupInput
              type="search"
              aria-label="Filter plans"
              placeholder="Filter by title, summary or tag"
              value={q}
              onChange={(event) => void setSearch({ q: event.target.value })}
            />
          </InputGroup>
          <ToggleGroup
            aria-label="Status"
            variant="outline"
            spacing={0}
            value={[status]}
            onValueChange={(value: string[]) => {
              if (value[0]) void setSearch({ status: value[0] as StatusFilter })
            }}
          >
            {STATUS_FILTERS.map((filter) => (
              <ToggleGroupItem key={filter} value={filter}>
                {filter === "all" ? "All" : PLAN_STATUS_LABEL[filter]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
      </header>
      <PlanFolders
        data={data}
        plans={plans}
        broken={broken}
        onClear={() => void setSearch({ q: "", status: "all" })}
      />
    </div>
  )
}

function PlanFolders({
  data,
  plans,
  broken,
  onClear,
}: {
  data: PlanList
  plans: PlanSummary[]
  broken: BrokenSummary[]
  onClear: () => void
}) {
  if (!data.plans.length && !data.broken.length) {
    return (
      <Empty className="border border-dashed">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <FolderOpenIcon />
          </EmptyMedia>
          <EmptyTitle>No plans yet</EmptyTitle>
          <EmptyDescription>
            Create one with <Code>planboard new &lt;folder&gt;/&lt;slug&gt;</Code>, fill it in, and it
            appears here.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }
  if (!plans.length && !broken.length) {
    return (
      <Empty className="border border-dashed">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <MagnifyingGlassIcon />
          </EmptyMedia>
          <EmptyTitle>No plans match</EmptyTitle>
          <EmptyDescription>Try fewer words or another status.</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button variant="outline" onClick={onClear}>
            Clear filters
          </Button>
        </EmptyContent>
      </Empty>
    )
  }
  return (
    <div className="flex flex-col gap-10">
      {group(plans, broken).map(([folder, entries]) => (
        <section key={folder} aria-labelledby={`folder-${folder}`} className="flex flex-col gap-3">
          <h2 id={`folder-${folder}`} className="font-mono text-xs text-muted-foreground">
            {folder}/
          </h2>
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {entries.plans.map((plan) => (
              <li key={plan.id} className="flex">
                <PlanCard plan={plan} />
              </li>
            ))}
            {entries.broken.map((entry) => (
              <li key={entry.id} className="flex">
                <BrokenCard entry={entry} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

function PlanCard({ plan }: { plan: PlanSummary }) {
  return (
    <Card className="relative w-full transition-colors hover:bg-muted/50 has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-ring">
      <CardHeader>
        <CardDescription className="font-mono">{plan.id}</CardDescription>
        <CardTitle className="text-base">
          <Link
            to="/plan/$"
            params={{ _splat: plan.id }}
            className="after:absolute after:inset-0 focus-visible:outline-none"
          >
            {plan.title}
          </Link>
        </CardTitle>
        <CardAction>
          <PlanStatusBadge status={plan.status} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <p className="line-clamp-3 text-muted-foreground">
          <Inline text={plan.summary} planId={plan.id} />
        </p>
        {plan.tasks.length ? <ProgressStrip tasks={plan.tasks} className="mt-auto" /> : null}
      </CardContent>
      <CardFooter className="flex flex-wrap justify-between gap-2 border-t py-3 text-muted-foreground">
        <span>{plan.tasks.length ? summarizeTasks(plan.tasks) : "No tasks yet"}</span>
        {plan.updated ? <span>Updated {formatDate(plan.updated)}</span> : null}
        {plan.problems.length ? (
          <Badge variant="destructive" title={plan.problems[0]}>
            {plural(plan.problems.length, "problem")}
          </Badge>
        ) : null}
      </CardFooter>
    </Card>
  )
}

function BrokenCard({ entry }: { entry: BrokenSummary }) {
  return (
    <Alert variant="destructive" className="w-full">
      <WarningCircleIcon />
      <AlertTitle>
        <span className="font-mono">{entry.id}/</span> can’t be read
      </AlertTitle>
      <AlertDescription>
        <p>Fix the file and save it; this page updates on its own.</p>
        <ul className="list-disc pl-4">
          {entry.errors.slice(0, 6).map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  )
}

function IndexPending() {
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-4 w-80" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((index) => (
          <Skeleton key={index} className="h-48" />
        ))}
      </div>
    </div>
  )
}
