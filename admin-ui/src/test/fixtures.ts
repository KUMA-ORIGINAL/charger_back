import type { Dashboard, Me, ResourceMeta } from '@/shared/api/generated/model'

export const me: Me = {
  id: 2,
  phone_number: '+996700000002',
  full_name: 'Айбек Владелец',
  role: 'owner',
  role_label: 'Владелец',
  is_superuser: false,
}

const column = (
  name: string,
  label: string,
  type: ResourceMeta['list_display'][number]['type'],
  extra: Partial<ResourceMeta['list_display'][number]> = {},
): ResourceMeta['list_display'][number] => ({
  name,
  label,
  type,
  help_text: '',
  required: false,
  read_only: true,
  computed: false,
  badges: null,
  format: null,
  sortable: true,
  ...extra,
})

export const orderMeta: ResourceMeta = {
  key: 'order',
  label: 'Заказ',
  label_plural: 'Заказы',
  group: 'Продажи',
  icon: 'shopping-cart',
  order: 10,
  hidden: false,
  links: [],
  auto_refresh: 0,
  list_tabs: null,
  permissions: { view: true, add: false, change: true, delete: false },
  list_display: [
    column('id', 'ID', 'integer'),
    column('phone', 'Телефон клиента', 'string'),
    column('status', 'Статус заказа', 'choice', {
      choices: [
        { value: 0, label: 'Заказ оформлен' },
        { value: 3, label: 'Заказ выполнен' },
      ],
      badges: { '0': 'info', '3': 'success' },
    }),
    column('total_price', 'Итоговая цена', 'decimal', { format: 'money' }),
    column('spot', 'Точка заведения', 'fk', { related_resource: 'spot' }),
  ],
  list_display_links: ['id', 'phone'],
  list_filter: [
    {
      name: 'status',
      label: 'Статус заказа',
      type: 'choice',
      choices: [
        { value: 0, label: 'Заказ оформлен' },
        { value: 3, label: 'Заказ выполнен' },
      ],
    },
    { name: 'total_price', label: 'Итоговая цена', type: 'number_range' },
  ],
  search: { enabled: true, help: 'Телефон клиента' },
  ordering: ['-created_at'],
  per_page: 50,
  fields: [],
  fieldsets: [],
  inlines: [],
  actions: [],
  export: true,
}

export const orderRows = [
  {
    id: 5,
    phone: '0555738720',
    status: 3,
    total_price: 1020,
    spot: { id: 1, label: 'ТЦ Дордой Плаза' },
  },
  { id: 1, phone: '0555197251', status: 0, total_price: 170, spot: null },
]

export const dashboard: Dashboard = {
  date_from: '2026-10-01',
  date_to: '2026-10-03',
  summary: {
    revenue: 4500,
    payments: 30,
    sessions: 28,
    kwh: 420.5,
    previous_revenue: 3000,
    previous_payments: 30,
    previous_sessions: 25,
    previous_kwh: 400,
  },
  days: [
    { date: '2026-10-01', sessions: 10, revenue: 1500, kwh: 120 },
    { date: '2026-10-02', sessions: 0, revenue: 0, kwh: 0 },
    { date: '2026-10-03', sessions: 18, revenue: 3000, kwh: 300.5 },
  ],
  stations: [],
  active_sessions: 0,
}

const field = (
  name: string,
  label: string,
  type: ResourceMeta['fields'][number]['type'],
  extra: Partial<ResourceMeta['fields'][number]> = {},
): ResourceMeta['fields'][number] => ({
  name,
  label,
  type,
  help_text: '',
  required: false,
  read_only: false,
  computed: false,
  badges: null,
  format: null,
  ...extra,
})

/** Ресурс с разумными умолчаниями — в тестах задаются только отличия. */
export function resourceMeta(
  extra: Partial<ResourceMeta> & Pick<ResourceMeta, 'key'>,
): ResourceMeta {
  return {
    label: extra.key,
    label_plural: extra.key,
    group: 'Прочее',
    icon: 'table',
    order: 100,
    hidden: false,
    links: [],
    auto_refresh: 0,
    list_tabs: null,
    permissions: { view: true, add: true, change: true, delete: true },
    list_display: [column('id', 'ID', 'integer')],
    list_display_links: ['id'],
    list_filter: [],
    search: { enabled: false, help: '' },
    ordering: ['-id'],
    per_page: 25,
    fields: [],
    fieldsets: [],
    inlines: [],
    actions: [],
    export: false,
    ...extra,
  }
}

export const productMeta = resourceMeta({
  key: 'product',
  label: 'Товар',
  label_plural: 'Товары',
  group: 'Каталог',
  fields: [field('product_price', 'Цена', 'integer')],
  fieldsets: [{ title: 'Цена', fields: ['product_price'] }],
  inlines: [
    {
      name: 'modificators',
      label: 'Модификаторы',
      columns: [
        { name: 'name', label: 'Название', type: 'string', choices: null, format: null },
        { name: 'price', label: 'Цена', type: 'integer', choices: null, format: 'money' },
      ],
      resource: 'modificator',
      fk: 'product',
    },
  ],
  actions: [
    {
      name: 'download_qr_card',
      label: 'Скачать QR-карточку',
      detail: true,
      confirm: null,
      variant: 'default',
      permission: 'change',
      icon: 'qr-code',
      form: null,
    },
    {
      name: 'translate',
      label: 'Перевести',
      detail: true,
      confirm: null,
      variant: 'default',
      permission: 'change',
      icon: null,
      form: null,
    },
  ],
})

export const modificatorMeta = resourceMeta({
  key: 'modificator',
  label: 'Модификатор',
  label_plural: 'Модификаторы',
  group: 'Каталог',
  hidden: true,
  fields: [
    field('name', 'Название', 'string', { required: true }),
    field('price', 'Цена', 'integer', { default: 0 }),
    field('product', 'Товар', 'fk', { related_resource: 'product' }),
  ],
  fieldsets: [{ title: null, fields: ['name', 'price', 'product'] }],
})

export const productRow = {
  id: 7,
  product_price: 90,
  inlines: { modificators: [{ id: 3, name: 'Со льдом', price: 0 }] },
  _actions: {
    download_qr_card: {
      form: [
        {
          name: 'spot',
          label: 'Точка',
          type: 'choice' as const,
          required: true,
          choices: [
            { value: 1, label: 'ТЦ Дордой Плаза' },
            { value: 2, label: 'Бизнес-центр Орион' },
          ],
        },
      ],
    },
  },
}
