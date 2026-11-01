import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import type { Dashboard, StationStatus } from '@/shared/api/generated/model'
import { getStaffDashboardQueryOptions } from '@/shared/api/generated/staff'
import { formatTime } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/shared/ui/chart'
import { Skeleton } from '@/shared/ui/skeleton'

/** Период дашборда — пресеты, а не календарь: так быстрее с телефона. */
export type Period = 'today' | '7d' | 'month' | '30d' | 'prev-month'

export interface DashboardSearch {
  period?: Period
}

const PERIODS: Record<Period, string> = {
  today: 'Сегодня',
  '7d': '7 дней',
  month: 'Месяц',
  '30d': '30 дней',
  'prev-month': 'Прошлый месяц',
}

const iso = (date: Date) => date.toLocaleDateString('sv-SE', { timeZone: 'Asia/Bishkek' })

export function periodRange(
  period: Period,
  today = new Date(),
): { date_from: string; date_to: string } {
  const day = (offset: number) => new Date(today.getTime() - offset * 86_400_000)
  const [year, month] = iso(today).split('-').map(Number)
  switch (period) {
    case 'today':
      return { date_from: iso(today), date_to: iso(today) }
    case '7d':
      return { date_from: iso(day(6)), date_to: iso(today) }
    case '30d':
      return { date_from: iso(day(29)), date_to: iso(today) }
    case 'prev-month': {
      const start = new Date(Date.UTC(year, month - 2, 1))
      const end = new Date(Date.UTC(year, month - 1, 0))
      return {
        date_from: start.toISOString().slice(0, 10),
        date_to: end.toISOString().slice(0, 10),
      }
    }
    default:
      return { date_from: `${year}-${String(month).padStart(2, '0')}-01`, date_to: iso(today) }
  }
}

const bishkek = { timeZone: 'Asia/Bishkek' } as const

function shortDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
  })
}

/** «1–22 октября», «28 сентября – 4 октября». */
function periodLabel(from: string, to: string) {
  if (from === to) return shortDate(from)
  const [fromDay, fromMonth] = shortDate(from).split(' ')
  const toLabel = shortDate(to)
  return from.slice(0, 7) === to.slice(0, 7)
    ? `${fromDay}–${toLabel}`
    : `${fromDay} ${fromMonth} – ${toLabel}`
}

export function DashboardPage({
  search,
  onSearchChange,
}: {
  search: DashboardSearch
  onSearchChange: (next: DashboardSearch) => void
}) {
  const period = search.period ?? 'month'
  const query = useQuery({
    ...getStaffDashboardQueryOptions(periodRange(period)),
    // Связь со станциями и зарядки идут сами по себе — обновляем раз в 30 секунд.
    refetchInterval: 30_000,
  })
  const data = query.data
  const now = new Date()
  const today = now.toLocaleDateString('ru-RU', {
    ...bishkek,
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-col gap-4 @4xl:flex-row @4xl:items-end @4xl:justify-between">
        <div>
          <p className="text-sm text-muted-foreground first-letter:uppercase">
            {today}
            {query.dataUpdatedAt > 0 && ` · данные на ${formatTime(query.dataUpdatedAt)}`}
          </p>
          <h1 className="mt-1 text-2xl sm:text-[1.75rem] sm:leading-tight">Обзор сети</h1>
        </div>
        <PeriodSwitch
          value={period}
          onChange={(value) => onSearchChange({ ...search, period: value })}
        />
      </header>

      {query.isError && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-destructive">
          Не удалось загрузить сводку. Обновите страницу через минуту.
        </p>
      )}

      <Metrics data={data} />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 @4xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <ChartCard data={data} />
        <StationList stations={data?.stations} />
      </div>
    </div>
  )
}

