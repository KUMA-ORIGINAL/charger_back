import { Link } from '@tanstack/react-router'
import { Check, ImageOff, Minus, X } from 'lucide-react'
import {
  formatDate,
  formatDateTime,
  formatMoney,
  formatPhone,
  formatTime,
} from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Badge } from '@/shared/ui/badge'
import { isLinkValue, PanelLink } from '../components/panel-link'
import { isRelated, type RelatedValue } from '../types'
import { isSeries, SeriesChart } from './series-chart'

/**
 * Как показать значение поля — по `type` из /meta/. Один компонент для ячеек
 * таблицы, карточки и строк инлайнов, поэтому выглядит одинаково везде.
 */

export interface ValueMeta {
  type: string
  choices?: { value: unknown; label: string }[] | null
  badges?: Record<string, string> | null
  related_resource?: string | null
  format?: string | null
}

/**
 * Тон бейджа задаёт бэкенд (`badges`): у каждого статуса свой оттенок, точка
 * того же цвета — чтобы статусы различались и при беглом взгляде на список.
 * Старые имена (success, warning…) — синонимы оттенков.
 */
const TONES: Record<string, string> = {
  violet: 'var(--tone-violet)',
  amber: 'var(--tone-amber)',
  cyan: 'var(--tone-cyan)',
  green: 'var(--tone-green)',
  orange: 'var(--tone-orange)',
  red: 'var(--tone-red)',
  gray: 'var(--tone-gray)',
  success: 'var(--tone-green)',
  warning: 'var(--tone-amber)',
  danger: 'var(--tone-red)',
  info: 'var(--tone-violet)',
  primary: 'var(--tone-violet)',
  secondary: 'var(--tone-gray)',
}

/** CSS-цвет тона (для точек во вкладках и легенд): неизвестный тон — серый. */
export function toneColor(tone?: string | null): string {
  return TONES[tone ?? 'secondary'] ?? TONES.secondary
}

export function Tone({ tone, children }: { tone?: string; children: React.ReactNode }) {
  const color = toneColor(tone)
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md bg-(--tone)/14 px-2 py-0.5 text-[0.8rem] font-medium whitespace-nowrap text-(--tone)"
      style={{ '--tone': color } as React.CSSProperties}
    >
      <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-(--tone)" />
      {children}
    </span>
  )
}

function choiceLabel(meta: ValueMeta, value: unknown): string {
  const choice = meta.choices?.find((item) => String(item.value) === String(value))
  return choice?.label ?? String(value)
}

function RelatedLink({
  value,
  resource,
  compact,
}: {
  value: RelatedValue
  resource?: string | null
  compact?: boolean
}) {
  if (!resource) return <span>{value.label}</span>
  return (
    <Link
      to="/r/$resource/$id"
      params={{ resource, id: value.id }}
      // В таблице связь — обычный текст: колонка ссылок цвета акцента пестрит.
      className={cn(
        'underline-offset-4 hover:underline',
        compact ? 'hover:text-primary' : 'text-primary',
      )}
      onClick={(event) => event.stopPropagation()}
    >
      {value.label}
    </Link>
  )
}

interface TableValue {
  columns: { name: string; label: string }[]
  rows: Record<string, unknown>[]
}

function isTable(value: unknown): value is TableValue {
  return typeof value === 'object' && value !== null && 'columns' in value && 'rows' in value
}

