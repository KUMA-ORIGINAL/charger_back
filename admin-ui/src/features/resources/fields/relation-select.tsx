import { useQuery } from '@tanstack/react-query'
import { Check, ChevronsUpDown, X } from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/ui/popover'
import { lookupQuery } from '../api'
import type { RelatedValue } from '../types'

/**
 * Выбор связи (FK или M2M) с поиском на сервере. Варианты приходят из
 * `lookup/<поле>/` ресурса-владельца поля и уже ограничены правами: владелец
 * не увидит чужих точек и категорий.
 */

interface BaseProps {
  resource: string
  field: string
  placeholder?: string
  disabled?: boolean
  invalid?: boolean
  /** Подписи уже выбранных значений, если они известны (из ответа API). */
  known?: RelatedValue[]
  id?: string
}

interface SingleProps extends BaseProps {
  multiple?: false
  value: number | null
  onChange: (value: number | null) => void
}

interface MultipleProps extends BaseProps {
  multiple: true
  value: number[]
  onChange: (value: number[]) => void
}

export function RelationSelect(props: SingleProps | MultipleProps) {
  const { resource, field, placeholder = 'Выберите…', disabled, invalid, known = [], id } = props
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const deferred = useDeferredValue(search)

  const selected: number[] = props.multiple ? props.value : props.value == null ? [] : [props.value]
  const missing = selected.filter((value) => !known.some((item) => item.id === value))
  const options = useQuery({ ...lookupQuery(resource, field, deferred), enabled: open })
  const labels = useQuery({
    ...lookupQuery(resource, field, '', missing),
    enabled: missing.length > 0,
  })

  const labelOf = (value: number) =>
    known.find((item) => item.id === value)?.label ??
    labels.data?.find((item) => item.id === value)?.label ??
    options.data?.find((item) => item.id === value)?.label ??
    `#${value}`

  const toggle = (value: number) => {
    if (props.multiple) {
      props.onChange(
        props.value.includes(value)
          ? props.value.filter((v) => v !== value)
          : [...props.value, value],
      )
    } else {
      props.onChange(props.value === value ? null : value)
      setOpen(false)
    }
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        // Старый запрос при следующем открытии только мешает найти другое.
        if (!next) setSearch('')
      }}
    >
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-invalid={invalid || undefined}
          disabled={disabled}
          className="h-auto min-h-11 w-full justify-between rounded-lg px-3.5 py-2 text-base font-normal active:scale-100 data-[state=open]:border-primary data-[state=open]:ring-4 data-[state=open]:ring-primary/15"
        >
          <span className="flex flex-1 flex-wrap gap-1 text-left">
            {selected.length === 0 && <span className="text-muted-foreground">{placeholder}</span>}
            {props.multiple
              ? selected.map((value) => (
                  <span
                    key={value}
                    className="inline-flex items-center rounded-md bg-accent px-2 py-0.5 text-[0.9rem] font-medium text-accent-foreground"
                  >
                    {labelOf(value)}
                  </span>
                ))
              : selected.map((value) => <span key={value}>{labelOf(value)}</span>)}
          </span>
          <span className="flex items-center gap-1">
            {selected.length > 0 && !disabled && (
              <X
                role="button"
                aria-label="Очистить"
                className="size-4 text-muted-foreground hover:text-foreground"
                onClick={(event) => {
                  event.stopPropagation()
                  if (props.multiple) props.onChange([])
                  else props.onChange(null)
                }}
              />
            )}
            <ChevronsUpDown className="size-4 opacity-50" />
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-64 p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput placeholder="Поиск…" value={search} onValueChange={setSearch} />
          <CommandList>
            <CommandEmpty>{options.isFetching ? 'Загрузка…' : 'Ничего не найдено'}</CommandEmpty>
            <CommandGroup>
              {options.data?.map((item) => (
                <CommandItem key={item.id} value={String(item.id)} onSelect={() => toggle(item.id)}>
                  <Check
                    className={cn(
                      'size-4',
                      selected.includes(item.id) ? 'opacity-100' : 'opacity-0',
                    )}
                  />
                  {item.label}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
