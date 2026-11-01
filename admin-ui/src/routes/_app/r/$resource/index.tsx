import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { ResourceList } from '@/features/resources/components/resource-list'
import {
  flattenListSearch,
  type ListSearch,
  parseListSearch,
} from '@/features/resources/list-search'
import { requireResource, useResourceMeta } from '@/features/resources/meta'

export const Route = createFileRoute('/_app/r/$resource/')({
  validateSearch: (search: Record<string, unknown>): ListSearch => parseListSearch(search),
  // Плоские параметры в URL: ?status=1&page=2, а не ?filters={...}.
  search: {
    middlewares: [({ search, next }) => flattenListSearch(next(search)) as unknown as ListSearch],
  },
  loader: ({ context, params }) => requireResource(context.queryClient, params.resource),
  component: ResourceListRoute,
})

function ResourceListRoute() {
  const { resource } = Route.useParams()
  const search = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const meta = useResourceMeta(resource)
  return (
    <ResourceList
      key={resource}
      meta={meta}
      search={search}
      onSearchChange={(next) => navigate({ search: next })}
    />
  )
}
