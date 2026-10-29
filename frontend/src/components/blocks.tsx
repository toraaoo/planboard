import * as React from "react"
import { Link } from "@tanstack/react-router"
import {
  ArrowsOutIcon,
  CheckIcon,
  CopyIcon,
  InfoIcon,
  WarningIcon,
} from "@phosphor-icons/react"

import type { Block, Diagram, ListItem } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Code, Inline } from "@/components/inline"
import { MermaidCanvas, useMermaid } from "@/components/mermaid"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface BlockContext {
  planId: string
}

function Caption({ text, planId }: { text?: string; planId: string }) {
  if (!text) return null
  return (
    <figcaption className="text-xs/relaxed text-muted-foreground">
      <Inline text={text} planId={planId} />
    </figcaption>
  )
}

function ListItems({
  items,
  ordered,
  planId,
}: {
  items: Array<string | ListItem>
  ordered?: boolean
  planId: string
}) {
  const List = ordered ? "ol" : "ul"
  return (
    <List
      className={cn(
        "flex flex-col gap-1.5 pl-5 marker:text-muted-foreground",
        ordered ? "list-decimal" : "list-disc"
      )}
    >
      {items.map((item, index) =>
        typeof item === "string" ? (
          <li key={index}>
            <Inline text={item} planId={planId} />
          </li>
        ) : (
          <li key={index} className="flex flex-col gap-1.5">
            <span>
              <Inline text={item.text} planId={planId} />
            </span>
            {item.items?.length ? (
              <ListItems items={item.items} planId={planId} />
            ) : null}
          </li>
        )
      )}
    </List>
  )
}

function CopyButton({ text }: { text: string }) {
  const [state, setState] = React.useState<"idle" | "copied" | "failed">("idle")
  React.useEffect(() => {
    if (state === "idle") return
    const timer = setTimeout(() => setState("idle"), 1400)
    return () => clearTimeout(timer)
  }, [state])
  const label = { idle: "Copy code", copied: "Copied", failed: "Copy failed" }[state]
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={label}
            onClick={() =>
              navigator.clipboard.writeText(text).then(
                () => setState("copied"),
                () => setState("failed")
              )
            }
          />
        }
      >
        {state === "copied" ? <CheckIcon /> : <CopyIcon />}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

function DiagramFigure({
  diagram,
  caption,
  anchored,
  context,
}: {
  diagram: Diagram
  caption?: string
  anchored: boolean
  context: BlockContext
}) {
  const own = diagram.plan_id === context.planId
  const [expanded, setExpanded] = React.useState(false)
  const state = useMermaid(diagram.source ?? "")

  return (
    <figure
      id={anchored ? `diagram-${diagram.diagram_id}` : undefined}
      className="flex scroll-mt-20 flex-col gap-2 data-[highlight=true]:ring-2 data-[highlight=true]:ring-ring"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[0.7rem] text-muted-foreground uppercase">
        <Link
          to="/plan/$"
          params={{ _splat: diagram.plan_id }}
          search={{ at: diagram.diagram_id }}
          aria-label={`Link to diagram ${diagram.diagram_id}`}
          className="hover:text-foreground"
        >
          Fig · {diagram.diagram_id}
        </Link>
        {diagram.file ? (
          <span className="normal-case">
            from <Code>{diagram.file}</Code>
          </span>
        ) : null}
        {own ? null : (
          <span className="normal-case">
            from{" "}
            <Link
              to="/plan/$"
              params={{ _splat: diagram.plan_id }}
              className="underline underline-offset-4 hover:text-foreground"
            >
              {diagram.plan_title ?? diagram.plan_id}
            </Link>
          </span>
        )}
      </div>
      <div className="relative border bg-card p-4">
        {diagram.error ? (
          <p role="alert" className="text-xs text-destructive">
            This diagram can’t be shown: {diagram.error}.
          </p>
        ) : (
          <>
            <MermaidCanvas state={state} label={diagram.alt} />
            {state.kind === "ready" ? (
              <Button
                variant="outline"
                size="icon-sm"
                className="absolute top-2 right-2"
                aria-label={`Expand diagram: ${diagram.alt}`}
                onClick={() => setExpanded(true)}
              >
                <ArrowsOutIcon />
              </Button>
            ) : null}
          </>
        )}
      </div>
      <Caption text={caption} planId={context.planId} />
      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-h-[90svh] w-[min(96vw,1400px)] max-w-none overflow-auto sm:max-w-none">
          <DialogHeader>
            <DialogTitle>Fig · {diagram.diagram_id}</DialogTitle>
            <DialogDescription>{diagram.alt}</DialogDescription>
          </DialogHeader>
          <MermaidCanvas
            state={state}
            label={diagram.alt}
            className="[&_svg]:max-w-none! [&_svg]:min-w-full"
          />
        </DialogContent>
      </Dialog>
    </figure>
  )
}

