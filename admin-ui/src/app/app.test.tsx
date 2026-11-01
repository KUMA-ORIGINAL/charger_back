import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { dashboard, me, orderMeta, orderRows } from '@/test/fixtures'
import { server } from '@/test/msw-server'
import { API, renderApp } from '@/test/render-app'

function signedIn() {
  const listRequests: URL[] = []
  server.use(
    http.get(`${API}/auth/me/`, () => HttpResponse.json(me)),
    http.get(`${API}/meta/`, () => HttpResponse.json({ resources: [orderMeta] })),
    http.get(`${API}/resources/order/`, ({ request }) => {
      const url = new URL(request.url)
      listRequests.push(url)
      const status = url.searchParams.get('status')
      const results = status ? orderRows.filter((row) => String(row.status) === status) : orderRows
      return HttpResponse.json({
        count: results.length,
        next: null,
        previous: null,
        page_size: 50,
        results,
      })
    }),
  )
  return { listRequests }
}

describe('admin-ui', () => {
  it('sends anonymous users to the login page and back after signing in', async () => {
    let loggedIn = false
    server.use(
      http.get(`${API}/auth/me/`, () =>
        loggedIn
          ? HttpResponse.json(me)
          : HttpResponse.json({ detail: 'Нужно войти' }, { status: 403 }),
      ),
      http.get(`${API}/auth/csrf/`, () => HttpResponse.json({ detail: 'ok' })),
      http.post(`${API}/auth/login/`, () => {
        loggedIn = true
        return HttpResponse.json(me)
      }),
      http.get(`${API}/meta/`, () => HttpResponse.json({ resources: [orderMeta] })),
      http.get(`${API}/resources/order/`, () =>
        HttpResponse.json({ count: 0, next: null, previous: null, page_size: 50, results: [] }),
      ),
    )
    const { router } = renderApp('/panel/r/order')

    expect(await screen.findByRole('heading', { name: 'Вход в панель' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')

    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Телефон'), '0700000002')
    await user.type(screen.getByLabelText('Пароль'), 'secret')
    await user.click(screen.getByRole('button', { name: 'Войти' }))

    expect(
      await screen.findByRole('heading', { name: 'Заказы' }, { timeout: 5000 }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/r/order')
  })

  it('renders a resource list from meta: badges, money, relations, navigation', async () => {
    signedIn()
    renderApp('/panel/r/order')

    const table = await screen.findByRole('table')
    expect(await within(table).findByText('0555738720')).toBeInTheDocument()
    expect(within(table).getByText('Заказ выполнен')).toBeInTheDocument()
    expect(within(table).getByText('1 020 сом')).toBeInTheDocument()
    expect(within(table).getByRole('link', { name: 'ТЦ Дордой Плаза' })).toHaveAttribute(
      'href',
      '/panel/r/spot/1',
    )
    // Меню собрано из meta.
    expect(screen.getByRole('link', { name: 'Заказы' })).toBeInTheDocument()
  })

  it('applies a filter typed in the filters panel: URL, API and chip', async () => {
    const { listRequests } = signedIn()
    const { router } = renderApp('/panel/r/order')
    await screen.findByRole('table')

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Фильтры' }))
    await user.type(await screen.findByLabelText('Итоговая цена: от'), '500')

    await waitFor(() => expect(router.state.location.href).toContain('total_price__gte=500'))
    await waitFor(() =>
      expect(listRequests.at(-1)?.searchParams.get('total_price__gte')).toBe('500'),
    )
    await user.keyboard('{Escape}') // панель модальная: закрываем, чтобы увидеть чип
    expect(
      screen.getByRole('button', { name: 'Убрать фильтр «Итоговая цена»' }),
    ).toBeInTheDocument()
  })

  it('switches status with the quick filter above the table', async () => {
    const { listRequests } = signedIn()
    const { router } = renderApp('/panel/r/order')
    await screen.findByRole('table')

    const user = userEvent.setup()
    const quick = screen.getByRole('toolbar', { name: 'Статус заказа' })
    await user.click(within(quick).getByRole('button', { name: 'Заказ выполнен' }))

    await waitFor(() => expect(router.state.location.href).toContain('status=3'))
    await waitFor(() => expect(listRequests.at(-1)?.searchParams.get('status')).toBe('3'))
    expect(within(quick).getByRole('button', { name: 'Заказ выполнен' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('passes filters from the URL to the API and shows them as chips', async () => {
    const { listRequests } = signedIn()
    renderApp('/panel/r/order?status=3')

    const table = await screen.findByRole('table')
    expect(await within(table).findByText('0555738720')).toBeInTheDocument()
    expect(within(table).queryByText('0555197251')).not.toBeInTheDocument()
    expect(listRequests.at(-1)?.searchParams.get('status')).toBe('3')
    expect(
      screen.getByRole('button', { name: 'Убрать фильтр «Статус заказа»' }),
    ).toBeInTheDocument()
  })

  it('removes filters: the chip cross and "reset all"', async () => {
    const { listRequests } = signedIn()
    const { router } = renderApp('/panel/r/order?status=3&total_price__gte=500')
    await screen.findByRole('table')
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Убрать фильтр «Статус заказа»' }))
    await waitFor(() => expect(router.state.location.href).not.toContain('status='))
    expect(router.state.location.href).toContain('total_price__gte=500')
    await waitFor(() => expect(listRequests.at(-1)?.searchParams.get('status')).toBeNull())

    await user.click(screen.getByRole('button', { name: /Фильтры/ }))
    await user.click(await screen.findByRole('button', { name: 'Сбросить всё' }))
    await waitFor(() => expect(router.state.location.href).toBe('/r/order'))
    await waitFor(() => expect(listRequests.at(-1)?.searchParams.toString()).toBe(''))
  })

  it('"All" status tab drops the status filter', async () => {
    signedIn()
    server.use(
      http.get(`${API}/meta/`, () =>
        HttpResponse.json({ resources: [{ ...orderMeta, list_tabs: 'status' }] }),
      ),
    )
    const { router } = renderApp('/panel/r/order?status=3')
    await screen.findByRole('table')
    await userEvent.setup().click(screen.getByRole('tab', { name: /^Все/ }))
    await waitFor(() => expect(router.state.location.href).toBe('/r/order'))
  })

  it('shows period totals and stations on the dashboard', async () => {
    signedIn()
    server.use(
      http.get(`${API}/dashboard/`, () =>
        HttpResponse.json({
          ...dashboard,
          stations: [
            {
              id: 1,
              cp_id: 'CP-1',
              name: 'Станция Центр',
              online: true,
              charging: true,
              session_id: 5,
              power_kw: 22,
              soc: 55,
              sessions_today: 3,
            },
          ],
        }),
      ),
    )
    renderApp('/panel/')

    // Главная грузит профиль, /meta/ и сводку по очереди — секунды по умолчанию мало.
    const totals = await screen.findByRole('region', { name: 'Итоги периода' }, { timeout: 5000 })
    expect(await within(totals).findByText('4 500', {}, { timeout: 5000 })).toBeInTheDocument()
    expect(within(totals).getByText('Сессий зарядки')).toBeInTheDocument()

    const station = await screen.findByRole('link', { name: /Станция Центр/ })
    expect(station).toHaveAttribute('href', '/panel/r/chargepoint/1')
    expect(station).toHaveTextContent('Заряжает · 22 кВт · 55%')
  })
})
