import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { createRouter } from '@tanstack/react-router'
import { checkSessionAfter } from '@/features/auth/session'
import { routeTree } from '@/routeTree.gen'
import { ErrorFallback, NotFound } from './fallbacks'

export interface RouterContext {
  queryClient: QueryClient
}

/** Сессия кончилась посреди работы — на вход, с возвратом на текущую страницу. */
const onApiError = (error: unknown) =>
  void checkSessionAfter(error, queryClient, () => {
    const { pathname, href } = router.state.location
    if (pathname === '/login') return
    void router.navigate({ to: '/login', search: { redirect: href } })
  })

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onApiError }),
  mutationCache: new MutationCache({ onError: onApiError }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export const router = createRouter({
  routeTree,
  basepath: '/panel',
  context: { queryClient } satisfies RouterContext,
  defaultPreload: 'intent',
  // TanStack Query owns caching; the router always re-runs loaders.
  defaultPreloadStaleTime: 0,
  scrollRestoration: true,
  defaultNotFoundComponent: NotFound,
  defaultErrorComponent: ErrorFallback,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
