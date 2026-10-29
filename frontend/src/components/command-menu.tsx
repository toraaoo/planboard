import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { useMatch, useNavigate } from "@tanstack/react-router"
import {
  FileTextIcon,
  GraphIcon,
  KanbanIcon,
  MagnifyingGlassIcon,
  MonitorIcon,
  MoonIcon,
  SunIcon,
} from "@phosphor-icons/react"

import { planQuery, plansQuery } from "@/lib/queries"
import { position } from "@/lib/plan"
import { useTheme } from "@/components/theme-provider"
import { STATUS_ICON } from "@/components/status"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import { Kbd, KbdGroup } from "@/components/ui/kbd"

const VIEWS = [
  { id: "document", label: "Document", icon: FileTextIcon },
  { id: "board", label: "Board", icon: KanbanIcon },
  { id: "graph", label: "Graph", icon: GraphIcon },
] as const

export function CommandMenu() {
  const [open, setOpen] = React.useState(false)
  const navigate = useNavigate()
  const { setTheme } = useTheme()
  const planMatch = useMatch({ from: "/plan/$", shouldThrow: false })
  const planId = planMatch?.params._splat
  const plans = useQuery({ ...plansQuery, enabled: open })
  const current = useQuery({ ...planQuery(planId ?? ""), enabled: open && !!planId })
  const payload = current.data?.kind === "plan" ? current.data : undefined

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setOpen((value) => !value)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  const run = (action: () => unknown) => {
    setOpen(false)
    void action()
  }

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        className="text-muted-foreground"
        aria-keyshortcuts="Control+K Meta+K"
      >
        <MagnifyingGlassIcon data-icon="inline-start" />
        <span className="hidden sm:inline">Search</span>
        <KbdGroup className="hidden sm:inline-flex">
          <Kbd>Ctrl</Kbd>
          <Kbd>K</Kbd>
        </KbdGroup>
      </Button>
      <CommandDialog
        open={open}
        onOpenChange={setOpen}
        title="Search planboard"
        description="Jump to a plan, a task or a view."
      >
        <Command>
          <CommandInput placeholder="Search plans and tasks…" />
          <CommandList>
            <CommandEmpty>Nothing matches.</CommandEmpty>
            {payload ? (
              <>
                <CommandGroup heading={payload.plan.title}>
                  {VIEWS.map((view) => (
                    <CommandItem
                      key={view.id}
                      value={`view ${view.label}`}
                      onSelect={() =>
                        run(() =>
                          navigate({ to: "/plan/$", params: { _splat: payload.id }, search: { view: view.id } })
                        )
                      }
                    >
                      <view.icon />
                      {view.label}
                    </CommandItem>
                  ))}
                  {payload.plan.tasks.map((task, index) => {
                    const StatusGlyph = STATUS_ICON[task.status]
                    return (
                      <CommandItem
                        key={task.id}
                        value={`task ${task.id} ${task.title}`}
                        onSelect={() =>
                          run(() =>
                            navigate({
                              to: "/plan/$",
                              params: { _splat: payload.id },
                              search: (prev) => ({ ...prev, task: task.id }),
                            })
                          )
                        }
                      >
                        <StatusGlyph />
                        <span className="font-mono text-muted-foreground">{position(index)}</span>
                        {task.title}
                      </CommandItem>
                    )
                  })}
                </CommandGroup>
                <CommandSeparator />
              </>
            ) : null}
            <CommandGroup heading="Plans">
              {plans.data?.plans.map((plan) => (
                <CommandItem
                  key={plan.id}
                  value={`plan ${plan.id} ${plan.title} ${plan.tags.join(" ")}`}
                  onSelect={() => run(() => navigate({ to: "/plan/$", params: { _splat: plan.id } }))}
                >
                  <FileTextIcon />
                  {plan.title}
                  <span className="ml-auto font-mono text-muted-foreground">{plan.id}</span>
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
            <CommandGroup heading="Theme">
              <CommandItem value="theme light" onSelect={() => run(() => setTheme("light"))}>
                <SunIcon />
                Light
              </CommandItem>
              <CommandItem value="theme dark" onSelect={() => run(() => setTheme("dark"))}>
                <MoonIcon />
                Dark
              </CommandItem>
              <CommandItem value="theme system" onSelect={() => run(() => setTheme("system"))}>
                <MonitorIcon />
                System
              </CommandItem>
            </CommandGroup>
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  )
}