export function ValueView({
  meta,
  value,
  compact = false,
}: {
  meta: ValueMeta
  value: unknown
  compact?: boolean
}) {
  if (value === null || value === undefined || value === '') {
    // Пустое фото в таблице — плитка того же размера, чтобы строки не прыгали.
    if (meta.type === 'image' && compact) {
      return (
        <span className="grid size-10 place-items-center rounded-md bg-muted text-muted-foreground/70">
          <ImageOff aria-label="нет фото" className="size-4" />
        </span>
      )
    }
    return <Minus aria-label="пусто" className="size-4 text-muted-foreground/60" />
  }

  if (meta.format === 'money' && (typeof value === 'number' || typeof value === 'string')) {
    return (
      <span className={cn('tabular-nums whitespace-nowrap', compact && 'font-semibold')}>
        {formatMoney(value)}
      </span>
    )
  }

  switch (meta.type) {
    case 'boolean':
      if (value) return <Check aria-label="да" className="size-4 text-primary" />
      // В таблице «нет» не рисуем: колонка из одних крестиков только шумит.
      return compact ? (
        <span className="sr-only">нет</span>
      ) : (
        <X aria-label="нет" className="size-4 text-muted-foreground" />
      )
    case 'choice': {
      const label = choiceLabel(meta, value)
      if (meta.badges) return <Tone tone={meta.badges[String(value)]}>{label}</Tone>
      return <span>{label}</span>
    }
    case 'multichoice': {
      const items = Array.isArray(value) ? value : []
      if (!items.length)
        return <Minus aria-label="пусто" className="size-4 text-muted-foreground/60" />
      return <span>{items.map((item) => choiceLabel(meta, item)).join(', ')}</span>
    }
    case 'password':
      return (
        <span>
          <span aria-hidden>••••••</span>
          <span className="sr-only">скрыто</span>
        </span>
      )
    case 'link': {
      const links = (Array.isArray(value) ? value : [value]).filter(isLinkValue)
      if (!links.length)
        return <Minus aria-label="пусто" className="size-4 text-muted-foreground/60" />
      return (
        <span className={cn('flex gap-x-4 gap-y-1.5', compact ? 'flex-wrap' : 'flex-col')}>
          {links.map((link) => (
            <PanelLink key={`${link.label}-${link.resource ?? link.to}`} link={link} />
          ))}
        </span>
      )
    }
    case 'badge': {
      // Вычисляемый статус: {value, label}; цвет — по value.
      const item = value as { value: string; label: string }
      return <Tone tone={meta.badges?.[item.value]}>{item.label}</Tone>
    }
    case 'datetime':
      return <span className="whitespace-nowrap tabular-nums">{formatDateTime(String(value))}</span>
    case 'date':
      return <span className="tabular-nums">{formatDate(String(value))}</span>
    case 'time':
      return (
        <span className="tabular-nums">
          {String(value).length <= 8 ? String(value).slice(0, 5) : formatTime(String(value))}
        </span>
      )
    case 'fk':
      return isRelated(value) ? (
        <RelatedLink value={value} resource={meta.related_resource} compact={compact} />
      ) : (
        <span>{String(value)}</span>
      )
    case 'm2m': {
      const items = Array.isArray(value) ? value.filter(isRelated) : []
      if (!items.length) return <Minus className="size-4 text-muted-foreground/60" />
      return (
        <span className="flex flex-wrap gap-1">
          {items.map((item) => (
            <Badge key={item.id} variant="outline" className="font-normal">
              {item.label}
            </Badge>
          ))}
        </span>
      )
    }
    case 'image':
      return (
        <img
          src={String(value)}
          alt=""
          loading="lazy"
          className={cn('rounded-md border object-cover', compact ? 'size-10' : 'max-h-48')}
        />
      )
    case 'file':
    case 'url':
      return (
        <a
          href={String(value)}
          target="_blank"
          rel="noreferrer"
          className="break-all text-primary underline-offset-4 hover:underline"
          onClick={(event) => event.stopPropagation()}
        >
          {compact ? 'Открыть' : String(value)}
        </a>
      )
    case 'json':
      return (
        <pre className="max-h-96 overflow-auto rounded-md bg-muted p-3 text-xs">
          {JSON.stringify(value, null, 2)}
        </pre>
      )
    case 'table':
      return isTable(value) ? <MiniTable value={value} /> : null
    case 'series': {
      if (!isSeries(value)) return null
      if (!compact) return <SeriesChart value={value} />
      const last = value.points.at(-1)
      return last ? (
        <span className="tabular-nums">
          {last.v} {value.unit}
        </span>
      ) : (
        <Minus aria-label="пусто" className="size-4 text-muted-foreground/60" />
      )
    }
    case 'decimal':
    case 'number':
    case 'integer':
      return <span className="tabular-nums">{Number(value).toLocaleString('ru-RU')}</span>
    case 'phone':
      return (
        <span className="font-medium whitespace-nowrap tabular-nums">
          {formatPhone(String(value))}
        </span>
      )
    case 'text':
      return (
        <span className={cn(compact ? 'line-clamp-2' : 'whitespace-pre-wrap')}>
          {String(value)}
        </span>
      )
    default:
      return <span>{String(value)}</span>
  }
}

function MiniTable({ value }: { value: TableValue }) {
  if (!value.rows.length) return <p className="text-sm text-muted-foreground">Нет данных</p>
  return (
    <div className="overflow-hidden rounded-md border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-muted-foreground">
          <tr>
            {value.columns.map((column) => (
              <th key={column.name} className="px-3 py-2 text-left font-medium">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {value.rows.map((row, index) => (
            <tr key={String(row.id ?? index)} className="border-t">
              {value.columns.map((column) => (
                <td key={column.name} className="px-3 py-2 tabular-nums">
                  {String(row[column.name] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
