import { createFileRoute, useNavigate } from '@tanstack/react-router'
import {
  DashboardPage,
  type DashboardSearch,
  type Period,
} from '@/features/dashboard/dashboard-page'

const PERIODS: Period[] = ['today', 'month', '7d', '30d', 'prev-month']

export const Route = createFileRoute('/_app/')({
  validateSearch: (search: Record<string, unknown>): DashboardSearch => ({
    period: PERIODS.includes(search.period as Period) ? (search.period as Period) : undefined,
  }),
  component: DashboardRoute,
})

function DashboardRoute() {
  const search = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  return <DashboardPage search={search} onSearchChange={(next) => navigate({ search: next })} />
}
