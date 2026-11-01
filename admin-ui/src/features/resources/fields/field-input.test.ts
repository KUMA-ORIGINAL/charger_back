import { describe, expect, it } from 'vitest'
import type { FieldMeta } from '../types'
import { JsonFieldError, knownRelated, toApiValue, toFormValue, toLocalInput } from './field-input'

const field = (type: FieldMeta['type'], extra: Partial<FieldMeta> = {}): FieldMeta => ({
  name: 'f',
  label: 'F',
  type,
  help_text: '',
  required: false,
  read_only: false,
  computed: false,
  badges: null,
  format: null,
  ...extra,
})

describe('form value conversion', () => {
  it('maps relations to ids and back', () => {
    expect(toFormValue(field('fk'), { id: 3, label: 'Точка' })).toBe(3)
    expect(
      toFormValue(field('m2m'), [
        { id: 1, label: 'a' },
        { id: 2, label: 'b' },
      ]),
    ).toEqual([1, 2])
    expect(toApiValue(field('m2m'), [1, 2])).toEqual([1, 2])
  })

  it('sends numbers as numbers and empty non-text values as null', () => {
    expect(toApiValue(field('integer'), '42')).toBe(42)
    expect(toApiValue(field('decimal'), '')).toBeNull()
    expect(toApiValue(field('string'), '')).toBe('')
  })

  it('does not resend an unchanged file', () => {
    expect(toApiValue(field('image'), '/media/a.png')).toBeUndefined()
    const file = new File(['x'], 'a.png')
    expect(toApiValue(field('image'), file)).toBe(file)
  })

  it('shows datetimes in Bishkek time for datetime-local inputs', () => {
    expect(toLocalInput('2026-10-21T08:30:00Z')).toBe('2026-10-21T14:30')
  })

  it('edits JSON as text and sends parsed JSON', () => {
    expect(toFormValue(field('json'), [0, 1])).toBe('[\n  0,\n  1\n]')
    expect(toApiValue(field('json'), '{"a": 1}')).toEqual({ a: 1 })
    expect(toApiValue(field('json'), '  ')).toBeNull()
    expect(() => toApiValue(field('json', { name: 'raw' }), '{oops')).toThrow(JsonFieldError)
  })

  it('keeps several choices as a list', () => {
    expect(toFormValue(field('multichoice'), null)).toEqual([])
    expect(toApiValue(field('multichoice'), [0, 4])).toEqual([0, 4])
  })

  it('never prefills a password and skips an empty one', () => {
    expect(toFormValue(field('password'), 'hash')).toBe('')
    expect(toApiValue(field('password'), '')).toBeUndefined()
    expect(toApiValue(field('password'), 'Secret-1')).toBe('Secret-1')
  })

  it('collects known labels of selected relations', () => {
    const row = { id: 1, categories: [{ id: 5, label: 'Напитки' }] }
    expect(knownRelated(row, field('m2m', { name: 'categories' }))).toEqual([
      { id: 5, label: 'Напитки' },
    ])
  })
})
