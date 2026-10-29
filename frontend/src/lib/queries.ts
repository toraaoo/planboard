import * as React from "react"
import {
  QueryClient,
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { useRouter } from "@tanstack/react-router"

import { api, type PlanPayload, type TaskStatus } from "@/lib/api"
import { STATUS_LABEL } from "@/lib/plan"
import { toast } from "@/components/ui/toast"

const POLL_MS = 2000

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      // The server is on this machine: navigator.onLine says nothing about it.
      queries: { networkMode: "always", staleTime: Infinity, retry: false },
      mutations: { networkMode: "always" },
    },
  })
}

export const plansQuery = queryOptions({
  queryKey: ["plans"],
  queryFn: api.plans,
})

export function planQuery(planId: string) {
  return queryOptions({
    queryKey: ["plans", planId],
    queryFn: () => api.plan(planId),
  })
}

/** Polls the workspace version and refetches plans when a file changes on disk. */
export function useWorkspaceSync() {
  const queryClient = useQueryClient()
  const router = useRouter()
  const seen = React.useRef<string | null>(null)
  const version = useQuery({
    queryKey: ["version"],
    queryFn: api.version,
    refetchInterval: POLL_MS,
    staleTime: 0,
  })
  const offline = version.isError

  React.useEffect(() => {
    const current = version.data?.version
    if (!current) return
    if (seen.current !== null && seen.current !== current) {
      void queryClient.invalidateQueries({ queryKey: ["plans"] })
    }
    seen.current = current
  }, [version.data?.version, queryClient])

  const wasOffline = React.useRef(false)
  React.useEffect(() => {
    if (wasOffline.current && !offline) {
      void queryClient.invalidateQueries({ queryKey: ["plans"] })
      void router.invalidate()
    }
    wasOffline.current = offline
  }, [offline, queryClient, router])

  return { offline }
}

export function useSetTaskStatus(planId: string) {
  const queryClient = useQueryClient()
  const key = planQuery(planId).queryKey

  return useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: TaskStatus }) =>
      api.setTaskStatus(planId, taskId, status),
    onMutate: async ({ taskId, status }) => {
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData(key)
      queryClient.setQueryData(key, (payload) =>
        payload?.kind === "plan" ? withStatus(payload, taskId, status) : payload
      )
      return { previous }
    },
    onError: (error, { taskId }, context) => {
      const payload = context?.previous
      queryClient.setQueryData(key, payload)
      const task =
        payload?.kind === "plan"
          ? payload.plan.tasks.find((candidate) => candidate.id === taskId)
          : undefined
      toast.add({
        type: "error",
        title: task
          ? `${task.title} stayed in ${STATUS_LABEL[task.status]}`
          : "The task did not move",
        description: error.message,
      })
    },
    // A new version makes useWorkspaceSync refetch the plans once.
    onSuccess: ({ version }) => {
      queryClient.setQueryData(["version"], { version })
    },
  })
}

function withStatus(
  payload: PlanPayload,
  taskId: string,
  status: TaskStatus
): PlanPayload {
  return {
    ...payload,
    plan: {
      ...payload.plan,
      tasks: payload.plan.tasks.map((task) =>
        task.id === taskId ? { ...task, status } : task
      ),
    },
  }
}
