import * as React from "react"
import dagre from "@dagrejs/dagre"
import {
  Background,
  Controls,
  type Edge,
  Handle,
  MarkerType,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { Link } from "@tanstack/react-router"
import { CaretDownIcon, GraphIcon } from "@phosphor-icons/react"

import type { PlanPayload, TaskStatus } from "@/lib/api"
import { localTask, position, refLabel, STATUS_LABEL } from "@/lib/plan"
import { useResolvedTheme } from "@/lib/theme"
import { cn } from "@/lib/utils"
import { TaskStatusBadge, TaskStatusLabel } from "@/components/status"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"

const NODE_WIDTH = 232
const NODE_HEIGHT = 76
const FIT = { padding: 0.15, maxZoom: 1 }

type Target = { planId: string; taskId?: string }

type GraphNodeData = {
  caption: string
  title: string
  status?: TaskStatus
  kind: "task" | "plan" | "external"
  target?: Target
}

type GraphNode = Node<GraphNodeData, "plan-node">

function GraphNodeView({ data }: NodeProps<GraphNode>) {
  const body = (
    <>
      <span className="font-mono text-[0.7rem] text-muted-foreground">{data.caption}</span>
      <span className="line-clamp-2 text-xs font-medium">{data.title}</span>
      {data.status ? <TaskStatusBadge status={data.status} /> : null}
    </>
  )
  const className = cn(
    "flex h-full w-full flex-col items-start justify-center gap-1 bg-card px-3 py-2 text-left text-card-foreground ring-1 ring-foreground/10",
    data.kind === "external" && "border border-dashed bg-background text-muted-foreground ring-0",
    data.kind === "plan" && "bg-muted",
    data.target && "transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
  )
  return (
    <>
      <Handle type="target" position={Position.Left} className="invisible" isConnectable={false} />
      {data.target ? (
        <Link
          to="/plan/$"
          params={{ _splat: data.target.planId }}
          search={(prev) =>
            data.kind === "task" ? { ...prev, task: data.target?.taskId } : { task: data.target?.taskId }
          }
          className={className}
          style={{ width: NODE_WIDTH, height: NODE_HEIGHT }}
          aria-label={`${data.caption} ${data.title}${data.status ? `, ${STATUS_LABEL[data.status]}` : ""}. Open details.`}
        >
          {body}
        </Link>
      ) : (
        <div className={className} style={{ width: NODE_WIDTH, height: NODE_HEIGHT }}>
          {body}
        </div>
      )}
      <Handle type="source" position={Position.Right} className="invisible" isConnectable={false} />
    </>
  )
}

const nodeTypes = { "plan-node": GraphNodeView }

function buildGraph(payload: PlanPayload) {
  const nodes: GraphNode[] = []
  const edges: Edge[] = []
  const externals = new Map<string, string>()
  const add = (id: string, data: GraphNodeData) =>
    nodes.push({
      id,
      type: "plan-node",
      data,
      position: { x: 0, y: 0 },
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    })
  const link = (source: string, target: string, external: boolean) =>
    edges.push({
      id: `${source}->${target}`,
      source,
      target,
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
      style: external ? { strokeDasharray: "4 3" } : undefined,
    })

  const externalNode = (ref: string) => {
    let id = externals.get(ref)
    if (id) return id
    id = `e${externals.size}`
    externals.set(ref, id)
    const resolution = payload.resolved[ref]
    add(id, {
      kind: "external",
      caption: "Outside this plan",
      title: refLabel(ref, payload),
      target:
        resolution && resolution.state !== "missing"
          ? { planId: resolution.plan_id, taskId: resolution.task_id ?? undefined }
          : undefined,
    })
    return id
  }

  if (payload.plan.dependsOn.length || payload.dependents.some((d) => !d.target)) {
    add("plan", { kind: "plan", caption: "This plan", title: payload.plan.title })
  }
  payload.plan.tasks.forEach((task, index) =>
    add(`t:${task.id}`, {
      kind: "task",
      caption: `${position(index)} · ${task.id}`,
      title: task.title,
      status: task.status,
      target: { planId: payload.id, taskId: task.id },
    })
  )
  for (const ref of payload.plan.dependsOn) link(externalNode(ref), "plan", true)
  for (const task of payload.plan.tasks) {
    for (const ref of task.dependsOn) {
      const local = localTask(ref, payload)
      if (local) link(`t:${local.id}`, `t:${task.id}`, false)
      else link(externalNode(ref), `t:${task.id}`, true)
    }
  }
  payload.dependents.forEach((dependent, index) => {
    const id = `d${index}`
    add(id, {
      kind: "external",
      caption: "Needs this plan",
      title: `${dependent.plan_title}${dependent.task_id ? ` · ${dependent.title}` : ""}`,
      target: { planId: dependent.plan_id, taskId: dependent.task_id ?? undefined },
    })
    link(dependent.target ? `t:${dependent.target}` : "plan", id, true)
  })

  const layout = new dagre.graphlib.Graph()
  layout.setGraph({ rankdir: "LR", nodesep: 24, ranksep: 64, marginx: 16, marginy: 16 })
  layout.setDefaultEdgeLabel(() => ({}))
  for (const node of nodes) layout.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  for (const edge of edges) layout.setEdge(edge.source, edge.target)
  dagre.layout(layout)
  for (const node of nodes) {
    const { x, y } = layout.node(node.id)
    node.position = { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 }
  }
  return { nodes, edges }
}

function DependencyList({ payload }: { payload: PlanPayload }) {
  return (
    <Collapsible className="border">
      <CollapsibleTrigger render={<Button variant="ghost" className="w-full justify-between" />}>
        Dependencies as a list
        <CaretDownIcon data-icon="inline-end" />
      </CollapsibleTrigger>
      <CollapsibleContent className="px-4 pb-4">
        <ol className="flex flex-col gap-2 text-xs">
          {payload.plan.tasks.map((task, index) => (
            <li key={task.id} className="flex flex-wrap items-baseline gap-x-2">
              <Link
                to="/plan/$"
                params={{ _splat: payload.id }}
                search={(prev) => ({ ...prev, task: task.id })}
                className="font-medium underline-offset-4 hover:underline"
              >
                {position(index)} {task.title}
              </Link>
              <TaskStatusLabel status={task.status} />
              <span className="text-muted-foreground">
                {task.dependsOn.length
                  ? `after ${task.dependsOn.map((ref) => refLabel(ref, payload)).join(", ")}`
                  : "no dependencies"}
              </span>
            </li>
          ))}
        </ol>
      </CollapsibleContent>
    </Collapsible>
  )
}

export function GraphView({ payload }: { payload: PlanPayload }) {
  const theme = useResolvedTheme()
  const { nodes, edges } = React.useMemo(() => buildGraph(payload), [payload])

  if (!payload.plan.tasks.length) {
    return (
      <Empty className="border border-dashed">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <GraphIcon />
          </EmptyMedia>
          <EmptyTitle>Nothing to graph yet</EmptyTitle>
          <EmptyDescription>
            Tasks and their dependencies appear here once the plan has some.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        Arrows point from a dependency to the task that needs it. Dashed boxes and lines are
        outside this plan. Select a box to open it.
      </p>
      <div
        role="group"
        aria-label="Task dependency graph"
        className="h-[min(70svh,720px)] border"
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          colorMode={theme}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          fitView
          fitViewOptions={FIT}
          onInit={(instance) => void instance.fitView(FIT)}
          minZoom={0.2}
        >
          <Background gap={16} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <DependencyList payload={payload} />
    </div>
  )
}
