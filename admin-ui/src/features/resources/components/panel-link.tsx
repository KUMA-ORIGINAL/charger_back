import { Link, type LinkProps } from '@tanstack/react-router'
import { ArrowUpRight } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { useResources } from '../meta'
import type { LinkValue } from '../types'

/**
 * Куда ведёт ссылка бэкенда: на список раздела с фильтрами («Заказы клиента»),
 * на карточку или на особый экран («Остатки»). Разделы, которых пользователю
 * не видно в /meta/, дают `null` — там была бы 404.
 */
export function usePanelLinkTarget(link: LinkValue): LinkProps | null {
  const resources = useResources()
  if (link.resource) {
    if (!resources.some((resource) => resource.key === link.resource)) return null
    if (link.id !== undefined) {
      return { to: '/r/$resource/$id', params: { resource: link.resource, id: link.id } }
    }
    const filters = Object.fromEntries(
      Object.entries(link.filters ?? {}).map(([key, value]) => [key, String(value)]),
    )
    return { to: '/r/$resource', params: { resource: link.resource }, search: { filters } }
  }
  if (link.to) {
    // Путь особого экрана приходит с бэкенда строкой — роутер его типы не знает.
    return { to: link.to as never, search: (link.search ?? {}) as never }
  }
  return null
}

export function PanelLink({ link, className }: { link: LinkValue; className?: string }) {
  const target = usePanelLinkTarget(link)
  if (!target) return link.resource ? null : <span>{link.label}</span>
  return (
    <Link
      {...target}
      className={cn(
        'inline-flex items-center gap-1 font-semibold text-primary underline-offset-4 hover:underline',
        className,
      )}
      onClick={(event) => event.stopPropagation()}
    >
      {link.label}
      <ArrowUpRight aria-hidden className="size-3.5" />
    </Link>
  )
}

export function isLinkValue(value: unknown): value is LinkValue {
  return (
    typeof value === 'object' &&
    value !== null &&
    'label' in value &&
    ('resource' in value || 'to' in value)
  )
}
