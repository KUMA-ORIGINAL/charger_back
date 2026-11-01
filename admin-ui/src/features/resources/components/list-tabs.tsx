import { cn } from '@/shared/lib/utils'
import { toneColor } from '../fields/value-view'
import type { ColumnMeta, FilterMeta } from '../types'

/**
 * Вкладки над списком по полю `list_tabs` («Все · Оформлен 12 · Готовим 3…»):
 * тот же фильтр, что в панели фильтров, но с числом строк в каждой вкладке и
 * цветной точкой статуса. Пустые вкладки не прячем — так видно, что их нет.
 */
export function ListTabs({
  filter,
  column,
  counts,
  value,
  onChange,
}: {
  filter: FilterMeta
  column?: ColumnMeta
  counts?: Record<string, number>
  value?: string
  onChange: (value: string | undefined) => void
}) {
  const total = counts ? Object.values(counts).reduce((sum, count) => sum + count, 0) : undefined
  const tabs = [
    { value: undefined, label: 'Все', count: total, tone: null },
    ...(filter.choices ?? []).map((choice) => ({
      value: String(choice.value),
      label: choice.label,
      count: counts ? (counts[String(choice.value)] ?? 0) : undefined,
      tone: column?.badges?.[String(choice.value)] ?? null,
    })),
  ]
  return (
    <div
      role="tablist"
      aria-label={filter.label}
      className="-mb-px flex overflow-x-auto px-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {tabs.map((tab) => {
        const active = (value ?? undefined) === tab.value
        return (
          <button
            key={tab.value ?? 'all'}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.value)}
            className={cn(
              'flex shrink-0 items-center gap-1.5 border-b-2 border-transparent px-2.5 py-2.5 text-sm whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
              active && 'border-primary font-medium text-foreground',
            )}
          >
            {tab.tone && (
              <span
                aria-hidden
                className="size-1.5 rounded-full"
                style={{ background: toneColor(tab.tone) }}
              />
            )}
            {tab.label}
            {tab.count !== undefined && (
              <span className="text-xs text-muted-foreground tabular-nums">
                {tab.count.toLocaleString('ru-RU')}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
