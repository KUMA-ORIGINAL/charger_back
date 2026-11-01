export const LOCALE = 'ru-RU'
export const TIME_ZONE = 'Asia/Bishkek'

const moneyFormatter = new Intl.NumberFormat(LOCALE, {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

const dateFormatter = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

const dateTimeFormatter = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

const timeFormatter = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
})

type DateInput = Date | string | number

function toDate(value: DateInput): Date {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) throw new RangeError(`Invalid date: ${String(value)}`)
  return date
}

/** Amount in KGS, e.g. `1 234,5 сом`. Accepts numbers or decimal strings from the API. */
export function formatMoney(amount: number | string): string {
  const value = typeof amount === 'string' ? Number(amount) : amount
  if (!Number.isFinite(value)) throw new RangeError(`Invalid amount: ${String(amount)}`)
  return `${moneyFormatter.format(value)} сом`
}

/** `21.10.2026` in Asia/Bishkek. */
export function formatDate(value: DateInput): string {
  return dateFormatter.format(toDate(value))
}

/** `21.10.2026, 14:05` in Asia/Bishkek. */
export function formatDateTime(value: DateInput): string {
  return dateTimeFormatter.format(toDate(value))
}

/** `14:05` in Asia/Bishkek. */
export function formatTime(value: DateInput): string {
  return timeFormatter.format(toDate(value))
}

/**
 * Номер Кыргызстана группами: `+996 705 133 000`. Принимает `+996…`, `996…` и
 * местный `0705…`; остальное возвращает как есть.
 */
export function formatPhone(value: string): string {
  const digits = value.replace(/\D/g, '')
  const local =
    digits.length === 12 && digits.startsWith('996')
      ? digits.slice(3)
      : digits.length === 10 && digits.startsWith('0')
        ? digits.slice(1)
        : null
  if (!local) return value
  return `+996 ${local.slice(0, 3)} ${local.slice(3, 6)} ${local.slice(6)}`
}
