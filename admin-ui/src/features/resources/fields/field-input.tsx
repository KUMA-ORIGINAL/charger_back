import { TIME_ZONE } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Input } from '@/shared/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { Switch } from '@/shared/ui/switch'
import { Textarea } from '@/shared/ui/textarea'
import { type FieldMeta, isRelated, type RelatedValue, type Row } from '../types'
import { RelationSelect } from './relation-select'

/**
 * Виджет поля формы по `type` из /meta/ и преобразования «значение API ⇄
 * значение формы». Новый тип поля добавляется здесь и в value-view.tsx.
 */

const EMPTY_CHOICE = '__empty__'
const CHOICE_BUTTONS_MAX = 6

/** Значение из ответа API → значение формы. */
export function toFormValue(field: FieldMeta, value: unknown): unknown {
  switch (field.type) {
    case 'fk':
      return isRelated(value) ? value.id : (value ?? null)
    case 'm2m':
      return Array.isArray(value) ? value.map((item) => (isRelated(item) ? item.id : item)) : []
    case 'boolean':
      return Boolean(value)
    case 'datetime':
      return typeof value === 'string' ? toLocalInput(value) : ''
    case 'image':
    case 'file':
      return value ?? null
    case 'multichoice':
      return Array.isArray(value) ? value : []
    case 'json':
      // JSON правят текстом; строку показываем как есть, остальное — отформатированным.
      if (value === null || value === undefined) return ''
      return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
    case 'password':
      // Пароль из API не приходит: пустое поле — «не менять».
      return ''
    default:
      return value ?? ''
  }
}

/** Текст поля JSON не разобрался — форма покажет ошибку под полем. */
export class JsonFieldError extends Error {
  readonly field: string

  constructor(field: string) {
    super('Некорректный JSON')
    this.field = field
  }
}

/** Значение формы → тело запроса; `undefined` — поле не отправлять. */
export function toApiValue(field: FieldMeta, value: unknown): unknown {
  if ((field.type === 'image' || field.type === 'file') && !(value instanceof File)) {
    return undefined // файл не меняли
  }
  if (field.type === 'password') {
    return value ? value : undefined
  }
  if (field.type === 'json' && typeof value === 'string') {
    if (!value.trim()) return null
    try {
      return JSON.parse(value)
    } catch {
      throw new JsonFieldError(field.name)
    }
  }
  if (value === '' && !['string', 'text', 'email', 'url', 'phone'].includes(field.type)) {
    return null
  }
  if (['integer', 'decimal', 'number'].includes(field.type) && value !== null) {
    return Number(value)
  }
  return value
}

/** Подписи выбранных связей из ответа API — чтобы не запрашивать их отдельно. */
export function knownRelated(row: Row | undefined, field: FieldMeta): RelatedValue[] {
  const value = row?.[field.name]
  if (isRelated(value)) return [value]
  if (Array.isArray(value)) return value.filter(isRelated)
  return []
}

