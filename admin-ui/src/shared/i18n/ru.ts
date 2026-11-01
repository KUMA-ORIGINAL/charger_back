export const ru = {
  app: {
    title: 'Charger Admin',
    placeholder: 'Панель управления в разработке',
  },
  common: {
    save: 'Сохранить',
    cancel: 'Отмена',
    delete: 'Удалить',
    loading: 'Загрузка…',
    error: 'Что-то пошло не так',
  },
} as const

export type Resources = typeof ru
