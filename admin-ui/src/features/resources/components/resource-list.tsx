import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  type RowSelectionState,
  useReactTable,
} from '@tanstack/react-table'
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  Plus,
  Search,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '@/shared/api/http'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Checkbox } from '@/shared/ui/checkbox'
import { Input } from '@/shared/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { Skeleton } from '@/shared/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import { exportRows, listQuery } from '../api'
import { ValueView } from '../fields/value-view'
import { type ListSearch, rememberListSearch } from '../list-search'
import type { ResourceMeta, Row } from '../types'
import { ActionButton, reportActionResult } from './action-button'
import { FiltersPanel, QuickFilter } from './filters-panel'
import { ListTabs } from './list-tabs'
import { PageHeader } from './page-header'
import { ResourceIcon } from './resource-icon'

/** Список ресурса — аналог changelist Django admin, целиком из /meta/. */

interface ResourceListProps {
  meta: ResourceMeta
  search: ListSearch
  onSearchChange: (next: ListSearch) => void
}

export function ResourceList({ meta, search, onSearchChange }: ResourceListProps) {
  const navigate = useNavigate()
  const query = useQuery(listQuery(meta.key, search, meta.auto_refresh))
  const [selection, setSelection] = useState<RowSelectionState>({})
  const [exporting, setExporting] = useState(false)
  const bulkActions = meta.actions.filter((action) => !action.detail)
  const tabsFilter = meta.list_tabs
    ? meta.list_filter.find((filter) => filter.name === meta.list_tabs)
    : undefined
  const selectable = bulkActions.length > 0

  // Выбор относится к странице: при смене фильтров и страницы он сбрасывается.
  // biome-ignore lint/correctness/useExhaustiveDependencies: сброс именно по смене search
  useEffect(() => setSelection({}), [search])
  useEffect(() => rememberListSearch(meta.key, search), [meta.key, search])

  const update = (patch: Partial<ListSearch>) =>
    onSearchChange({ ...search, page: undefined, ...patch })
  const ordering = search.ordering ?? meta.ordering[0] ?? ''

  // biome-ignore lint/correctness/useExhaustiveDependencies: update пересоздаётся на каждый рендер, колонкам он нужен только как обработчик
  const columns = useMemo<ColumnDef<Row>[]>(() => {
    const result: ColumnDef<Row>[] = meta.list_display.map((column) => ({
      id: column.name,
      header: () =>
        column.sortable ? (
          <SortHeader
            label={column.label}
            name={column.name}
            ordering={ordering}
            onSort={(next) => update({ ordering: next })}
          />
        ) : (
          column.label
        ),
      cell: ({ row }) => {
        const value = <ValueView compact meta={column} value={row.original[column.name]} />
        // Строка кликабельна мышью, а первая колонка из list_display_links — ещё
        // и настоящая ссылка: открывается с клавиатуры и в новой вкладке.
        if (column.name !== meta.list_display_links[0]) return value
        return (
          <Link
            to="/r/$resource/$id"
            params={{ resource: meta.key, id: row.original.id }}
            className="font-medium hover:underline"
            onClick={(event) => event.stopPropagation()}
          >
            {value}
          </Link>
        )
      },
    }))
    if (selectable) {
      result.unshift({
        id: '__select',
        header: ({ table }) => (
          <Checkbox
            aria-label="Выбрать все на странице"
            checked={
              table.getIsAllPageRowsSelected() ||
              (table.getIsSomePageRowsSelected() && 'indeterminate')
            }
            onCheckedChange={(value) => table.toggleAllPageRowsSelected(Boolean(value))}
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            aria-label="Выбрать строку"
            checked={row.getIsSelected()}
            onClick={(event) => event.stopPropagation()}
            onCheckedChange={(value) => row.toggleSelected(Boolean(value))}
          />
        ),
      })
    }
    return result
  }, [meta, ordering, selectable])

  const table = useReactTable({
    data: query.data?.results ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => String(row.id),
    manualPagination: true,
    manualSorting: true,
    enableRowSelection: selectable,
    state: { rowSelection: selection },
    onRowSelectionChange: setSelection,
  })

  // Суммы и количества — по правому краю: так разряды встают друг под другом.
  const numericColumns = new Set(
    meta.list_display
      .filter((column) => column.format === 'money' || NUMERIC_TYPES.has(column.type))
      .map((column) => column.name),
  )
  const selectedIds = Object.keys(selection).map(Number)
  const pageSize = query.data?.page_size ?? meta.per_page
  const total = query.data?.count ?? 0
  const page = search.page ?? 1
  const pages = Math.max(1, Math.ceil(total / pageSize))

  const download = async () => {
    setExporting(true)
    try {
      reportActionResult(await exportRows(meta.key, search))
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : 'Не удалось выгрузить')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={meta.label_plural}
        description={
          query.data ? `${total.toLocaleString('ru-RU')} ${countLabel(total)}` : undefined
        }
      >
        {meta.links.map((link) => (
          <Button key={link.to} variant="outline" asChild>
            {/* Путь особого экрана приходит с бэкенда строкой — типов роутера у него нет. */}
            <Link to={link.to as never}>
              {link.icon && <ResourceIcon name={link.icon} />}
              {link.label}
            </Link>
          </Button>
        ))}
        {meta.export && (
          <Button variant="outline" onClick={download} disabled={exporting}>
            {exporting ? <Loader2 className="animate-spin" /> : <Download />}
            Скачать Excel
          </Button>
        )}
        {meta.permissions.add && (
          <Button asChild>
            <Link to="/r/$resource/new" params={{ resource: meta.key }}>
              <Plus />
              Добавить
            </Link>
          </Button>
        )}
      </PageHeader>

      <div className="overflow-hidden rounded-2xl border border-border/70 bg-card shadow-[0_1px_2px_rgb(14_38_34/0.04),0_8px_24px_-12px_rgb(14_38_34/0.12)]">
        <div className="flex flex-col gap-3 border-b border-border/70 p-4 sm:flex-row sm:flex-wrap sm:items-center">
          {meta.search.enabled && (
            <SearchBox
              initial={search.search ?? ''}
              placeholder={meta.search.help ? `Поиск: ${meta.search.help.toLowerCase()}` : 'Поиск'}
              onSearch={(value) => update({ search: value || undefined })}
            />
          )}
          <FiltersPanel
            resource={meta.key}
            filters={meta.list_filter}
            values={search.filters ?? {}}
            onChange={(filters) => update({ filters })}
            resultCount={query.data?.count}
          />
        </div>

        {tabsFilter && (
          <div className="border-b border-border/70">
            <ListTabs
              filter={tabsFilter}
              column={meta.list_display.find((column) => column.name === tabsFilter.name)}
              counts={query.data?.tab_counts}
              value={search.filters?.[tabsFilter.name]}
              onChange={(value) => {
                const filters = { ...search.filters }
                if (value === undefined) delete filters[tabsFilter.name]
                else filters[tabsFilter.name] = value
                update({ filters: Object.keys(filters).length ? filters : undefined })
              }}
            />
          </div>
        )}

        {!tabsFilter && meta.list_filter.some((filter) => filter.type === 'choice') && (
          <div className="border-b border-border/70 px-4 py-3 empty:hidden">
            <QuickFilter
              filters={meta.list_filter}
              values={search.filters ?? {}}
              onChange={(filters) => update({ filters })}
            />
          </div>
        )}

        {selectedIds.length > 0 && (
          <div className="flex flex-wrap items-center gap-3 border-b border-border/70 bg-accent/60 px-4 py-3">
            <span className="font-semibold">Выбрано: {selectedIds.length}</span>
            {bulkActions.map((action) => (
              <ActionButton
                key={action.name}
                resource={meta.key}
                action={action}
                target={selectedIds}
                onDone={() => setSelection({})}
              />
            ))}
            <Button variant="ghost" size="sm" onClick={() => setSelection({})}>
              Снять выбор
            </Button>
          </div>
        )}

        <Table>
          <TableHeader className="bg-muted/40">
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id} className="hover:bg-transparent">
                {group.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className={cn(
                      'group/head',
                      header.id === '__select' && 'w-12',
                      numericColumns.has(header.id) && 'text-right',
                    )}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody className={cn('transition-opacity', query.isPlaceholderData && 'opacity-60')}>
            {query.isPending &&
              Array.from({ length: 6 }, (_, index) => (
                <TableRow key={`skeleton-${String(index)}`}>
                  {columns.map((column) => (
                    <TableCell key={column.id}>
                      <Skeleton className="h-5 w-full max-w-36" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            {query.isError && (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-16 text-center text-destructive">
                  {query.error instanceof ApiError
                    ? query.error.message
                    : 'Список не загрузился. Обновите страницу.'}
                </TableCell>
              </TableRow>
            )}
            {query.isSuccess && table.getRowModel().rows.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={columns.length} className="py-16 text-center">
                  <p className="text-lg font-bold">Ничего не нашлось</p>
                  <p className="mt-1 text-muted-foreground">
                    {search.search || Object.keys(search.filters ?? {}).length
                      ? 'Измените поиск или сбросьте фильтры.'
                      : 'Здесь пока пусто.'}
                  </p>
                </TableCell>
              </TableRow>
            )}
            {table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                data-state={row.getIsSelected() ? 'selected' : undefined}
                className="cursor-pointer"
                onClick={() =>
                  navigate({
                    to: '/r/$resource/$id',
                    params: { resource: meta.key, id: row.original.id },
                  })
                }
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell
                    key={cell.id}
                    className={cn('max-w-xs', numericColumns.has(cell.column.id) && 'text-right')}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <div className="flex flex-col gap-3 border-t border-border/70 px-4 py-3 text-[0.95rem] text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span>
              {total > 0
                ? `Показаны ${((page - 1) * pageSize + 1).toLocaleString('ru-RU')}-${Math.min(page * pageSize, total).toLocaleString('ru-RU')} из ${total.toLocaleString('ru-RU')}`
                : 'Нет записей'}
            </span>
            {total > PAGE_SIZES[0] && (
              <Select
                value={String(pageSize)}
                onValueChange={(value) =>
                  update({ page_size: Number(value) === meta.per_page ? undefined : Number(value) })
                }
              >
                <SelectTrigger size="sm" aria-label="Строк на странице" className="w-auto gap-1.5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[...new Set([...PAGE_SIZES, meta.per_page])]
                    .sort((a, b) => a - b)
                    .map((size) => (
                      <SelectItem key={size} value={String(size)}>
                        по {size}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => onSearchChange({ ...search, page: page - 1 })}
            >
              <ChevronLeft />
              Назад
            </Button>
            <span className="px-2 font-semibold text-foreground tabular-nums">
              {page} / {pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= pages}
              onClick={() => onSearchChange({ ...search, page: page + 1 })}
            >
              Вперёд
              <ChevronRight />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

const NUMERIC_TYPES = new Set(['integer', 'decimal', 'number'])

/** Сколько строк показать на странице; бэкенд отдаёт не больше 200. */
const PAGE_SIZES = [25, 50, 100, 200]

function countLabel(n: number) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'запись'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'записи'
  return 'записей'
}

function SortHeader({
  label,
  name,
  ordering,
  onSort,
}: {
  label: string
  name: string
  ordering: string
  onSort: (ordering: string) => void
}) {
  const direction = ordering === name ? 'asc' : ordering === `-${name}` ? 'desc' : null
  const Icon = direction === 'asc' ? ArrowUp : direction === 'desc' ? ArrowDown : ArrowUpDown
  return (
    <button
      type="button"
      className="-mx-1 inline-flex items-center gap-1 rounded px-1 hover:text-foreground"
      onClick={() => onSort(direction === 'asc' ? `-${name}` : name)}
    >
      {label}
      <Icon className={cn('size-3', !direction && 'opacity-0 group-hover/head:opacity-40')} />
    </button>
  )
}

/** Поиск по Enter или после паузы в наборе — не дёргаем API на каждую букву. */
function SearchBox({
  initial,
  placeholder,
  onSearch,
}: {
  initial: string
  placeholder: string
  onSearch: (value: string) => void
}) {
  const [value, setValue] = useState(initial)
  useEffect(() => setValue(initial), [initial])
  useEffect(() => {
    if (value === initial) return
    const timer = setTimeout(() => onSearch(value.trim()), 400)
    return () => clearTimeout(timer)
  }, [value, initial, onSearch])

  return (
    <div className="relative w-full sm:max-w-sm">
      <Search className="pointer-events-none absolute top-1/2 left-3.5 size-5 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        aria-label="Поиск"
        placeholder={placeholder}
        className="pl-11"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') onSearch(value.trim())
        }}
      />
    </div>
  )
}