/** Переключатель-«таблетка»: выбранный вариант — приподнятая плашка внутри. */
function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  size = 'default',
}: {
  label: string
  options: Record<T, string>
  value: T
  onChange: (value: T) => void
  size?: 'default' | 'sm'
}) {
  return (
    <fieldset className="flex max-w-full min-w-0 overflow-x-auto rounded-lg border bg-muted/50 p-0.5">
      <legend className="sr-only">{label}</legend>
      {(Object.keys(options) as T[]).map((key) => (
        <button
          key={key}
          type="button"
          aria-pressed={value === key}
          onClick={() => onChange(key)}
          className={cn(
            'rounded-md px-3 text-sm whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
            size === 'sm' ? 'h-7 px-2.5 text-[0.8rem]' : 'h-8',
            value === key &&
              'bg-background font-medium text-foreground shadow-xs dark:bg-secondary',
          )}
        >
          {options[key]}
        </button>
      ))}
    </fieldset>
  )
}

function PeriodSwitch({ value, onChange }: { value: Period; onChange: (value: Period) => void }) {
  return <Segmented label="Период" options={PERIODS} value={value} onChange={onChange} />
}

function change(current: number, previous: number) {
  return previous ? ((current - previous) / previous) * 100 : null
}

function Delta({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="text-xs text-muted-foreground">в прошлом периоде данных не было</span>
  }
  const up = value >= 0
  const Icon = up ? ArrowUp : ArrowDown
  return (
    <span className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-muted-foreground">
      <span
        className={cn(
          'inline-flex items-center gap-0.5 rounded px-1 py-px font-medium tabular-nums',
          up ? 'bg-success/14 text-success' : 'bg-destructive/14 text-destructive',
        )}
      >
        <Icon aria-hidden className="size-3" />
        <span className="sr-only">{up ? 'рост' : 'падение'}</span>
        {Math.abs(value).toFixed(0)}%
      </span>
      к прошлому периоду
    </span>
  )
}

function Metrics({ data }: { data?: Dashboard }) {
  const summary = data?.summary
  const items = [
    {
      label: 'Выручка',
      value: summary?.revenue.toLocaleString('ru-RU', { maximumFractionDigits: 0 }),
      unit: 'сом',
      delta: summary && change(summary.revenue, summary.previous_revenue),
    },
    {
      label: 'Оплат',
      value: summary?.payments.toLocaleString('ru-RU'),
      delta: summary && change(summary.payments, summary.previous_payments),
    },
    {
      label: 'Сессий зарядки',
      value: summary?.sessions.toLocaleString('ru-RU'),
      delta: summary && change(summary.sessions, summary.previous_sessions),
    },
    {
      label: 'Выдано энергии',
      value: summary?.kwh.toLocaleString('ru-RU', { maximumFractionDigits: 1 }),
      unit: 'кВт⋅ч',
      delta: summary && change(summary.kwh, summary.previous_kwh),
    },
  ]

  return (
    <section
      aria-label="Итоги периода"
      className="grid grid-cols-2 overflow-hidden rounded-xl border bg-card @3xl:grid-cols-4"
    >
      {items.map((item) => (
        <div
          key={item.label}
          className="min-w-0 border-border px-3.5 py-3 odd:border-r nth-[-n+2]:border-b @xl:px-4 @xl:py-3.5 @3xl:nth-[-n+2]:border-b-0 @3xl:not-last:border-r"
        >
          <p className="text-[0.8rem] text-muted-foreground">{item.label}</p>
          {item.value === undefined ? (
            <Skeleton className="mt-2 h-8 w-28" />
          ) : (
            <p className="mt-1 text-[1.3rem] leading-tight font-semibold tracking-[-0.02em] tabular-nums @xl:text-[1.6rem]">
              {item.value}
              {item.unit && (
                <span className="ml-1 text-sm font-normal text-muted-foreground">{item.unit}</span>
              )}
            </p>
          )}
          {item.delta !== undefined && (
            <div className="mt-1">
              <Delta value={item.delta} />
            </div>
          )}
        </div>
      ))}
    </section>
  )
}

type Series = 'revenue' | 'sessions' | 'kwh'

const SERIES: Record<Series, string> = { revenue: 'Выручка', sessions: 'Сессии', kwh: 'кВт⋅ч' }
const TITLES: Record<Series, string> = {
  revenue: 'Выручка по дням',
  sessions: 'Сессии по дням',
  kwh: 'Выдано энергии по дням',
}

const chartConfig = {
  revenue: { label: 'Выручка, сом', color: 'var(--chart-1)' },
  sessions: { label: 'Сессии', color: 'var(--chart-1)' },
  kwh: { label: 'кВт⋅ч', color: 'var(--chart-1)' },
} satisfies ChartConfig

