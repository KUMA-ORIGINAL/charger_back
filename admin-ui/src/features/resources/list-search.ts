/**
 * Состояние списка живёт в URL: ссылку на отфильтрованный список можно
 * отправить коллеге. Известные ключи — пагинация, поиск, сортировка; все
 * остальные — фильтры в синтаксисе API (`status=1`, `created_at__gte=…`).
 */

export interface ListSearch {
  page?: number
  page_size?: number
  search?: string
  ordering?: string
  /** Необязательно, чтобы ссылки на список не требовали параметров. */
  filters?: Record<string, string>
}

const RESERVED = new Set(['page', 'page_size', 'search', 'ordering'])

function positiveInt(value: unknown): number | undefined {
  const number = typeof value === 'number' ? value : Number(value)
  return Number.isInteger(number) && number > 0 ? number : undefined
}

function text(value: unknown): string | undefined {
  if (value === undefined || value === null || value === '') return undefined
  return String(value)
}

/** `validateSearch` маршрута списка: сырые параметры → ListSearch. */
export function parseListSearch(raw: Record<string, unknown>): ListSearch {
  // Роутер валидирует и плоский поиск из URL, и вложенный `{filters}` из
  // navigate() — до того, как middleware маршрута его расплющит. Вложенный
  // главнее: в состоянии роутера рядом с ним лежат и старые плоские ключи из
  // адреса, и снятый фильтр иначе вернулся бы из них.
  // Ключ `filters` есть (даже `undefined` — «снять все») — значит, это navigate().
  const source = 'filters' in raw ? ((raw.filters ?? {}) as Record<string, unknown>) : raw
  const filters: Record<string, string> = {}
  for (const [key, value] of Object.entries(source)) {
    if (RESERVED.has(key) || key === 'filters') continue
    const parsed = text(value)
    if (parsed !== undefined) filters[key] = parsed
  }
  return {
    page: positiveInt(raw.page),
    page_size: positiveInt(raw.page_size),
    search: text(raw.search),
    ordering: text(raw.ordering),
    filters,
  }
}

/** Обратно в плоские параметры URL (пустые значения отбрасываются). */
export function flattenListSearch(search: ListSearch): Record<string, string | number> {
  const result: Record<string, string | number> = {}
  if (search.page && search.page > 1) result.page = search.page
  if (search.page_size) result.page_size = search.page_size
  if (search.search) result.search = search.search
  if (search.ordering) result.ordering = search.ordering
  for (const [key, value] of Object.entries(search.filters ?? {})) {
    if (value !== '') result[key] = asNumberIfExact(value)
  }
  return result
}

/**
 * Роутер пишет строку "3" в URL как `%223%22`, чтобы не спутать с числом.
 * Отдаём числом, если оно превращается обратно в ту же строку (`0555` — нет).
 */
function asNumberIfExact(value: string): string | number {
  const number = Number(value)
  return Number.isFinite(number) && String(number) === value ? number : value
}

/**
 * Последний поиск списка каждого раздела — чтобы «← Заказы» из карточки
 * возвращал к тому же фильтру и странице, а не к началу списка. Только в
 * памяти вкладки: после перезагрузки начинаем с чистого списка.
 */
const lastSearch = new Map<string, ListSearch>()

export function rememberListSearch(resource: string, search: ListSearch) {
  lastSearch.set(resource, search)
}

export function lastListSearch(resource: string): ListSearch {
  return lastSearch.get(resource) ?? {}
}

/** Те же параметры для запроса к API. */
export function toQueryString(search: ListSearch): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(flattenListSearch(search))) {
    params.set(key, String(value))
  }
  return params.toString()
}
