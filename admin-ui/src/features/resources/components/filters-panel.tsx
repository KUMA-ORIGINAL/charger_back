import { useQuery } from '@tanstack/react-query'
import { SlidersHorizontal, X } from 'lucide-react'
import { useState } from 'react'
import { formatDate } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/shared/ui/sheet'
import { lookupQuery } from '../api'
import { RelationSelect } from '../fields/relation-select'
import type { FilterMeta } from '../types'

/**
 * Фильтры из `list_filter`. Значения — строки параметров API, как в URL:
 * `status=1`, `spot=3`, `created_at__gte=2026-10-01`.
 */

const ANY = '__any__'

type Filters = Record<string, string>

/** Имена параметров, которые занимает фильтр (у диапазона их два). */
export function filterParams(filter: FilterMeta): string[] {
  return filter.type === 'date_range' || filter.type === 'number_range'
    ? [`${filter.name}__gte`, `${filter.name}__lte`]
    : [filter.name]
}

interface FiltersPanelProps {
  resource: string
  filters: FilterMeta[]
  values: Filters
  onChange: (values: Filters) => void
  /** Сколько строк сейчас под фильтрами — для кнопки «Показать N». */
  resultCount?: number
}

type SetFilters = (patch: Filters) => void

/** Применяет сразу несколько параметров (диапазон дат — это два ключа). */
function patchFilters(values: Filters, patch: Filters): Filters {
  const next = { ...values }
  for (const [name, value] of Object.entries(patch)) {
    if (value) next[name] = value
    else delete next[name]
  }
  return next
}

export function FiltersPanel({
  resource,
  filters,
  values,
  onChange,
  resultCount,
}: FiltersPanelProps) {
  const [open, setOpen] = useState(false)
  const active = filters.filter((filter) => filterParams(filter).some((name) => values[name]))
  const set: SetFilters = (patch) => onChange(patchFilters(values, patch))

  if (!filters.length) return null

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="outline" size="sm">
            <SlidersHorizontal className="size-4" />
            Фильтры
            {active.length > 0 && (
              <Badge className="ml-1 h-5 min-w-5 rounded-full px-1.5">{active.length}</Badge>
            )}
          </Button>
        </SheetTrigger>
        <SheetContent className="w-full overflow-y-auto sm:max-w-sm">
          <SheetHeader>
            <SheetTitle>Фильтры</SheetTitle>
            <SheetDescription>Список обновляется сразу, пока вы выбираете.</SheetDescription>
          </SheetHeader>
          <div className="grid gap-6 px-4">
            {filters.map((filter) => (
              <FilterControl
                key={filter.name}
                resource={resource}
                filter={filter}
                values={values}
                set={set}
              />
            ))}
          </div>
          <SheetFooter className="grid grid-cols-2 gap-2 border-t">
            <Button variant="outline" onClick={() => onChange({})} disabled={!active.length}>
              Сбросить всё
            </Button>
            <Button onClick={() => setOpen(false)}>
              {resultCount === undefined
                ? 'Готово'
                : `Показать ${resultCount.toLocaleString('ru-RU')}`}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
      {active.map((filter) => (
        <ActiveChip
          key={filter.name}
          resource={resource}
          filter={filter}
          values={values}
          onClear={() => {
            const next = { ...values }
            for (const name of filterParams(filter)) delete next[name]
            onChange(next)
          }}
        />
      ))}
    </div>
  )
}

/** Варианты фильтра «выбор» и «да/нет» в одном виде. */
function choicesOf(filter: FilterMeta) {
  if (filter.type === 'boolean') {
    return [
      { value: 'true', label: 'Да' },
      { value: 'false', label: 'Нет' },
    ]
  }
  return (filter.choices ?? []).map((choice) => ({
    value: String(choice.value),
    label: choice.label,
  }))
}

/** Короткий выбор — кнопками «Все / …», длинный — выпадающим списком. */
const SEGMENTED_MAX = 4

