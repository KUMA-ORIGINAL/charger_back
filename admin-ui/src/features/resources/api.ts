import { keepPreviousData, queryOptions } from '@tanstack/react-query'
import { apiFetch, apiFetchMaybeFile, type DownloadedFile } from '@/shared/api/http'
import { type ListSearch, toQueryString } from './list-search'
import type { ActionResult, Page, RelatedValue, Row } from './types'

/**
 * CRUD любого ресурса staff-API. Тип строки общий (Row): форма данных описана
 * в /meta/, а не в OpenAPI — так новый ресурс не требует кода на фронте.
 */

const BASE = '/api/staff/v1/resources'

export const resourceKeys = {
  all: (key: string) => ['resource', key] as const,
  list: (key: string, search: ListSearch) => ['resource', key, 'list', search] as const,
  detail: (key: string, id: number) => ['resource', key, 'detail', id] as const,
  lookup: (key: string, field: string, search: string, ids: readonly number[]) =>
    ['resource', key, 'lookup', field, search, ids] as const,
}

/** `refreshSeconds` — автообновление списка (новые заказы), 0 — выключено. */
export function listQuery(key: string, search: ListSearch, refreshSeconds = 0) {
  const qs = toQueryString(search)
  return queryOptions({
    queryKey: resourceKeys.list(key, search),
    queryFn: () => apiFetch<Page<Row>>(`${BASE}/${key}/${qs ? `?${qs}` : ''}`),
    placeholderData: keepPreviousData,
    refetchInterval: refreshSeconds > 0 ? refreshSeconds * 1000 : false,
  })
}

export function detailQuery(key: string, id: number) {
  return queryOptions({
    queryKey: resourceKeys.detail(key, id),
    queryFn: () => apiFetch<Row>(`${BASE}/${key}/${id}/`),
  })
}

export function lookupQuery(
  key: string,
  field: string,
  search: string,
  ids: readonly number[] = [],
) {
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  if (ids.length) params.set('ids', ids.join(','))
  return queryOptions({
    queryKey: resourceKeys.lookup(key, field, search, ids),
    queryFn: () =>
      apiFetch<{ results: RelatedValue[] }>(`${BASE}/${key}/lookup/${field}/?${params}`).then(
        (data) => data.results,
      ),
    staleTime: 60_000,
  })
}

/** JSON, а если есть файлы — multipart (DRF принимает оба). */
function encode(values: Record<string, unknown>): RequestInit {
  const hasFile = Object.values(values).some((value) => value instanceof File)
  if (!hasFile) {
    return { body: JSON.stringify(values), headers: { 'Content-Type': 'application/json' } }
  }
  const form = new FormData()
  for (const [name, value] of Object.entries(values)) {
    if (value === undefined) continue
    if (Array.isArray(value)) for (const item of value) form.append(name, String(item))
    else if (value instanceof File) form.append(name, value)
    else form.append(name, value === null ? '' : String(value))
  }
  return { body: form }
}

export function createRow(key: string, values: Record<string, unknown>) {
  return apiFetch<Row>(`${BASE}/${key}/`, { method: 'POST', ...encode(values) })
}

export function updateRow(key: string, id: number, values: Record<string, unknown>) {
  return apiFetch<Row>(`${BASE}/${key}/${id}/`, { method: 'PATCH', ...encode(values) })
}

export function deleteRow(key: string, id: number) {
  return apiFetch<void>(`${BASE}/${key}/${id}/`, { method: 'DELETE' })
}

/** `data` — ввод формы действия (если у действия есть `form`). */
export function runAction(key: string, name: string, id: number, data?: Record<string, unknown>) {
  return apiFetchMaybeFile<ActionResult>(`${BASE}/${key}/${id}/actions/${name}/`, {
    method: 'POST',
    body: JSON.stringify(data ? { data } : {}),
    headers: { 'Content-Type': 'application/json' },
  })
}

export function runBulkAction(
  key: string,
  name: string,
  ids: number[],
  data?: Record<string, unknown>,
) {
  return apiFetchMaybeFile<ActionResult>(`${BASE}/${key}/bulk-actions/${name}/`, {
    method: 'POST',
    body: JSON.stringify(data ? { ids, data } : { ids }),
    headers: { 'Content-Type': 'application/json' },
  })
}

export function exportRows(
  key: string,
  search: ListSearch,
): Promise<ActionResult | DownloadedFile> {
  const qs = toQueryString({ ...search, page: undefined, page_size: undefined })
  return apiFetchMaybeFile<ActionResult>(`${BASE}/${key}/export/${qs ? `?${qs}` : ''}`)
}
