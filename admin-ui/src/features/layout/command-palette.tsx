import { useNavigate } from '@tanstack/react-router'
import { Hash, LayoutDashboard, Plus, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from '@/shared/ui/command'
import { ResourceIcon } from '../resources/components/resource-icon'
import { useResources } from '../resources/meta'

/**
 * Быстрый переход: Ctrl+K (⌘K на Mac) — разделы, «Добавить …», поиск по
 * разделу и заказ по номеру. Пункты те же, что в меню: из /meta/ и прав.
 */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const resources = useResources().filter((resource) => !resource.hidden)
  const [query, setQuery] = useState('')
  const searchable = resources.filter((resource) => resource.search.enabled)
  const trimmed = query.trim()
  const number = /^#?\d+$/.test(trimmed) ? Number(trimmed.replace('#', '')) : null
  const sessions = resources.find((resource) => resource.key === 'chargingsession')

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        onOpenChange(!open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  const go = (action: () => void) => {
    onOpenChange(false)
    setQuery('')
    action()
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Быстрый переход"
      description="Раздел, действие или номер сессии"
    >
      <CommandInput
        placeholder="Раздел, действие или номер сессии…"
        value={query}
        onValueChange={setQuery}
      />
      <CommandList className="max-h-[min(70dvh,28rem)]">
        <CommandEmpty>Ничего не нашлось</CommandEmpty>
        {number !== null && sessions && (
          <CommandGroup heading="Сессия">
            <CommandItem
              value={`сессия ${trimmed}`}
              onSelect={() =>
                go(() =>
                  navigate({
                    to: '/r/$resource/$id',
                    params: { resource: 'chargingsession', id: number },
                  }),
                )
              }
            >
              <Hash />
              Открыть сессию №{number}
            </CommandItem>
          </CommandGroup>
        )}
        <CommandGroup heading="Разделы">
          <CommandItem value="дашборд главная" onSelect={() => go(() => navigate({ to: '/' }))}>
            <LayoutDashboard />
            Дашборд
          </CommandItem>
          {resources.map((resource) => (
            <CommandItem
              key={resource.key}
              value={`${resource.label_plural} ${resource.group}`}
              onSelect={() =>
                go(() => navigate({ to: '/r/$resource', params: { resource: resource.key } }))
              }
            >
              <ResourceIcon name={resource.icon} />
              {resource.label_plural}
              <CommandShortcut>{resource.group}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandGroup heading="Действия">
          {resources
            .filter((resource) => resource.permissions.add)
            .map((resource) => (
              <CommandItem
                key={resource.key}
                value={`добавить ${resource.label} ${resource.label_plural}`}
                onSelect={() =>
                  go(() => navigate({ to: '/r/$resource/new', params: { resource: resource.key } }))
                }
              >
                <Plus />
                Добавить: {resource.label.toLowerCase()}
              </CommandItem>
            ))}
        </CommandGroup>
        {trimmed && number === null && searchable.length > 0 && (
          <CommandGroup heading={`Найти «${trimmed}»`}>
            {searchable.map((resource) => (
              <CommandItem
                key={resource.key}
                // Значение содержит запрос — cmdk не отфильтрует эти пункты.
                value={`${trimmed} поиск ${resource.label_plural}`}
                onSelect={() =>
                  go(() =>
                    navigate({
                      to: '/r/$resource',
                      params: { resource: resource.key },
                      search: { search: trimmed },
                    }),
                  )
                }
              >
                <Search />в разделе «{resource.label_plural}»
                {resource.search.help && <CommandShortcut>{resource.search.help}</CommandShortcut>}
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  )
}
