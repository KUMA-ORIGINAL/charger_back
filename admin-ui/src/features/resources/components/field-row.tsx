import { cn } from '@/shared/lib/utils'
import { Label } from '@/shared/ui/label'
import type { FieldMeta } from '../types'

/** Подпись, виджет и подсказка (или ошибка) одного поля формы. */
export function FieldRow({
  field,
  wide,
  error,
  htmlFor = `field-${field.name}`,
  children,
}: {
  field: FieldMeta
  wide?: boolean
  error?: string
  htmlFor?: string
  children: React.ReactNode
}) {
  return (
    <div className={cn('grid content-start gap-2.5', wide && 'md:col-span-2')}>
      <Label htmlFor={htmlFor}>
        {field.label}
        {field.required && <span className="text-destructive">*</span>}
      </Label>
      {children}
      {error ? (
        <p className="text-sm font-medium text-destructive">{error}</p>
      ) : (
        field.help_text && <p className="text-sm text-muted-foreground">{field.help_text}</p>
      )}
    </div>
  )
}
