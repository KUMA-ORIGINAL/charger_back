import type {
  ActionField,
  ActionMeta,
  ColumnMeta,
  FieldMeta,
  FilterMeta,
  InlineMeta,
  LinkMeta,
  ResourceMeta,
} from '@/shared/api/generated/model'

export type {
  ActionField,
  ActionMeta,
  ColumnMeta,
  FieldMeta,
  FilterMeta,
  InlineMeta,
  LinkMeta,
  ResourceMeta,
}

/** Связь в ответе API: `{id, label}`; в запрос уходит только id. */
export interface RelatedValue {
  id: number
  label: string
}

/** Строка ресурса: поля приходят по именам из meta, их состав зависит от роли. */
export type Row = { id: number } & Record<string, unknown>

/**
 * Detail-действия, доступные именно этому объекту (`_actions` в карточке), с
 * формой, если она зависит от объекта. Нет ключа — действие объекту недоступно.
 */
export type ObjectActions = Record<string, { form: ActionField[] | null }>

/** Ссылка из вычисляемого поля `link`: на список с фильтрами, карточку или особый экран. */
export interface LinkValue {
  label: string
  resource?: string
  filters?: Record<string, string | number>
  id?: number
  to?: string
  search?: Record<string, string | number>
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  page_size: number
  results: T[]
  /** Строк в каждой вкладке (`list_tabs` в meta): значение поля → число. */
  tab_counts?: Record<string, number>
}

export interface ActionResult {
  message: string
  level: 'success' | 'info' | 'warning' | 'error'
  /** Действие создало объект — открыть его карточку. */
  open?: { resource: string; id: number }
}

export function isRelated(value: unknown): value is RelatedValue {
  return typeof value === 'object' && value !== null && 'id' in value && 'label' in value
}
