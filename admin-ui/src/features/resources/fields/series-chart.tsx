import { CartesianGrid, Line, LineChart, ReferenceArea, XAxis, YAxis } from 'recharts'
import { formatDateTime, formatTime } from '@/shared/lib/format'
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/shared/ui/chart'

/**
 * Значение типа `series` — ряд замеров во времени (температура холодильника).
 * Зона нормы закрашена: выход за неё видно без чтения чисел.
 */

export interface SeriesValue {
  unit: string
  normal?: [number, number] | null
  points: { t: string; v: number }[]
}

export function isSeries(value: unknown): value is SeriesValue {
  return typeof value === 'object' && value !== null && 'points' in value && 'unit' in value
}

const config = {
  v: { label: 'Значение', color: 'var(--chart-1)' },
} satisfies ChartConfig

export function SeriesChart({ value }: { value: SeriesValue }) {
  if (!value.points.length) {
    return <p className="text-sm text-muted-foreground">Замеров за это время нет.</p>
  }
  const values = value.points.map((point) => point.v)
  const [low, high] = value.normal ?? [Math.min(...values), Math.max(...values)]
  const outside = values.filter((v) => v < low || v > high).length
  const last = value.points.at(-1)
  const data = value.points.map((point) => ({ ...point, time: formatTime(point.t) }))

  return (
    <div className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        Сейчас{' '}
        <span className="font-semibold text-foreground tabular-nums">
          {last?.v} {value.unit}
        </span>
        {value.normal &&
          (outside
            ? `, вне нормы ${low}…${high} ${value.unit}: ${outside} из ${values.length} замеров`
            : `, все замеры в норме ${low}…${high} ${value.unit}`)}
      </p>
      <ChartContainer config={config} className="h-56 w-full">
        <LineChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 6" />
          {value.normal && (
            <ReferenceArea y1={low} y2={high} fill="var(--chart-2)" fillOpacity={0.08} />
          )}
          <XAxis dataKey="time" tickLine={false} axisLine={false} minTickGap={32} tickMargin={8} />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={36}
            domain={[
              (min: number) => Math.floor(Math.min(min, low) - 1),
              (max: number) => Math.ceil(Math.max(max, high) + 1),
            ]}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                labelFormatter={(_, payload) => {
                  const point = payload?.[0]?.payload as { t?: string } | undefined
                  return point?.t ? formatDateTime(point.t) : ''
                }}
                formatter={(item) => `${item} ${value.unit}`}
              />
            }
          />
          <Line dataKey="v" stroke="var(--color-v)" strokeWidth={2} dot={false} type="monotone" />
        </LineChart>
      </ChartContainer>
    </div>
  )
}
