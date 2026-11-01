import { describe, expect, it } from 'vitest'
import type { FieldMeta } from '../types'
import { groupTranslations, isTranslatedGroup } from './translated-field'

const field = (name: string, label: string, type: FieldMeta['type'] = 'string'): FieldMeta => ({
  name,
  label,
  type,
  help_text: '',
  required: false,
  read_only: false,
  computed: false,
  badges: null,
  format: null,
})

describe('groupTranslations', () => {
  it('folds _ru/_ky/_en into one field in RU, KY, EN order and keeps the rest', () => {
    const items = groupTranslations([
      field('product_name_en', 'Название товара [en]'),
      field('product_name_ru', 'Название товара [ru]'),
      field('product_name_ky', 'Название товара [ky]'),
      field('product_price', 'Цена', 'integer'),
    ])
    expect(items).toHaveLength(2)
    const [group, price] = items
    expect(isTranslatedGroup(group) && group.label).toBe('Название товара')
    expect(isTranslatedGroup(group) && group.fields.map((item) => item.name)).toEqual([
      'product_name_ru',
      'product_name_ky',
      'product_name_en',
    ])
    expect(isTranslatedGroup(price)).toBe(false)
  })

  it('leaves a lone language suffix alone', () => {
    const items = groupTranslations([field('code_en', 'Код')])
    expect(isTranslatedGroup(items[0])).toBe(false)
  })
})