function BlockView({
  block,
  anchored,
  context,
}: {
  block: Block
  anchored: boolean
  context: BlockContext
}) {
  const { planId } = context
  switch (block.type) {
    case "heading":
      return <h3 className="pt-2 font-heading text-base font-semibold">{block.text}</h3>
    case "text":
      return (
        <p className="text-pretty">
          <Inline text={block.text} planId={planId} />
        </p>
      )
    case "list":
      return <ListItems items={block.items} ordered={block.ordered} planId={planId} />
    case "table":
      return (
        <figure className="flex flex-col gap-2">
          <div
            role="region"
            tabIndex={0}
            aria-label={block.caption ?? block.columns.join(", ")}
            className="border"
          >
            <Table>
              <TableHeader>
                <TableRow>
                  {block.columns.map((column) => (
                    <TableHead key={column}>{column}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {block.rows.map((row, rowIndex) => (
                  <TableRow key={rowIndex}>
                    {row.map((cell, index) => {
                      const content =
                        cell === null ? (
                          <span aria-label="None" className="text-muted-foreground">
                            —
                          </span>
                        ) : (
                          <Inline text={cell} planId={planId} />
                        )
                      return index === 0 ? (
                        <TableHead key={index} scope="row" className="font-medium text-foreground">
                          {content}
                        </TableHead>
                      ) : (
                        <TableCell key={index} className="whitespace-normal">
                          {content}
                        </TableCell>
                      )
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Caption text={block.caption} planId={planId} />
        </figure>
      )
    case "callout": {
      const Icon = block.tone === "warning" ? WarningIcon : InfoIcon
      return (
        <Alert role="note">
          <Icon />
          <AlertTitle>{block.title}</AlertTitle>
          <AlertDescription>
            <Inline text={block.text} planId={planId} />
          </AlertDescription>
        </Alert>
      )
    }
    case "code":
      return (
        <figure className="flex flex-col gap-2">
          <div className="relative border bg-muted/50">
            <pre
              tabIndex={0}
              aria-label={block.language ? `${block.language} example` : "Code example"}
              className="overflow-x-auto p-4 pr-12 font-mono text-xs leading-relaxed"
            >
              <code>{block.code}</code>
            </pre>
            <div className="absolute top-1.5 right-1.5">
              <CopyButton text={block.code} />
            </div>
          </div>
          <Caption text={block.caption} planId={planId} />
        </figure>
      )
    case "diagram":
      return (
        <DiagramFigure
          diagram={block.diagram}
          caption={block.caption}
          anchored={anchored}
          context={context}
        />
      )
    default:
      return (
        <Alert variant="destructive">
          <AlertTitle>
            Unknown block type “{(block as { type: string }).type}”.
          </AlertTitle>
        </Alert>
      )
  }
}

/** Blocks of one section; `anchors` holds the indexes of diagrams that carry an id. */
export function Blocks({
  blocks,
  anchors,
  context,
}: {
  blocks: Block[]
  anchors: Set<number>
  context: BlockContext
}) {
  return (
    <>
      {blocks.map((block, index) => (
        <BlockView key={index} block={block} anchored={anchors.has(index)} context={context} />
      ))}
    </>
  )
}

/** The first block showing each of this plan's diagrams carries its anchor. */
export function diagramAnchors(planId: string, sections: Array<{ blocks: Block[] }>) {
  const seen = new Set<string>()
  return sections.map((section) => {
    const anchors = new Set<number>()
    section.blocks.forEach((block, index) => {
      if (block.type !== "diagram" || block.diagram.plan_id !== planId) return
      if (seen.has(block.diagram.diagram_id)) return
      seen.add(block.diagram.diagram_id)
      anchors.add(index)
    })
    return anchors
  })
}
