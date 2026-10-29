import { type ErrorComponentProps, Link, useRouter } from "@tanstack/react-router"
import { ArrowClockwiseIcon, PlugsIcon, QuestionIcon } from "@phosphor-icons/react"

import { Code } from "@/components/inline"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"

export function NotFound() {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <QuestionIcon />
        </EmptyMedia>
        <EmptyTitle>Nothing here</EmptyTitle>
        <EmptyDescription>This address doesn’t match a plan or page.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button variant="outline" render={<Link to="/" />}>
          Go to all plans
        </Button>
      </EmptyContent>
    </Empty>
  )
}

export function RouteError({ error }: ErrorComponentProps) {
  const router = useRouter()
  // fetch() rejects with a TypeError when nothing answers on the port.
  const unreachable = error instanceof TypeError
  const title = unreachable
    ? "The planboard server isn’t answering"
    : error instanceof Error
      ? error.message
      : "Something went wrong"
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <PlugsIcon />
        </EmptyMedia>
        <EmptyTitle>
          {title}
        </EmptyTitle>
        <EmptyDescription>
          {unreachable ? (
            <>
              Start it with <Code>planboard serve</Code>; this page reconnects on its own.
            </>
          ) : (
            "Try again, or go back to all plans."
          )}
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent className="flex-row justify-center">
        <Button variant="outline" onClick={() => void router.invalidate()}>
          <ArrowClockwiseIcon data-icon="inline-start" />
          Try again
        </Button>
        <Button variant="ghost" render={<Link to="/" />}>
          All plans
        </Button>
      </EmptyContent>
    </Empty>
  )
}
