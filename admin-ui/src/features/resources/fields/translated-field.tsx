import { useState } from 'react'
import { type Control, Controller, type FieldErrors, useWatch } from 'react-hook-form'
import { cn } from '@/shared/lib/utils'
import { Label } from '@/shared/ui/label'
import type { FieldMeta, Row } from '../types'
import { FieldInput, knownRelated } from './field-input'

/**
 * Поля modeltranslation (`name_ru`, `name_ky`, `name_en`) — одно поле с
 * вкладками языков вместо трёх одинаковых. Все языки остаются в форме, на
 * экране только выбранный.
 */

export const LANGUAGES = [
  { code: 'ru', label: 'RU', title: 'Русский' },
  { code: 'ky', label: 'KY', title: 'Кыргызча' },
  { code: 'en', label: 'EN', title: 'English' },
] as const

const SUFFIX = /_(ru|ky|en)$/
const LABEL_SUFFIX = /\s*\[(ru|ky|en)\]\s*$/i

export interface TranslatedGroup {
  base: string
  label: string
  fields: FieldMeta[]
}

/** Раскладывает поля секции: переводы одного поля — в группу, остальные как есть. */
export function groupTranslations(fields: FieldMeta[]): (FieldMeta | TranslatedGroup)[] {
  const byBase = new Map<string, FieldMeta[]>()
  for (const field of fields) {
    const match = SUFFIX.exec(field.name)
    if (match) {
      const base = field.name.slice(0, -3)
      byBase.set(base, [...(byBase.get(base) ?? []), field])
    }
  }
  const seen = new Set<string>()
  const result: (FieldMeta | TranslatedGroup)[] = []
  for (const field of fields) {
    const match = SUFFIX.exec(field.name)
    const base = match ? field.name.slice(0, -3) : null
    const group = base ? byBase.get(base) : undefined
    if (!base || !group || group.length < 2) {
      result.push(field)
      continue
    }
    if (seen.has(base)) continue
    seen.add(base)
    const order = LANGUAGES.map((lang) => lang.code as string)
    result.push({
      base,
      label: field.label.replace(LABEL_SUFFIX, ''),
      fields: [...group].sort(
        (a, b) => order.indexOf(a.name.slice(-2)) - order.indexOf(b.name.slice(-2)),
      ),
    })
  }
  return result
}

export function isTranslatedGroup(item: FieldMeta | TranslatedGroup): item is TranslatedGroup {
  return 'base' in item
}

interface TranslatedFieldProps {
  group: TranslatedGroup
  resource: string
  control: Control<Record<string, unknown>>
  errors: FieldErrors<Record<string, unknown>>
  row?: Row
}

export function TranslatedField({ group, resource, control, errors, row }: TranslatedFieldProps) {
  const values = useWatch({ control, name: group.fields.map((field) => field.name) })
  const [active, setActive] = useState(group.fields[0]?.name)
  const wide = group.fields.some((field) => field.type === 'text')
  const required = group.fields.some((field) => field.required)
  const activeError = errors[active ?? '']?.message as string | undefined

  return (
    <div className={cn('grid content-start gap-2.5', wide && 'md:col-span-2')}>
      <div className="flex items-center justify-between gap-3">
        <Label htmlFor={`field-${active}`}>
          {group.label}
          {required && <span className="text-destructive">*</span>}
        </Label>
        <div role="toolbar" className="flex rounded-lg bg-muted p-0.5" aria-label="Язык">
          {group.fields.map((field, index) => {
            const code = field.name.slice(-2)
            const lang = LANGUAGES.find((item) => item.code === code)
            const empty = !String(values[index] ?? '').trim()
            const hasError = Boolean(errors[field.name])
            return (
              <button
                key={field.name}
                type="button"
                title={`${lang?.title ?? code}${empty ? ', не заполнено' : ''}`}
                aria-pressed={active === field.name}
                onClick={() => setActive(field.name)}
                className={cn(
                  'h-7 min-w-10 rounded-md px-2 text-xs font-bold tracking-wide transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                  active === field.name
                    ? 'bg-card text-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground',
                  empty && active !== field.name && 'opacity-55',
                  hasError && 'text-destructive',
                )}
              >
                {lang?.label ?? code.toUpperCase()}
              </button>
            )
          })}
        </div>
      </div>
      {group.fields.map((field) => (
        <div key={field.name} hidden={active !== field.name}>
          <Controller
            control={control}
            name={field.name}
            render={({ field: input, fieldState }) => (
              <FieldInput
                id={`field-${field.name}`}
                field={field}
                resource={resource}
                value={input.value}
                onChange={input.onChange}
                onBlur={input.onBlur}
                invalid={fieldState.invalid}
                known={knownRelated(row, field)}
              />
            )}
          />
        </div>
      ))}
      {activeError && <p className="text-sm font-medium text-destructive">{activeError}</p>}
    </div>
  )
}
