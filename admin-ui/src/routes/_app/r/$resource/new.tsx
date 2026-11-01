import { createFileRoute, notFound } from '@tanstack/react-router'
import { ResourceForm } from '@/features/resources/components/resource-form'
import { requireResource, useResourceMeta } from '@/features/resources/meta'

export const Route = createFileRoute('/_app/r/$resource/new')({
  loader: async ({ context, params }) => {
    const meta = await requireResource(context.queryClient, params.resource)
    if (!meta.permissions.add) throw notFound()
  },
  component: NewRoute,
})

function NewRoute() {
  const { resource } = Route.useParams()
  const meta = useResourceMeta(resource)
  return <ResourceForm key={resource} meta={meta} />
}
