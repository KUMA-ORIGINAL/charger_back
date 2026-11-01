import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, notFound } from '@tanstack/react-router'
import { detailQuery } from '@/features/resources/api'
import { ResourceForm } from '@/features/resources/components/resource-form'
import { requireResource, useResourceMeta } from '@/features/resources/meta'
import { ApiError } from '@/shared/api/http'

export const Route = createFileRoute('/_app/r/$resource/$id')({
  params: {
    parse: ({ resource, id }) => {
      const parsed = Number(id)
      if (!Number.isInteger(parsed) || parsed <= 0) throw notFound()
      return { resource, id: parsed }
    },
    stringify: ({ resource, id }) => ({ resource, id: String(id) }),
  },
  loader: async ({ context, params }) => {
    await requireResource(context.queryClient, params.resource)
    try {
      await context.queryClient.ensureQueryData(detailQuery(params.resource, params.id))
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) throw notFound()
      throw error
    }
  },
  component: DetailRoute,
})

function DetailRoute() {
  const { resource, id } = Route.useParams()
  const meta = useResourceMeta(resource)
  const { data: row } = useSuspenseQuery(detailQuery(resource, id))
  // key: форма пересоздаётся при переходе к другому объекту.
  return <ResourceForm key={`${resource}-${id}`} meta={meta} row={row} />
}
