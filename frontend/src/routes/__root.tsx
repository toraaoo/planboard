import type { QueryClient } from "@tanstack/react-query"
import {
  createRootRouteWithContext,
  HeadContent,
  Outlet,
} from "@tanstack/react-router"

import { useWorkspaceSync } from "@/lib/queries"
import { NotFound, RouteError } from "@/components/route-states"
import { SiteHeader } from "@/components/site-header"

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({ meta: [{ title: "planboard" }] }),
  component: RootLayout,
  notFoundComponent: NotFound,
  errorComponent: RouteError,
})

function RootLayout() {
  const { offline } = useWorkspaceSync()
  return (
    <>
      <HeadContent />
      <a
        href="#main"
        onClick={(event) => {
          event.preventDefault()
          document.getElementById("main")?.focus()
        }}
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>
      <div className="flex min-h-svh flex-col">
        <SiteHeader offline={offline} />
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 outline-none sm:px-6 sm:py-10">
          <Outlet />
        </main>
      </div>
    </>
  )
}