/** Одна серия на одной оси: переключатель вместо нескольких графиков на разных шкалах. */
function ChartCard({ data }: { data?: Dashboard }) {
  const [series, setSeries] = useState<Series>('revenue')
  return (
    <section aria-labelledby="chart-title" className="rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="chart-title" className="text-[0.95rem] font-semibold">
            {TITLES[series]}
          </h2>
          <p className="text-xs text-muted-foreground">
            {data ? `${periodLabel(data.date_from, data.date_to)} · ` : ''}
            {series === 'revenue' ? 'только оплаченные QR-платежи' : 'по началу сессии'}
          </p>
        </div>
        <Segmented
          label="Что показать"
          options={SERIES}
          value={series}
          onChange={setSeries}
          size="sm"
        />
      </div>
      {data ? (
        <ChartContainer config={chartConfig} className="mt-3 h-64 w-full">
          <BarChart
            data={data.days.map((day) => ({ ...day, label: day.date.slice(8, 10) }))}
            margin={{ left: 0, right: 0, top: 4 }}
          >
            <CartesianGrid vertical={false} strokeDasharray="2 4" />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              minTickGap={12}
              tickMargin={8}
            />
            <YAxis
              allowDecimals={series === 'kwh'}
              tickLine={false}
              axisLine={false}
              width={series === 'revenue' ? 48 : 36}
              tickFormatter={(value: number) => value.toLocaleString('ru-RU')}
            />
            <ChartTooltip
              cursor={{ fill: 'var(--muted)', opacity: 0.6 }}
              content={
                <ChartTooltipContent
                  labelFormatter={(_, payload) => {
                    const date = payload?.[0]?.payload?.date as string | undefined
                    return date ? shortDate(date) : ''
                  }}
                />
              }
            />
            <Bar dataKey={series} fill={`var(--color-${series})`} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ChartContainer>
      ) : (
        <Skeleton className="mt-3 h-64 w-full" />
      )}
    </section>
  )
}

function stationState(station: StationStatus) {
  if (station.online === false) return { label: 'Нет связи', dot: 'bg-destructive' }
  if (station.online === null) return { label: 'Связь неизвестна', dot: 'bg-muted-foreground/50' }
  if (station.charging) return { label: 'Заряжает', dot: 'bg-success led-live' }
  if (station.session_id) return { label: 'Подготовка', dot: 'bg-warning' }
  return { label: 'Свободна', dot: 'bg-success' }
}

function StationList({ stations }: { stations?: StationStatus[] }) {
  return (
    <section aria-labelledby="stations-title" className="rounded-xl border bg-card p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="stations-title" className="text-[0.95rem] font-semibold">
          Станции
        </h2>
        <Link
          to="/r/$resource"
          params={{ resource: 'chargepoint' }}
          className="text-sm text-primary hover:underline"
        >
          Все станции
        </Link>
      </div>
      {!stations && <Skeleton className="mt-3 h-48 w-full" />}
      {stations?.length === 0 && (
        <p className="py-8 text-sm text-muted-foreground">
          Станций пока нет. Добавьте первую в разделе «Станции».
        </p>
      )}
      {!!stations?.length && (
        <ul className="mt-2 grid">
          {stations.map((station) => {
            const state = stationState(station)
            return (
              <li key={station.id} className="border-b border-border/60 last:border-0">
                <Link
                  to="/r/$resource/$id"
                  params={{ resource: 'chargepoint', id: station.id }}
                  className="-mx-2 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <span className="min-w-0 leading-tight">
                    <span className="block truncate text-sm font-medium">{station.name}</span>
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span
                        aria-hidden
                        className={cn('size-1.5 shrink-0 rounded-full', state.dot)}
                      />
                      {state.label}
                      {station.power_kw !== null && ` · ${station.power_kw} кВт`}
                      {station.soc !== null && ` · ${station.soc}%`}
                    </span>
                  </span>
                  <span className="text-right leading-tight">
                    <span className="block text-sm font-semibold tabular-nums">
                      {station.sessions_today}
                    </span>
                    <span className="text-xs text-muted-foreground">сегодня</span>
                  </span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