const localParts = new Intl.DateTimeFormat('sv-SE', {
  timeZone: TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

/** ISO-время → `YYYY-MM-DDTHH:mm` по Бишкеку (бэкенд считает наивное время бишкекским). */
export function toLocalInput(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return localParts.format(date).replace(' ', 'T')
}

interface FieldInputProps {
  field: FieldMeta
  resource: string
  value: unknown
  onChange: (value: unknown) => void
  onBlur?: () => void
  invalid?: boolean
  known?: RelatedValue[]
  id: string
}

export function FieldInput({
  field,
  resource,
  value,
  onChange,
  onBlur,
  invalid,
  known,
  id,
}: FieldInputProps) {
  const common = { id, 'aria-invalid': invalid || undefined, onBlur }

  switch (field.type) {
    case 'boolean':
      return (
        <Switch id={id} checked={Boolean(value)} onCheckedChange={(checked) => onChange(checked)} />
      )
    case 'multichoice': {
      // Несколько значений (дни недели) — кнопками-переключателями в порядке choices.
      const selected = Array.isArray(value) ? value : []
      const toggle = (choice: unknown) => {
        const next = selected.some((item) => String(item) === String(choice))
          ? selected.filter((item) => String(item) !== String(choice))
          : [...selected, choice]
        const order = (item: unknown) =>
          field.choices?.findIndex((option) => String(option.value) === String(item)) ?? 0
        onChange([...next].sort((a, b) => order(a) - order(b)))
      }
      return (
        <fieldset
          id={id}
          aria-label={field.label}
          className="m-0 flex min-w-0 flex-wrap gap-2 border-0 p-0"
        >
          {field.choices?.map((choice) => {
            const active = selected.some((item) => String(item) === String(choice.value))
            return (
              <ToggleChip
                key={String(choice.value)}
                active={active}
                onClick={() => toggle(choice.value)}
              >
                {choice.label}
              </ToggleChip>
            )
          })}
        </fieldset>
      )
    }
    case 'password':
      return (
        <Input
          {...common}
          type="password"
          autoComplete="new-password"
          value={String(value ?? '')}
          onChange={(event) => onChange(event.target.value)}
        />
      )
    case 'choice':
      // Короткий список (статус заказа) — кнопками: все варианты на виду, один клик.
      if ((field.choices?.length ?? 0) <= CHOICE_BUTTONS_MAX) {
        return (
          <div id={id} className="flex flex-wrap gap-2">
            {field.choices?.map((choice) => (
              <ToggleChip
                key={String(choice.value)}
                active={String(choice.value) === String(value)}
                onClick={() => onChange(choice.value)}
              >
                {choice.label}
              </ToggleChip>
            ))}
          </div>
        )
      }
      return (
        <Select
          value={value === null || value === '' ? EMPTY_CHOICE : String(value)}
          onValueChange={(next) => {
            const choice = field.choices?.find((item) => String(item.value) === next)
            onChange(choice ? choice.value : null)
          }}
        >
          <SelectTrigger id={id} aria-invalid={invalid || undefined} className="w-full">
            <SelectValue placeholder="Выберите…" />
          </SelectTrigger>
          <SelectContent>
            {!field.required && <SelectItem value={EMPTY_CHOICE}>Не выбрано</SelectItem>}
            {field.choices?.map((choice) => (
              <SelectItem key={String(choice.value)} value={String(choice.value)}>
                {choice.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )
    case 'fk':
      return (
        <RelationSelect
          id={id}
          resource={resource}
          field={field.name}
          value={(value as number | null) ?? null}
          onChange={onChange}
          invalid={invalid}
          known={known}
        />
      )
    case 'm2m':
      return (
        <RelationSelect
          id={id}
          multiple
          resource={resource}
          field={field.name}
          value={(value as number[]) ?? []}
          onChange={onChange}
          invalid={invalid}
          known={known}
        />
      )
    case 'text':
    case 'json':
      return (
        <Textarea
          {...common}
          rows={field.type === 'json' ? 5 : 3}
          className={cn(field.type === 'json' && 'font-mono text-sm')}
          spellCheck={field.type !== 'json'}
          value={typeof value === 'string' ? value : JSON.stringify(value ?? '')}
          onChange={(event) => onChange(event.target.value)}
        />
      )
    case 'integer':
    case 'decimal':
    case 'number':
      return (
        <Input
          {...common}
          type="number"
          inputMode="decimal"
          step={field.type === 'integer' ? 1 : 'any'}
          value={value === null || value === undefined ? '' : String(value)}
          onChange={(event) => onChange(event.target.value)}
        />
      )
    case 'date':
    case 'time':
      return (
        <Input
          {...common}
          type={field.type}
          value={String(value ?? '')}
          onChange={(event) => onChange(event.target.value)}
        />
      )
    case 'datetime':
      return (
        <Input
          {...common}
          type="datetime-local"
          value={String(value ?? '')}
          onChange={(event) => onChange(event.target.value)}
        />
      )
    case 'image':
    case 'file':
      return (
        <div className="flex items-center gap-3">
          {field.type === 'image' && typeof value === 'string' && value && (
            <img src={value} alt="" className="size-16 rounded-md border object-cover" />
          )}
          {value instanceof File && field.type === 'image' && (
            <img
              src={URL.createObjectURL(value)}
              alt=""
              className="size-16 rounded-md border object-cover"
            />
          )}
          <Input
            {...common}
            type="file"
            accept={field.type === 'image' ? 'image/*' : undefined}
            onChange={(event) => onChange(event.target.files?.[0] ?? value)}
          />
        </div>
      )
    default:
      return (
        <Input
          {...common}
          type={field.type === 'email' ? 'email' : field.type === 'url' ? 'url' : 'text'}
          maxLength={field.max_length}
          value={String(value ?? '')}
          onChange={(event) => onChange(event.target.value)}
        />
      )
  }
}

function ToggleChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        'h-10 rounded-lg border px-3.5 text-[0.92rem] font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        active
          ? 'border-primary bg-primary text-primary-foreground'
          : 'border-input bg-card text-foreground hover:border-primary/50 hover:bg-accent',
      )}
    >
      {children}
    </button>
  )
}
