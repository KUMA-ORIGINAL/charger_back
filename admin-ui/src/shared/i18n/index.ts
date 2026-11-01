import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'
import { type Resources, ru } from './ru'

export const defaultNS = 'translation'

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: typeof defaultNS
    resources: { translation: Resources }
  }
}

export const i18n = i18next.createInstance()

void i18n.use(initReactI18next).init({
  lng: 'ru',
  fallbackLng: 'ru',
  supportedLngs: ['ru'],
  defaultNS,
  resources: { ru: { translation: ru } },
  interpolation: { escapeValue: false },
  initAsync: false,
})
