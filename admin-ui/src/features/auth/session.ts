import { type QueryClient, queryOptions } from '@tanstack/react-query'
import { redirect } from '@tanstack/react-router'
import { getStaffMeQueryKey, staffMe } from '@/shared/api/generated/staff'
import { ApiError } from '@/shared/api/http'

export const meQuery = () =>
  queryOptions({
    queryKey: getStaffMeQueryKey(),
    queryFn: ({ signal }) => staffMe({ signal }),
    staleTime: 5 * 60_000,
    retry: false,
  })

/** beforeLoad закрытых маршрутов: без сессии — на /login с возвратом обратно. */
export async function requireSession(queryClient: QueryClient, href: string) {
  try {
    return await queryClient.ensureQueryData(meQuery())
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      throw redirect({ to: '/login', search: { redirect: href } })
    }
    throw error
  }
}

let checking = false

/**
 * Ответ 401/403 посреди работы — либо нет прав, либо сессия истекла (выход в
 * другой вкладке, смена пароля). Различаем повторным запросом профиля: если
 * и он отказан, сессии нет — отправляем на вход и после него вернём обратно.
 */
export async function checkSessionAfter(
  error: unknown,
  queryClient: QueryClient,
  onExpired: () => void,
) {
  if (!(error instanceof ApiError) || (error.status !== 401 && error.status !== 403)) return
  if (checking) return
  checking = true
  try {
    await staffMe()
  } catch (meError) {
    if (meError instanceof ApiError && (meError.status === 401 || meError.status === 403)) {
      queryClient.clear()
      onExpired()
    }
  } finally {
    checking = false
  }
}
