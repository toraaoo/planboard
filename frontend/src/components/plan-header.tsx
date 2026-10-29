import { Link } from "@tanstack/react-router"
import { WarningCircleIcon } from "@phosphor-icons/react"

import type { PlanPayload } from "@/lib/api"
import { formatDate, summarizeTasks } from "@/lib/plan"
import { Code, Inline } from "@/components/inline"
import { PlanStatusBadge, ProgressStrip, Tally } from "@/components/status"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <dt className="font-mono text-[0.7rem] text-muted-foreground uppercase">{label}</dt>
      <dd className="text-xs">{children}</dd>
    </div>
  )
}

export function PlanHeader({ payload }: { payload: PlanPayload }) {
  const { plan } = payload
  return (
    <header className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <p className="font-mono text-[0.7rem] text-muted-foreground">data/{payload.path}</p>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-heading text-2xl font-semibold tracking-tight text-balance">
            {plan.title}
          </h1>
          <PlanStatusBadge status={plan.status} />
        </div>
        <p className="max-w-[72ch] text-sm/7 text-pretty text-muted-foreground">
          <Inline text={plan.summary} planId={payload.id} />
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
        {plan.updated ? <Field label="Updated">{formatDate(plan.updated)}</Field> : null}
        {plan.branch ? (
          <Field label="Branch">
            <Code>{plan.branch}</Code>
          </Field>
        ) : null}
        {plan.tags.length ? (
          <Field label="Tags">
            <span className="flex flex-wrap gap-1">
              {plan.tags.map((tag) => (
                <Badge key={tag} variant="secondary">
                  {tag}
                </Badge>
              ))}
            </span>
          </Field>
        ) : null}
        <Field label="Depends on">
          {plan.dependsOn.length ? (
            <span className="flex flex-wrap gap-x-2 gap-y-1">
              {plan.dependsOn.map((ref) => {
                const resolution = payload.resolved[ref]
                return resolution && resolution.state !== "missing" ? (
                  <Link
                    key={ref}
                    to="/plan/$"
                    params={{ _splat: resolution.plan_id }}
                    search={{ task: resolution.task_id ?? undefined }}
                    className="underline underline-offset-4"
                  >
                    {resolution.plan_title ?? ref}
                  </Link>
                ) : (
                  <Code key={ref}>{ref}</Code>
                )
              })}
            </span>
          ) : (
            <span className="text-muted-foreground">Nothing outside this plan</span>
          )}
        </Field>
      </dl>
      {plan.tasks.length ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium">{summarizeTasks(plan.tasks)}</p>
          <ProgressStrip tasks={plan.tasks} planId={payload.id} />
          <Tally tasks={plan.tasks} />
        </div>
      ) : null}
      {payload.problems.length ? (
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertTitle>Needs attention</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">
              {payload.problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}
    </header>
  )
}
