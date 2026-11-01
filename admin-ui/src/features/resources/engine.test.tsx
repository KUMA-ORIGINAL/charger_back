import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { modificatorMeta, orderMeta, productMeta, productRow, resourceMeta } from '@/test/fixtures'
import { server } from '@/test/msw-server'
import { API, renderApp, signIn } from '@/test/render-app'

/** Возможности движка ресурсов поверх /meta/: формы действий, инлайны, ссылки, меню. */

function productCard() {
  signIn([orderMeta, productMeta, modificatorMeta])
  const requests: { method: string; url: string; body: unknown }[] = []
  const record = async (request: Request) => {
    const text = await request.text()
    requests.push({
      method: request.method,
      url: request.url,
      body: text ? JSON.parse(text) : null,
    })
  }
  server.use(
    http.get(`${API}/resources/product/7/`, () => HttpResponse.json(productRow)),
    http.patch(`${API}/resources/product/7/`, async ({ request }) => {
      await record(request)
      return HttpResponse.json(productRow)
    }),
    http.post(`${API}/resources/product/7/actions/download_qr_card/`, async ({ request }) => {
      await record(request)
      return HttpResponse.json({ message: 'Карточка готова', level: 'success' })
    }),
    http.post(`${API}/resources/modificator/`, async ({ request }) => {
      await record(request)
      return HttpResponse.json({
        id: 4,
        name: 'Сироп',
        price: 20,
        product: { id: 7, label: 'Кола' },
      })
    }),
  )
  return { requests }
}

describe('resource engine', () => {
  it('asks for the action form and sends it without saving the card', async () => {
    const { requests } = productCard()
    renderApp('/panel/r/product/7')
    const user = userEvent.setup()

    // Первая загрузка карточки (ленивые чанки) под нагрузкой бывает дольше секунды.
    await user.click(
      await screen.findByRole('button', { name: 'Скачать QR-карточку' }, { timeout: 5000 }),
    )
    const dialog = await screen.findByRole('dialog')
    // Без выбора точки не отправляем.
    await user.click(within(dialog).getByRole('button', { name: 'Выполнить' }))
    expect(within(dialog).getByText('Обязательное поле')).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Бизнес-центр Орион' }))
    await user.click(within(dialog).getByRole('button', { name: 'Выполнить' }))

    await waitFor(() => expect(requests).toHaveLength(1))
    expect(requests[0].url).toContain('/actions/download_qr_card/')
    expect(requests[0].body).toEqual({ data: { spot: 2 } })
    // Диалог в портале: его submit не должен всплыть до формы карточки (PATCH).
    expect(requests.some((request) => request.method === 'PATCH')).toBe(false)
  })

  it('shows only actions that the object allows', async () => {
    productCard()
    server.use(
      http.get(`${API}/resources/product/7/`, () =>
        HttpResponse.json({ ...productRow, _actions: { translate: { form: null } } }),
      ),
    )
    renderApp('/panel/r/product/7')

    expect(await screen.findByRole('button', { name: 'Перевести' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Скачать QR-карточку' })).not.toBeInTheDocument()
  })

  it('adds an inline row through its hidden resource with the parent link', async () => {
    const { requests } = productCard()
    renderApp('/panel/r/product/7')
    const user = userEvent.setup()

    const inline = (await screen.findByText('Модификаторы')).closest('[data-slot="card"]')
    expect(inline).not.toBeNull()
    await user.click(within(inline as HTMLElement).getByRole('button', { name: 'Добавить' }))
    const dialog = await screen.findByRole('dialog')
    // Умолчание из модели уже в форме, связь с товаром не спрашиваем.
    expect(within(dialog).getByLabelText('Цена')).toHaveValue(0)
    expect(within(dialog).queryByText('Товар')).not.toBeInTheDocument()

    await user.type(within(dialog).getByLabelText(/Название/), 'Сироп')
    await user.clear(within(dialog).getByLabelText('Цена'))
    await user.type(within(dialog).getByLabelText('Цена'), '20')
    await user.click(within(dialog).getByRole('button', { name: 'Добавить' }))

    await waitFor(() => expect(requests).toHaveLength(1))
    expect(requests[0].body).toEqual({ name: 'Сироп', price: 20, product: 7 })
  })

  it('keeps hidden resources out of the menu', async () => {
    signIn([orderMeta, productMeta, modificatorMeta])
    server.use(
      http.get(`${API}/resources/order/`, () =>
        HttpResponse.json({ count: 0, next: null, previous: null, page_size: 50, results: [] }),
      ),
    )
    renderApp('/panel/r/order')

    expect(await screen.findByRole('link', { name: 'Товары' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Модификаторы' })).not.toBeInTheDocument()
  })

  it('opens a section from the command palette', async () => {
    const sessions = resourceMeta({ key: 'chargingsession', label_plural: 'Сессии зарядки' })
    signIn([orderMeta, sessions])
    server.use(
      http.get(`${API}/resources/order/`, () =>
        HttpResponse.json({ count: 0, next: null, previous: null, page_size: 50, results: [] }),
      ),
      http.get(`${API}/resources/chargingsession/12/`, () => HttpResponse.json({ id: 12 })),
    )
    const { router } = renderApp('/panel/r/order')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Поиск и переход' }))
    const input = await screen.findByPlaceholderText('Раздел, действие или номер сессии…')
    await user.type(input, '12')
    await user.click(await screen.findByRole('option', { name: /Открыть сессию №12/ }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/r/chargingsession/12'))
  })
})

describe('forms and actions', () => {
  it('creates a row and starts a fresh form with "add another"', async () => {
    signIn([orderMeta, modificatorMeta])
    const created: unknown[] = []
    server.use(
      http.post(`${API}/resources/modificator/`, async ({ request }) => {
        created.push(await request.json())
        return HttpResponse.json({ id: 10, name: 'Сироп', price: 20, product: null })
      }),
    )
    const { router } = renderApp('/panel/r/modificator/new')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText(/Название/), 'Сироп')
    await user.click(screen.getByRole('button', { name: 'Создать и добавить ещё' }))

    await waitFor(() => expect(created).toHaveLength(1))
    await waitFor(() => expect(screen.getByLabelText(/Название/)).toHaveValue(''))
    expect(screen.getByLabelText('Цена')).toHaveValue(0)
    expect(router.state.location.pathname).toBe('/r/modificator/new')
  })

  it('opens the object an action created', async () => {
    productCard()
    server.use(
      http.get(`${API}/resources/product/7/`, () =>
        HttpResponse.json({ ...productRow, _actions: { duplicate: { form: null } } }),
      ),
      http.post(`${API}/resources/product/7/actions/duplicate/`, () =>
        HttpResponse.json({
          message: 'Копия создана',
          level: 'success',
          open: { resource: 'product', id: 8 },
        }),
      ),
      http.get(`${API}/resources/product/8/`, () =>
        HttpResponse.json({ ...productRow, id: 8, _actions: {} }),
      ),
    )
    const meta = {
      ...productMeta,
      actions: [
        ...productMeta.actions,
        {
          name: 'duplicate',
          label: 'Сделать копию',
          detail: true,
          confirm: null,
          variant: 'default' as const,
          permission: 'add',
          icon: 'copy',
          form: null,
        },
      ],
    }
    signIn([orderMeta, meta, modificatorMeta])
    const { router } = renderApp('/panel/r/product/7')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Сделать копию' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/r/product/8'))
    expect(await screen.findByRole('heading', { name: 'Товар #8' })).toBeInTheDocument()
  })
})
