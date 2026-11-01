import { useMutation, useQuery, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { ExternalLink, LayoutDashboard, LogOut, Moon, Search, Sun } from 'lucide-react'
import { useState } from 'react'
import { getStaffNavBadgesQueryOptions, staffLogout } from '@/shared/api/generated/staff'
import { formatPhone } from '@/shared/lib/format'
import { useTheme } from '@/shared/lib/theme'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/shared/ui/sidebar'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip'
import { meQuery } from '../auth/session'
import { ResourceIcon } from '../resources/components/resource-icon'
import { useResources } from '../resources/meta'
import type { ResourceMeta } from '../resources/types'
import { BrandMark } from './brand'
import { CommandPalette } from './command-palette'

/**
 * Link роутера помечает активную ссылку `data-status="active"`: активный пункт —
 * просто светлее фон и текст, без рамок и полосок.
 */
const ACTIVE =
  'data-[status=active]:bg-sidebar-accent data-[status=active]:font-medium data-[status=active]:text-sidebar-accent-foreground'

/** Счётчик проблем раздела: непробитые чеки, холодильники, пустые полки. */
function ProblemBadge({ count }: { count?: number }) {
  if (!count) return null
  return (
    <SidebarMenuBadge className="top-1/2! right-2 -translate-y-1/2 bg-destructive/16 text-destructive peer-hover/menu-button:text-destructive peer-data-[active=true]/menu-button:text-destructive">
      <span className="sr-only">Требуют внимания: </span>
      {count > 99 ? '99+' : count}
    </SidebarMenuBadge>
  )
}

/** Меню собирается из /meta/: раздел появляется, как только бэкенд его зарегистрировал и дал права. */
export function AppSidebar() {
  // Скрытые ресурсы (модификаторы, дни графика) правят из карточек, в меню их нет.
  const resources = useResources().filter((resource) => !resource.hidden)
  const { setOpenMobile } = useSidebar()
  const [palette, setPalette] = useState(false)
  const groups = groupBy(resources)
  const close = () => setOpenMobile(false)
  // Проблемы для бейджей меню — раз в минуту, отдельно от тяжёлого дашборда.
  const badges = useQuery({ ...getStaffNavBadgesQueryOptions(), refetchInterval: 60_000 }).data
    ?.badges

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-3 pt-4 pb-2">
        <div className="flex items-center gap-2.5 px-1">
          <Link to="/" onClick={close} aria-label="Charger, на главную" className="shrink-0">
            <BrandMark className="size-9 text-base" />
          </Link>
          <div className="grid min-w-0 flex-1 leading-tight group-data-[collapsible=icon]:hidden">
            <Link to="/" onClick={close} className="truncate text-base font-bold text-white">
              Charger
            </Link>
            <span className="truncate text-xs text-sidebar-foreground/60">Зарядная сеть</span>
          </div>
        </div>
        <SidebarMenu className="mt-3">
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="Поиск и переход (Ctrl+K)"
              className="border border-sidebar-border/60 text-sidebar-foreground/75"
              onClick={() => {
                close()
                setPalette(true)
              }}
            >
              <Search />
              <span>Поиск и переход</span>
              <kbd
                aria-hidden
                className="ml-auto rounded border border-sidebar-border/70 px-1.5 font-sans text-[0.7rem] text-sidebar-foreground/60 group-data-[collapsible=icon]:hidden"
              >
                Ctrl K
              </kbd>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <CommandPalette open={palette} onOpenChange={setPalette} />
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Дашборд" className={ACTIVE}>
                  <Link to="/" activeOptions={{ exact: true }} onClick={close}>
                    <LayoutDashboard />
                    <span>Дашборд</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {groups.map(([group, items]) => (
          <SidebarGroup key={group}>
            <SidebarGroupLabel>{group}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {items.map((resource) => (
                  <SidebarMenuItem key={resource.key}>
                    <SidebarMenuButton asChild tooltip={resource.label_plural} className={ACTIVE}>
                      <Link to="/r/$resource" params={{ resource: resource.key }} onClick={close}>
                        <ResourceIcon name={resource.icon} />
                        <span>{resource.label_plural}</span>
                      </Link>
                    </SidebarMenuButton>
                    <ProblemBadge count={badges?.[resource.key]} />
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}

        <SidebarGroup className="mt-auto">
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Классическая админка">
                  <a href="/admin/">
                    <ExternalLink />
                    <span>Классическая админка</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-3">
        <UserMenu />
      </SidebarFooter>
    </Sidebar>
  )
}

function UserMenu() {
  const { data: me } = useSuspenseQuery(meQuery())
  const { resolvedTheme, setTheme } = useTheme()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const logout = useMutation({
    mutationFn: () => staffLogout(),
    onSuccess: async () => {
      queryClient.clear()
      await navigate({ to: '/login', search: { redirect: undefined } })
    },
  })

  // Без ФИО вместо имени приходит телефон — инициалы тогда из роли, а не «+».
  const initials = [me.full_name, me.role_label]
    .map((text) =>
      text
        .split(/\s+/)
        .filter((part) => /^\p{L}/u.test(part))
        .slice(0, 2)
        .map((part) => part[0])
        .join('')
        .toUpperCase(),
    )
    .find(Boolean)

  return (
    <div className="flex items-center gap-3 rounded-xl bg-sidebar-accent/60 p-2 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:bg-transparent group-data-[collapsible=icon]:p-0">
      <span
        aria-hidden
        className="grid size-9 shrink-0 place-items-center rounded-full bg-sidebar-primary font-semibold text-sidebar-primary-foreground text-sm"
      >
        {initials || '•'}
      </span>
      <div className="grid min-w-0 flex-1 leading-tight group-data-[collapsible=icon]:hidden">
        <span className="truncate text-sm font-semibold text-white">
          {formatPhone(me.full_name)}
        </span>
        <span className="truncate text-xs text-sidebar-foreground/60">{me.role_label}</span>
      </div>
      <div className="flex gap-1 group-data-[collapsible=icon]:flex-col">
        <IconButton
          label={resolvedTheme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
          onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
        >
          {resolvedTheme === 'dark' ? <Sun /> : <Moon />}
        </IconButton>
        <IconButton label="Выйти" onClick={() => logout.mutate()}>
          <LogOut />
        </IconButton>
      </div>
    </div>
  )
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          onClick={onClick}
          className="grid size-8 place-items-center rounded-lg text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-white focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none [&>svg]:size-[1.05rem]"
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top">{label}</TooltipContent>
    </Tooltip>
  )
}

function groupBy(resources: ResourceMeta[]): [string, ResourceMeta[]][] {
  const groups = new Map<string, ResourceMeta[]>()
  for (const resource of [...resources].sort((a, b) => a.order - b.order)) {
    groups.set(resource.group, [...(groups.get(resource.group) ?? []), resource])
  }
  return [...groups.entries()]
}
