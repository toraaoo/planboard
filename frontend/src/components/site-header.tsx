import { useQuery } from "@tanstack/react-query"
import { Link, useMatch } from "@tanstack/react-router"
import {
  MonitorIcon,
  MoonIcon,
  KanbanIcon,
  SunIcon,
  WifiSlashIcon,
} from "@phosphor-icons/react"

import { planQuery } from "@/lib/queries"
import { CommandMenu } from "@/components/command-menu"
import { useTheme } from "@/components/theme-provider"
import { Badge } from "@/components/ui/badge"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

function Crumbs() {
  const planMatch = useMatch({ from: "/plan/$", shouldThrow: false })
  const planId = planMatch?.params._splat
  const plan = useQuery({ ...planQuery(planId ?? ""), enabled: !!planId })
  const payload = plan.data
  const folder = payload?.kind === "plan" ? payload.folder : undefined
  const title = payload?.kind === "plan" ? payload.plan.title : planId

  return (
    <Breadcrumb className="min-w-0">
      <BreadcrumbList className="flex-nowrap">
        <BreadcrumbItem className="whitespace-nowrap">
          {planId ? (
            <BreadcrumbLink render={<Link to="/" />}>All plans</BreadcrumbLink>
          ) : (
            <BreadcrumbPage>All plans</BreadcrumbPage>
          )}
        </BreadcrumbItem>
        {folder ? (
          <>
            <BreadcrumbSeparator />
            <BreadcrumbItem className="hidden sm:inline-flex">
              <BreadcrumbLink render={<Link to="/" search={{ q: folder }} />}>{folder}</BreadcrumbLink>
            </BreadcrumbItem>
          </>
        ) : null}
        {planId ? (
          <>
            <BreadcrumbSeparator className={folder ? "hidden sm:inline-flex" : undefined} />
            <BreadcrumbItem className="min-w-0">
              <BreadcrumbPage className="truncate">{title}</BreadcrumbPage>
            </BreadcrumbItem>
          </>
        ) : null}
      </BreadcrumbList>
    </Breadcrumb>
  )
}

function ThemeMenu() {
  const { theme, setTheme } = useTheme()
  const Icon = { light: SunIcon, dark: MoonIcon, system: MonitorIcon }[theme]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label="Theme" />}>
        <Icon />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuGroup>
          <DropdownMenuLabel>Theme</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={theme} onValueChange={(value) => setTheme(value as typeof theme)}>
            <DropdownMenuRadioItem value="light">
              <SunIcon />
              Light
            </DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="dark">
              <MoonIcon />
              Dark
            </DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="system">
              <MonitorIcon />
              System
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function SiteHeader({ offline }: { offline: boolean }) {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Link to="/" className="flex shrink-0 items-center gap-2 font-mono text-sm font-semibold">
          <KanbanIcon weight="fill" aria-hidden="true" className="size-5" />
          planboard
        </Link>
        <Crumbs />
        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          {offline ? (
            <Tooltip>
              <TooltipTrigger render={<Badge variant="destructive" role="status" />}>
                <WifiSlashIcon data-icon="inline-start" />
                Offline
              </TooltipTrigger>
              <TooltipContent>
                The planboard server isn’t answering. This page reconnects on its own.
              </TooltipContent>
            </Tooltip>
          ) : null}
          <CommandMenu />
          <ThemeMenu />
        </div>
      </div>
    </header>
  )
}
