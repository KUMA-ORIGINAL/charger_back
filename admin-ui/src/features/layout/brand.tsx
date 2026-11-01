import { Zap } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

/** Знак Charger: молния на квадрате акцентного цвета. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        'grid size-10 shrink-0 place-items-center rounded-xl bg-primary text-lg font-extrabold text-primary-foreground',
        className,
      )}
    >
      <Zap className="size-[55%]" />
    </span>
  )
}
