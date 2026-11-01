import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { ApiError } from '@/shared/api/http'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog'
import { Skeleton } from '@/shared/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import { createRow, deleteRow, detailQuery, resourceKeys, updateRow } from '../api'
import {
  FieldInput,
  JsonFieldError,
  knownRelated,
  toApiValue,
  toFormValue,
} from '../fields/field-input'
import { groupTranslations, isTranslatedGroup, TranslatedField } from '../fields/translated-field'
import { ValueView } from '../fields/value-view'
import { useResources } from '../meta'
import type { FieldMeta, InlineMeta, ResourceMeta, Row } from '../types'
import { FieldRow } from './field-row'

/**
 * Связанные строки в карточке (как TabularInline). Если у инлайна есть ресурс
 * и он доступен пользователю, строки добавляются и правятся в диалоге — с
 * правами и проверками этого ресурса; иначе таблица только для чтения.
 */
export function InlineTable({
  inline,
  rows,
  parent,
  parentId,
}: {
  inline: InlineMeta
  rows: Record<string, unknown>[]
  /** Ключ ресурса карточки — после правок её данные нужно перечитать. */
  parent: string
  parentId: number
}) {
  const target = useResources().find((resource) => resource.key === inline.resource)
  const [editing, setEditing] = useState<number | 'new' | null>(null)
  const canAdd = Boolean(target?.permissions.add && inline.fk)
  const canOpen = Boolean(target && (target.permissions.change || target.permissions.delete))

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle className="text-base">
          {inline.label}
          <span className="ml-2 font-normal text-muted-foreground">{rows.length}</span>
        </CardTitle>
        {canAdd && (
          <Button type="button" variant="outline" size="sm" onClick={() => setEditing('new')}>
            <Plus />
            Добавить
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Нет записей</p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  {inline.columns.map((column) => (
                    <TableHead key={column.name}>{column.label}</TableHead>
                  ))}
                  {canOpen && (
                    <TableHead className="w-12">
                      <span className="sr-only">Изменить</span>
                    </TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, index) => (
                  <TableRow
                    key={String(row.id ?? index)}
                    className={canOpen ? 'cursor-pointer' : undefined}
                    onClick={canOpen ? () => setEditing(Number(row.id)) : undefined}
                  >
                    {inline.columns.map((column) => (
                      <TableCell key={column.name}>
                        <ValueView compact meta={column} value={row[column.name]} />
                      </TableCell>
                    ))}
                    {canOpen && (
                      <TableCell>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Изменить: ${inline.label}, строка ${index + 1}`}
                          onClick={(event) => {
                            event.stopPropagation()
                            setEditing(Number(row.id))
                          }}
                        >
                          <Pencil className="size-4" />
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
      {target && editing !== null && (
        <InlineRowDialog
          key={String(editing)}
          meta={target}
          inline={inline}
          rowId={editing === 'new' ? null : editing}
          parent={parent}
          parentId={parentId}
          onClose={() => setEditing(null)}
        />
      )}
    </Card>
  )
}

type Values = Record<string, unknown>

function InlineRowDialog({
  meta,
  inline,
  rowId,
  parent,
  parentId,
  onClose,
}: {
  meta: ResourceMeta
  inline: InlineMeta
  rowId: number | null
  parent: string
  parentId: number
  onClose: () => void
}) {
  const detail = useQuery({ ...detailQuery(meta.key, rowId ?? 0), enabled: rowId !== null })
  const isNew = rowId === null

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{isNew ? `${meta.label}: новая запись` : meta.label}</DialogTitle>
          <DialogDescription>
            {isNew ? 'Заполните поля и сохраните.' : rowTitle(meta, detail.data)}
          </DialogDescription>
        </DialogHeader>
        {!isNew && detail.isPending && <Skeleton className="h-40 w-full" />}
        {!isNew && detail.isError && (
          <p className="text-destructive">
            Запись не загрузилась. Закройте окно и попробуйте снова.
          </p>
        )}
        {(isNew || detail.data) && (
          <InlineRowForm
            meta={meta}
            inline={inline}
            row={detail.data}
            parent={parent}
            parentId={parentId}
            onClose={onClose}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

/** Подзаголовок диалога: что за строку правим (например, «Понедельник»). */
function rowTitle(meta: ResourceMeta, row?: Row): string {
  if (!row) return ''
  const label = meta.fields.find((field) => field.read_only && field.type === 'choice')
  if (label) {
    const value = row[label.name]
    return label.choices?.find((choice) => String(choice.value) === String(value))?.label ?? ''
  }
  return `#${row.id}`
}

function InlineRowForm({
  meta,
  inline,
  row,
  parent,
  parentId,
  onClose,
}: {
  meta: ResourceMeta
  inline: InlineMeta
  row?: Row
  parent: string
  parentId: number
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const isNew = !row
  const canEdit = isNew ? meta.permissions.add : meta.permissions.change
  // Связь с родителем ставится сама — выбирать её в диалоге незачем.
  const editable = meta.fields.filter(
    (field) => !field.read_only && field.name !== inline.fk && canEdit,
  )
  const form = useForm<Values>({
    defaultValues: Object.fromEntries(
      editable.map((field) => [
        field.name,
        toFormValue(field, row ? row[field.name] : field.default),
      ]),
    ),
  })

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: resourceKeys.all(parent) })
    void queryClient.invalidateQueries({ queryKey: resourceKeys.all(meta.key) })
  }

  const save = useMutation({
    mutationFn: (values: Values) => {
      const payload: Values = {}
      for (const field of editable) {
        if (!isNew && !form.formState.dirtyFields[field.name]) continue
        const value = toApiValue(field, values[field.name])
        if (value !== undefined) payload[field.name] = value
      }
      if (isNew && inline.fk) payload[inline.fk] = parentId
      return isNew ? createRow(meta.key, payload) : updateRow(meta.key, row.id, payload)
    },
    onSuccess: () => {
      refresh()
      toast.success(isNew ? 'Добавлено' : 'Сохранено')
      onClose()
    },
    onError: (error) => {
      if (error instanceof JsonFieldError) {
        form.setError(error.field, { message: error.message })
        return
      }
      if (!(error instanceof ApiError)) {
        toast.error('Не удалось сохранить')
        return
      }
      const known = new Set(editable.map((field) => field.name))
      let shown = false
      for (const [name, messages] of Object.entries(error.fieldErrors)) {
        if (known.has(name)) {
          form.setError(name, { message: messages.join(' ') })
          shown = true
        }
      }
      if (!shown) toast.error(Object.values(error.fieldErrors).flat().join(' ') || error.message)
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteRow(meta.key, row?.id ?? 0),
    onSuccess: () => {
      refresh()
      toast.success('Удалено')
      onClose()
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Не удалось удалить'),
  })

  return (
    <form
      noValidate
      onSubmit={(event) => {
        // Диалог в портале, но submit всплывает по дереву React до формы карточки.
        event.stopPropagation()
        void form.handleSubmit((values) => save.mutate(values))(event)
      }}
      className="grid gap-5"
    >
      {editable.length === 0 && (
        <p className="text-muted-foreground">Изменять эту запись вам нельзя.</p>
      )}
      {groupTranslations(editable).map((field) =>
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
            error={form.formState.errors[field.name]?.message as string | undefined}
          >
            <Controller
              control={form.control}
              name={field.name}
              render={({ field: control, fieldState }) => (
                <FieldInput
                  id={`field-${field.name}`}
                  field={field as FieldMeta}
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
      <DialogFooter className="items-center gap-2 sm:justify-between">
        {row && meta.permissions.delete ? (
          // Второе нажатие подтверждает: отдельный диалог поверх диалога — лишний слой.
          <Button
            type="button"
            variant={confirmDelete ? 'destructive' : 'ghost'}
            className={confirmDelete ? undefined : 'text-destructive'}
            disabled={remove.isPending}
            onClick={() => (confirmDelete ? remove.mutate() : setConfirmDelete(true))}
          >
            <Trash2 className="size-4" />
            {confirmDelete ? 'Точно удалить?' : 'Удалить'}
          </Button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          {editable.length > 0 && (
            <Button type="submit" disabled={save.isPending}>
              {save.isPending && <Loader2 className="animate-spin" />}
              {isNew ? 'Добавить' : 'Сохранить'}
            </Button>
          )}
        </div>
      </DialogFooter>
    </form>
  )
}
