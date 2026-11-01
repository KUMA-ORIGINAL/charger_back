import { type QueryClient, queryOptions, useSuspenseQuery } from '@tanstack/react-query'
import { notFound } from '@tanstack/react-router'
import { getStaffMetaQueryKey, staffMeta } from '@/shared/api/generated/staff'
import type { ResourceMeta } from './types'

/** Описание ресурсов меняется только с деплоем бэкенда — кэшируем на сессию. */
export const metaQuery = () =>
  queryOptions({
    queryKey: getStaffMetaQueryKey(),
    queryFn: ({ signal }) => staffMeta({ signal }),
    staleTime: Number.POSITIVE_INFINITY,
  })

export function useResources(): ResourceMeta[] {
  return useSuspenseQuery(metaQuery()).data.resources
}

/** Для маршрутов, чей loader уже вызвал `requireResource`: ресурс точно есть. */
export function useResourceMeta(key: string): ResourceMeta {
  const meta = useResources().find((resource) => resource.key === key)
  if (!meta) throw new Error(`Ресурс ${key} не загружен`)
  return meta
}

/** loader маршрута ресурса: неизвестный или недоступный раздел — 404. */
export async function requireResource(queryClient: QueryClient, key: string) {
  const { resources } = await queryClient.ensureQueryData(metaQuery())
  const meta = resources.find((resource) => resource.key === key)
  if (!meta) throw notFound()
  return meta
}