function Segmented({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: { value: string; label: string }[]
  value: string | undefined
  onChange: (value: string) => void
  label: string
  className?: string
}) {
  return (
    <div role="toolbar" aria-label={label} className={cn('flex flex-wrap gap-1.5', className)}>
      {[{ value: '', label: 'Все' }, ...options].map((option) => {
        const selected = (value ?? '') === option.value
        return (
          <button
            key={option.value || 'all'}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.value)}
            className={cn(
              'h-9 shrink-0 rounded-full border px-3.5 text-sm font-semibold whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
              selected
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-input bg-card text-foreground hover:border-foreground/25 hover:bg-secondary',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

/**
 * Быстрый фильтр над таблицей: первый «выбор» из list_filter (статус заказа),
 * чтобы самое частое переключение было в один клик, без панели.
 */
export function QuickFilter({
  filters,
  values,
  onChange,
}: {
  filters: FilterMeta[]
  values: Filters
  onChange: (values: Filters) => void
}) {
  const filter = filters.find((item) => item.type === 'choice' && (item.choices?.length ?? 0) <= 8)
  if (!filter) return null
  return (
    <div className="-mx-4 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <Segmented
        label={filter.label}
        options={choicesOf(filter)}
        value={values[filter.name]}
        onChange={(value) => onChange(patchFilters(values, { [filter.name]: value }))}
        className="flex-nowrap"
      />
    </div>
  )
}

const bishkekDate = (offsetDays = 0) =>
  new Date(Date.now() - offsetDays * 86_400_000).toLocaleDateString('sv-SE', {
    timeZone: 'Asia/Bishkek',
  })

/** Частые периоды: ставят «от» и «до» одним нажатием. */
function datePresets(): { label: string; from: string; to: string }[] {
  const today = bishkekDate()
  return [
    { label: 'Сегодня', from: today, to: today },
    { label: 'Вчера', from: bishkekDate(1), to: bishkekDate(1) },
    { label: '7 дней', from: bishkekDate(6), to: today },
    { label: '30 дней', from: bishkekDate(29), to: today },
    { label: 'Этот месяц', from: `${today.slice(0, 8)}01`, to: today },
  ]
}

function FilterControl({
  resource,
  filter,
  values,
  set,
}: {
  resource: string
  filter: FilterMeta
  values: Filters
  set: SetFilters
}) {
  const id = `filter-${filter.name}`
  switch (filter.type) {
    case 'choice':
    case 'boolean': {
      const choices = choicesOf(filter)
      if (choices.length <= SEGMENTED_MAX) {
        return (
          <div className="grid gap-2.5">
            <span className="text-[0.9rem] font-semibold">{filter.label}</span>
            <Segmented
              label={filter.label}
              options={choices}
              value={values[filter.name]}
              onChange={(value) => set({ [filter.name]: value })}
            />
          </div>
        )
      }
      return (
        <div className="grid gap-2.5">
          <Label htmlFor={id}>{filter.label}</Label>
          <Select
            value={values[filter.name] ?? ANY}
            onValueChange={(value) => set({ [filter.name]: value === ANY ? '' : value })}
          >
            <SelectTrigger id={id} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Все</SelectItem>
              {choices.map((choice) => (
                <SelectItem key={choice.value} value={choice.value}>
                  {choice.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )
    }
    case 'relation': {
      const current = values[filter.name]
      return (
        <div className="grid gap-2.5">
          <Label htmlFor={id}>{filter.label}</Label>
          <RelationSelect
            id={id}
            resource={resource}
            field={filter.name}
            placeholder="Все"
            value={current ? Number(current) : null}
            onChange={(value) => set({ [filter.name]: value == null ? '' : String(value) })}
          />
        </div>
      )
    }
    case 'date_range':
    case 'number_range': {
      const isDate = filter.type === 'date_range'
      const from = `${filter.name}__gte`
      const to = `${filter.name}__lte`
      return (
        <fieldset className="grid gap-2.5">
          <legend className="mb-2.5 text-[0.9rem] font-semibold">{filter.label}</legend>
          {isDate && (
            <div className="flex flex-wrap gap-1.5">
              {datePresets().map((preset) => {
                const selected = values[from] === preset.from && values[to] === preset.to
                return (
                  <button
                    key={preset.label}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => set({ [from]: preset.from, [to]: preset.to })}
                    className={cn(
                      'h-8 rounded-full border px-3 text-[0.82rem] font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                      selected
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-input bg-card hover:border-foreground/25 hover:bg-secondary',
                    )}
                  >
                    {preset.label}
                  </button>
                )
              })}
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <Input
              aria-label={`${filter.label}: от`}
              placeholder="от"
              type={isDate ? 'date' : 'number'}
              inputMode={isDate ? undefined : 'decimal'}
              value={values[from] ?? ''}
              onChange={(event) => set({ [from]: event.target.value })}
            />
            <Input
              aria-label={`${filter.label}: до`}
              placeholder="до"
              type={isDate ? 'date' : 'number'}
              inputMode={isDate ? undefined : 'decimal'}
              value={values[to] ?? ''}
              onChange={(event) => set({ [to]: event.target.value })}
            />
          </div>
        </fieldset>
      )
    }
    default:
      return (
        <div className="grid gap-2.5">
          <Label htmlFor={id}>{filter.label}</Label>
          <Input
            id={id}
            value={values[filter.name] ?? ''}
            onChange={(event) => set({ [filter.name]: event.target.value })}
          />
        </div>
      )
  }
}

function ActiveChip({
  resource,
  filter,
  values,
  onClear,
}: {
  resource: string
  filter: FilterMeta
  values: Filters
  onClear: () => void
}) {
  const value = values[filter.name]
  const relation = useQuery({
    ...lookupQuery(resource, filter.name, '', value ? [Number(value)] : []),
    enabled: filter.type === 'relation' && Boolean(value),
  })

  let text: string
  if (filter.type === 'relation') text = relation.data?.[0]?.label ?? `#${value}`
  else if (filter.type === 'boolean') text = value === 'true' ? 'да' : 'нет'
  else if (filter.type === 'choice')
    text = filter.choices?.find((choice) => String(choice.value) === value)?.label ?? value
  else if (filter.type === 'date_range' || filter.type === 'number_range') {
    const show = (raw?: string) =>
      raw ? (filter.type === 'date_range' ? formatDate(raw) : raw) : '…'
    text = `от ${show(values[`${filter.name}__gte`])} до ${show(values[`${filter.name}__lte`])}`
  } else text = value

  return (
    <Badge variant="secondary" className="gap-1 py-1 pr-1 pl-2 font-normal">
      <span className="text-muted-foreground">{filter.label}:</span> {text}
      <button
        type="button"
        aria-label={`Убрать фильтр «${filter.label}»`}
        onClick={onClear}
        className="rounded-full p-0.5 hover:bg-background"
      >
        <X className="size-3" />
      </button>
    </Badge>
  )
}
