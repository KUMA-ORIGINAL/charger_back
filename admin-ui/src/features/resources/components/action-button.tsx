import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { Loader2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ApiError, isDownloadedFile, saveFile } from '@/shared/api/http'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/ui/alert-dialog'
import { Button } from '@/shared/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog'
import { Label } from '@/shared/ui/label'
import { resourceKeys, runAction, runBulkAction } from '../api'
import { FieldInput, toApiValue, toFormValue } from '../fields/field-input'
import type { ActionField, ActionMeta, ActionResult, FieldMeta } from '../types'
import { ResourceIcon } from './resource-icon'

/** Показывает итог действия: файл — сохранить, сообщение — тост нужного цвета. */
export function reportActionResult(result: unknown) {
  if (isDownloadedFile(result)) {
    saveFile(result)
    return
  }
  const { message, level } = result as ActionResult
  const show = {
    success: toast.success,
    info: toast.info,
    warning: toast.warning,
    error: toast.error,
  }[level]
  ;(show ?? toast)(message)
}

interface ActionButtonProps {
  resource: string
  action: ActionMeta
  /** Объект для detail-действия или выбранные строки для bulk. */
  target: number | number[]
  /** Форма, которая зависит от объекта (`_actions` карточки), вместо `action.form`. */
  form?: ActionField[] | null
  onDone?: () => void
  size?: 'sm' | 'default'
}

type Values = Record<string, unknown>

const isBlank = (value: unknown) =>
  value === null ||
  value === undefined ||
  value === '' ||
  (Array.isArray(value) && value.length === 0)

/** Поле формы действия в виде поля ресурса — чтобы переиспользовать FieldInput. */
function asFieldMeta(field: ActionField): FieldMeta {
  return {
    name: field.name,
    label: field.label,
    type: field.type,
    help_text: field.help_text ?? '',
    required: field.required ?? false,
    read_only: false,
    computed: false,
    badges: null,
    format: null,
    choices: field.choices,
  }
}

export function ActionButton({
  resource,
  action,
  target,
  form = action.form,
  onDone,
  size = 'sm',
}: ActionButtonProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)
  const [asking, setAsking] = useState(false)
  const fields = (form ?? []).map(asFieldMeta)
  const [values, setValues] = useState<Values>({})
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: (data?: Values) =>
      Array.isArray(target)
        ? runBulkAction(resource, action.name, target, data)
        : runAction(resource, action.name, target, data),
    onSuccess: (result) => {
      reportActionResult(result)
      setAsking(false)
      void queryClient.invalidateQueries({ queryKey: resourceKeys.all(resource) })
      onDone?.()
      // Действие создало объект (копия товара) — открываем его.
      const opened = isDownloadedFile(result) ? undefined : (result as ActionResult).open
      if (opened) {
        void navigate({
          to: '/r/$resource/$id',
          params: { resource: opened.resource, id: opened.id },
        })
      }
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const fieldErrors = error.fieldErrors
        const own = Object.fromEntries(
          fields
            .filter((field) => fieldErrors[field.name])
            .map((field) => [field.name, fieldErrors[field.name].join(' ')]),
        )
        setErrors(own)
        if (!Object.keys(own).length) toast.error(error.message)
      } else {
        toast.error('Не удалось выполнить')
      }
    },
  })

  const open = () => {
    if (fields.length) {
      setValues(Object.fromEntries(fields.map((field) => [field.name, toFormValue(field, null)])))
      setErrors({})
      setAsking(true)
    } else if (action.confirm) {
      setConfirming(true)
    } else {
      mutation.mutate(undefined)
    }
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    // Диалог в портале, но события React всплывают по дереву компонентов: без
    // этого submit дошёл бы до формы карточки и сохранил бы её.
    event.stopPropagation()
    const missing = fields.filter((field) => field.required && isBlank(values[field.name]))
    if (missing.length) {
      setErrors(Object.fromEntries(missing.map((field) => [field.name, 'Обязательное поле'])))
      return
    }
    mutation.mutate(
      Object.fromEntries(
        fields.map((field) => [field.name, toApiValue(field, values[field.name])]),
      ),
    )
  }

  return (
    <>
      <Button
        type="button"
        size={size}
        variant={action.variant === 'destructive' ? 'destructive' : 'outline'}
        disabled={mutation.isPending}
        onClick={open}
      >
        {mutation.isPending ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          action.icon && <ResourceIcon name={action.icon} className="size-4" />
        )}
        {action.label}
      </Button>

      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{action.label}</AlertDialogTitle>
            <AlertDialogDescription>{action.confirm}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction onClick={() => mutation.mutate(undefined)}>
              Выполнить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={asking} onOpenChange={setAsking}>
        <DialogContent>
          <form noValidate onSubmit={submit} className="grid gap-5">
            <DialogHeader>
              <DialogTitle>{action.label}</DialogTitle>
              {action.confirm && <DialogDescription>{action.confirm}</DialogDescription>}
            </DialogHeader>
            {fields.map((field) => (
              <div key={field.name} className="grid gap-2.5">
                <Label htmlFor={`action-${action.name}-${field.name}`}>
                  {field.label}
                  {field.required && <span className="text-destructive">*</span>}
                </Label>
                <FieldInput
                  id={`action-${action.name}-${field.name}`}
                  field={field}
                  resource={resource}
                  value={values[field.name]}
                  invalid={Boolean(errors[field.name])}
                  onChange={(value) => {
                    setValues((current) => ({ ...current, [field.name]: value }))
                    setErrors(({ [field.name]: _, ...rest }) => rest)
                  }}
                />
                {errors[field.name] ? (
                  <p className="text-sm font-medium text-destructive">{errors[field.name]}</p>
                ) : (
                  field.help_text && (
                    <p className="text-sm text-muted-foreground">{field.help_text}</p>
                  )
                )}
              </div>
            ))}
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setAsking(false)}>
                Отмена
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending && <Loader2 className="animate-spin" />}
                Выполнить
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
