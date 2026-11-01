import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useBlocker, useNavigate } from '@tanstack/react-router'
import { ArrowLeft, Loader2, Trash2 } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { ApiError } from '@/shared/api/http'
import { cn } from '@/shared/lib/utils'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/shared/ui/alert-dialog'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { createRow, deleteRow, resourceKeys, updateRow } from '../api'
import {
  FieldInput,
  JsonFieldError,
  knownRelated,
  toApiValue,
  toFormValue,
} from '../fields/field-input'
import { groupTranslations, isTranslatedGroup, TranslatedField } from '../fields/translated-field'
import { ValueView } from '../fields/value-view'
import { lastListSearch } from '../list-search'
import type { FieldMeta, ObjectActions, ResourceMeta, Row } from '../types'
import { ActionButton } from './action-button'
import { FieldRow } from './field-row'
import { InlineTable } from './inline-table'
import { PageHeader } from './page-header'

/**
 * Карточка объекта — аналог change form Django admin: секции из `fieldsets`,
 * редактируемые поля как виджеты, read-only как значения, ниже инлайны.
 * Без `row` — форма создания.
 */

type Values = Record<string, unknown>

interface ResourceFormProps {
  meta: ResourceMeta
  row?: Row
}

export function ResourceForm({ meta, row }: ResourceFormProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isNew = !row
  const canEdit = isNew ? meta.permissions.add : meta.permissions.change
  const fieldsByName = new Map(meta.fields.map((field) => [field.name, field]))
  const editable = meta.fields.filter((field) => !field.read_only && canEdit)

  const form = useForm<Values>({
    defaultValues: row
      ? Object.fromEntries(
          editable.map((field) => [field.name, toFormValue(field, row[field.name])]),
        )
      : defaults(editable),
  })

  const addAnother = useRef(false)
  const save = useMutation({
    mutationFn: (values: Values) => {
      const dirty = form.formState.dirtyFields
      const payload: Values = {}
      for (const field of editable) {
        // В PATCH уходят только изменённые поля: чужие правки не затираются.
        if (!isNew && !dirty[field.name]) continue
        const value = toApiValue(field, values[field.name])
        if (value !== undefined) payload[field.name] = value
      }
      return isNew ? createRow(meta.key, payload) : updateRow(meta.key, row.id, payload)
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(resourceKeys.detail(meta.key, saved.id), saved)
      void queryClient.invalidateQueries({ queryKey: resourceKeys.all(meta.key) })
      if (isNew && addAnother.current) {
        // «Создать и добавить ещё»: чистая форма с умолчаниями, без перехода.
        addAnother.current = false
        form.reset(defaults(editable))
        toast.success('Создано. Можно добавлять следующее')
        window.scrollTo({ top: 0 })
        return
      }
      toast.success(isNew ? 'Создано' : 'Сохранено')
      form.reset(
        Object.fromEntries(
          editable.map((field) => [field.name, toFormValue(field, saved[field.name])]),
        ),
      )
      if (isNew) {
        void navigate({ to: '/r/$resource/$id', params: { resource: meta.key, id: saved.id } })
      }
    },
    onError: (error) => {
      addAnother.current = false
      if (error instanceof JsonFieldError) {
        form.setError(error.field, { message: error.message })
        return
      }
      if (error instanceof ApiError) {
        const fieldErrors = error.fieldErrors
        for (const [name, messages] of Object.entries(fieldErrors)) {
          if (fieldsByName.has(name)) form.setError(name, { message: messages.join(' ') })
        }
        const general = fieldErrors.non_field_errors?.join(' ')
        toast.error(general ?? error.message)
      } else {
        toast.error('Не удалось сохранить')
      }
    },
  })

  // Объект удалён — его правки больше не нужны, уходим без вопроса.
  const leaving = useRef(false)
  const remove = useMutation({
    mutationFn: () => deleteRow(meta.key, row?.id ?? 0),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: resourceKeys.all(meta.key) })
      toast.success('Удалено')
      leaving.current = true
      // Удалили последнюю строку страницы — такой страницы может уже не быть.
      void navigate({
        to: '/r/$resource',
        params: { resource: meta.key },
        search: { ...lastListSearch(meta.key), page: undefined },
      })
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Не удалось удалить'),
  })

  // Не прошла проверка формы — «добавить ещё» не должен остаться взведённым.
  const submit = form.handleSubmit(
    (values) => save.mutate(values),
    () => {
      addAnother.current = false
    },
  )
  const canSave = canEdit && editable.length > 0
  // Ctrl+S (⌘S) сохраняет карточку, а не страницу браузера.
  const submitRef = useRef(submit)
  submitRef.current = submit
  const pendingRef = useRef(false)
  pendingRef.current = save.isPending
  useEffect(() => {
    if (!canSave) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 's' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault()
        // Повторное нажатие во время сохранения создало бы вторую запись, а
        // открытый диалог (действие, строка инлайна) сохраняется своей кнопкой.
        if (pendingRef.current || document.querySelector('[role="dialog"]')) return
        void submitRef.current()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [canSave])

  // Уйти со страницы с несохранёнными правками — только после подтверждения.
  useBlocker({
    shouldBlockFn: () =>
      !leaving.current &&
      form.formState.isDirty &&
      !save.isPending &&
      !window.confirm('Есть несохранённые изменения. Уйти без сохранения?'),
    enableBeforeUnload: () => form.formState.isDirty,
  })

  // `_actions` карточки — какие действия доступны именно этому объекту и с какой
  // формой; без него (старый ответ) показываем все detail-действия.
  const objectActions = row?._actions as ObjectActions | null | undefined
  const detailActions = meta.actions.filter(
    (action) => action.detail && (!objectActions || action.name in objectActions),
  )
  const title = isNew ? `${meta.label}: новая запись` : `${meta.label} #${row.id}`

  // Раскладка карточки: редактируемое — слева по секциям, справочное — справа
  // списком «название — значение»; таблицы и JSON справа не помещаются, они слева.
  const isEditable = (field: FieldMeta) => !field.read_only && canEdit
  const sections: { title: string | null; fields: FieldMeta[] }[] = []
  const wideInfo: FieldMeta[] = []
  const info: FieldMeta[] = []
  for (const fieldset of meta.fieldsets) {
    const fields = fieldset.fields
      .map((name) => fieldsByName.get(name))
      .filter((field): field is FieldMeta => Boolean(field))
      // В форме создания вычисляемым и read-only полям показать нечего.
      .filter((field) => !(isNew && field.read_only))
    const editableFields = fields.filter(isEditable)
    if (editableFields.length) sections.push({ title: fieldset.title, fields: editableFields })
    for (const field of fields.filter((item) => !isEditable(item))) {
      // Поле только для записи (пароль) показать нечем.
      if (field.write_only) continue
      if (WIDE_INFO.has(field.type)) wideInfo.push(field)
      else info.push(field)
    }
  }
  const inlineRows = (row?.inlines ?? {}) as Record<string, Record<string, unknown>[]>
  // Левой колонке нечего показать (чек, оплата) — сведения займут всю ширину.
  const hasMain =
    sections.length > 0 || Boolean(row && (wideInfo.length > 0 || meta.inlines.length > 0))
  const dirty = form.formState.isDirty

  return (
    <form noValidate onSubmit={submit} className="flex flex-col gap-6 pb-32">
      <Link
        to="/r/$resource"
        params={{ resource: meta.key }}
        search={lastListSearch(meta.key)}
        className="inline-flex w-fit items-center gap-2 text-[0.95rem] font-semibold text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        {meta.label_plural}
      </Link>
      <PageHeader title={title} description={row ? rowCaption(meta, row) : undefined}>
        {row &&
          detailActions.map((action) => (
            <ActionButton
              key={action.name}
              resource={meta.key}
              action={action}
              target={row.id}
              form={objectActions?.[action.name]?.form ?? action.form}
              size="default"
            />
          ))}
      </PageHeader>

      {/* Колонки по ширине области контента, а не окна: сайдбар её заметно сужает. */}
      <div className="@container">
        <div
          className={cn(
            // minmax(0,1fr): без явной колонки сетка растягивается по самой широкой таблице.
            'grid grid-cols-[minmax(0,1fr)] items-start gap-6',
            info.length > 0 && hasMain && '@4xl:grid-cols-[minmax(0,1fr)_minmax(17rem,21rem)]',
          )}
        >
          {hasMain && (
            <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6">
              {sections.map((section, index) => (
                <Card key={section.title ?? index}>
                  {section.title && (
                    <CardHeader>
                      <CardTitle>{section.title}</CardTitle>
                    </CardHeader>
                  )}
                  <CardContent className="grid gap-x-6 gap-y-6 md:grid-cols-2">
                    {groupTranslations(section.fields).map((field) =>
                      isTranslatedGroup(field) ? (
                        <TranslatedField
                          key={field.base}
                          group={field}
                          resource={meta.key}
                          control={form.control}
                          errors={form.formState.errors}
                          row={row}
                        />
                      ) : (
                        <FieldRow
                          key={field.name}
                          field={field}
                          wide={isWide(field)}
                          error={form.formState.errors[field.name]?.message as string | undefined}
                        >
                          <Controller
                            control={form.control}
                            name={field.name}
                            render={({ field: control, fieldState }) => (
                              <FieldInput
                                id={`field-${field.name}`}
                                field={field}
                                resource={meta.key}
                                value={control.value}
                                onChange={control.onChange}
                                onBlur={control.onBlur}
                                invalid={fieldState.invalid}
                                known={knownRelated(row, field)}
                              />
                            )}
                          />
                        </FieldRow>
                      ),
                    )}
                  </CardContent>
                </Card>
              ))}

              {row &&
                wideInfo.map((field) => (
                  <Card key={field.name}>
                    <CardHeader>
                      <CardTitle>{field.label}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ValueView meta={field} value={row[field.name]} />
                    </CardContent>
                  </Card>
                ))}

              {row &&
                meta.inlines.map((inline) => (
                  <InlineTable
                    key={inline.name}
                    inline={inline}
                    rows={inlineRows[inline.name] ?? []}
                    parent={meta.key}
                    parentId={row.id}
                  />
                ))}
            </div>
          )}

          {row && info.length > 0 && (
            <aside className={cn(hasMain && '@4xl:sticky @4xl:top-6')}>
              <Card className="gap-2">
                <CardHeader>
                  <CardTitle>Сведения</CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Карточка только для чтения: сведения на всю ширину, в две колонки. */}
                  <dl
                    className={cn(
                      hasMain ? 'divide-y divide-border/70' : 'grid @3xl:grid-cols-2 @3xl:gap-x-10',
                    )}
                  >
                    {info.map((field) => (
                      <div
                        key={field.name}
                        className={cn(
                          'grid content-start gap-1 py-3',
                          hasMain ? 'first:pt-0 last:pb-0' : 'border-b border-border/70',
                        )}
                      >
                        <dt className="text-sm text-muted-foreground">{field.label}</dt>
                        <dd className="font-semibold break-words">
                          <ValueView meta={field} value={row[field.name]} />
                        </dd>
                      </div>
                    ))}
                  </dl>
                </CardContent>
              </Card>
            </aside>
          )}
        </div>
      </div>

      {(canEdit || (row && meta.permissions.delete)) && (
        <div className="fixed inset-x-3 bottom-3 z-20 md:right-10 md:left-[calc(var(--sidebar-width)+2.5rem)]">
          <div className="mx-auto flex max-w-[80rem] items-center justify-between gap-3 rounded-2xl border border-border/70 bg-card/95 px-4 py-3 shadow-[0_12px_40px_-12px_rgb(14_38_34/0.35)] backdrop-blur">
            {row && meta.permissions.delete ? (
              <DeleteButton onConfirm={() => remove.mutate()} pending={remove.isPending} />
            ) : (
              <span />
            )}
            <div className="flex items-center gap-4">
              {!isNew && dirty && (
                <span className="hidden text-[0.95rem] text-muted-foreground sm:inline">
                  Есть несохранённые изменения
                </span>
              )}
              {canSave && isNew && (
                <Button
                  type="button"
                  variant="outline"
                  className="hidden sm:inline-flex"
                  disabled={save.isPending}
                  onClick={() => {
                    addAnother.current = true
                    void submit()
                  }}
                >
                  Создать и добавить ещё
                </Button>
              )}
              {canSave && (
                <Button
                  type="submit"
                  title="Ctrl+S"
                  disabled={save.isPending || (!isNew && !dirty)}
                >
                  {save.isPending && <Loader2 className="animate-spin" />}
                  {isNew ? 'Создать' : 'Сохранить'}
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </form>
  )
}

/** Значения новой записи: умолчания полей из модели. */
function defaults(fields: FieldMeta[]): Values {
  return Object.fromEntries(fields.map((field) => [field.name, toFormValue(field, field.default)]))
}

/** Справочные поля этих типов слишком широки для боковой колонки. */
const WIDE_INFO = new Set(['table', 'json', 'series'])

/**
 * Подпись под заголовком: первое текстовое поле из `list_display_links`.
 * Значение выбора — его подписью («Не пробит», а не `failed`).
 */
export function rowCaption(meta: ResourceMeta, row: Row): string | undefined {
  for (const name of meta.list_display_links) {
    const value = row[name]
    if (typeof value !== 'string' || value.startsWith('/')) continue
    const column = meta.list_display.find((item) => item.name === name)
    if (column?.choices) {
      return column.choices.find((choice) => String(choice.value) === value)?.label ?? value
    }
    return value
  }
  return undefined
}

function isWide(field: FieldMeta) {
  return ['text', 'json', 'table', 'm2m'].includes(field.type)
}

function DeleteButton({ onConfirm, pending }: { onConfirm: () => void; pending: boolean }) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button type="button" variant="ghost" className="text-destructive" disabled={pending}>
          <Trash2 className="size-4" />
          Удалить
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить объект?</AlertDialogTitle>
          <AlertDialogDescription>Действие нельзя отменить.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>Удалить</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
