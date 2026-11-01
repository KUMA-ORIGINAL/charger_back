import type { ReactNode } from 'react'

/**
 * Заголовок страницы и кнопки. Раскладка — по ширине области контента
 * (`@container` в лейауте), а не окна: с открытым сайдбаром места меньше, и
 * кнопки уходят под заголовок, а не обрезают его.
 */
export function PageHeader({
  title,
  description,
  children,
}: {
  title: ReactNode
  description?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-4 @4xl:flex-row @4xl:items-end @4xl:justify-between">
      <div className="min-w-0">
        <h1 className="text-[1.75rem] leading-tight font-semibold break-words sm:text-[2.1rem] @4xl:truncate">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 text-[0.95rem] text-muted-foreground">{description}</p>
        )}
      </div>
      {children && (
        <div className="flex flex-wrap items-center gap-3 @4xl:shrink-0 @4xl:justify-end">
          {children}
        </div>
      )}
    </div>
  )
}
