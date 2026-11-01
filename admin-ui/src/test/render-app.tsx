import { QueryClient } from '@tanstack/react-query'
import { createMemoryHistory, createRouter, RouterProvider } from '@tanstack/react-router'
import { render } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { Providers } from '@/app/providers'
import { routeTree } from '@/routeTree.gen'
import type { ResourceMeta } from '@/shared/api/generated/model'
import { me } from './fixtures'
import { server } from './msw-server'

export const API = '/api/staff/v1'

/** Всё приложение с memory-историей: проверяются и маршруты, и данные. */
export function renderApp(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const history = createMemoryHistory({ initialEntries: [path] })
  const router = createRouter({ routeTree, basepath: '/panel', context: { queryClient }, history })
  render(
    <Providers queryClient={queryClient}>
      <RouterProvider router={router} />
    </Providers>,
  )
  return { router, history, queryClient }
}

/** Вошедший владелец с заданными ресурсами в /meta/. */
export function signIn(resources: ResourceMeta[]) {
  server.use(
    http.get(`${API}/auth/me/`, () => HttpResponse.json(me)),
    http.get(`${API}/meta/`, () => HttpResponse.json({ resources })),
  )
}
