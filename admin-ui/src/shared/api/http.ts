/**
 * Единственная точка выхода в сеть. Сессия Django в httpOnly-куке, поэтому
 * токенов нет: запросы идут с cookie того же домена, а меняющие данные
 * запросы несут `X-CSRFToken` из куки `csrftoken`.
 */

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

/** Ошибки валидации DRF: `{field: ["msg"]}` или `{detail: "msg"}`. */
export type FieldErrors = Record<string, string[]>

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown) {
    super(ApiError.describe(status, body))
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }

  /** Ошибки по полям формы (пусто, если ответ не про валидацию). */
  get fieldErrors(): FieldErrors {
    if (this.status !== 400 || !this.body || typeof this.body !== 'object') return {}
    const result: FieldErrors = {}
    for (const [key, value] of Object.entries(this.body as Record<string, unknown>)) {
      if (key === 'detail') continue
      result[key] = Array.isArray(value) ? value.map(String) : [String(value)]
    }
    return result
  }

  private static describe(status: number, body: unknown): string {
    if (body && typeof body === 'object' && 'detail' in body) return String(body.detail)
    if (status === 400) return 'Проверьте заполнение формы'
    if (status === 403) return 'Недостаточно прав'
    if (status === 404) return 'Не найдено'
    if (status >= 500) return 'Ошибка сервера, попробуйте позже'
    return `Ошибка ${status}`
  }
}

export function readCookie(name: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1)
}

function withDefaults(init: RequestInit = {}): RequestInit {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (UNSAFE_METHODS.has(method)) {
    const token = readCookie('csrftoken')
    if (token) headers.set('X-CSRFToken', decodeURIComponent(token))
  }
  return { ...init, method, headers, credentials: 'same-origin' }
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const type = response.headers.get('Content-Type') ?? ''
  return type.includes('application/json') ? response.json() : response.text()
}

/** Мутатор для Orval и ручных вызовов: JSON в ответе, ApiError при ошибке. */
export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, withDefaults(init))
  const body = await parseBody(response)
  if (!response.ok) throw new ApiError(response.status, body)
  return body as T
}

export interface DownloadedFile {
  blob: Blob
  filename: string
}

/** Запрос, который может вернуть файл (экспорт, QR) или JSON (сообщение действия). */
export async function apiFetchMaybeFile<T>(
  url: string,
  init?: RequestInit,
): Promise<T | DownloadedFile> {
  const response = await fetch(url, withDefaults(init))
  const type = response.headers.get('Content-Type') ?? ''
  if (!response.ok) throw new ApiError(response.status, await parseBody(response))
  if (type.includes('application/json')) return (await response.json()) as T
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const filename = /filename="?([^"]+)"?/.exec(disposition)?.[1] ?? 'download'
  return { blob: await response.blob(), filename }
}

export function isDownloadedFile(value: unknown): value is DownloadedFile {
  return typeof value === 'object' && value !== null && 'blob' in value && 'filename' in value
}

/** Отдаёт файл браузеру на сохранение. */
export function saveFile({ blob, filename }: DownloadedFile) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
