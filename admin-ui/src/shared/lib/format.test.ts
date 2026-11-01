import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime, formatMoney, formatPhone, formatTime } from './format'

// Intl uses non-breaking / narrow spaces as group separators; normalise for assertions.
const plain = (s: string) => s.replace(/[  ]/g, ' ')

describe('formatMoney', () => {
  it('formats integers with group separators and the сом suffix', () => {
    expect(plain(formatMoney(1234567))).toBe('1 234 567 сом')
  })

  it('keeps up to two fractional digits with a comma', () => {
    expect(plain(formatMoney(1234.5))).toBe('1 234,5 сом')
    expect(plain(formatMoney(0.125))).toBe('0,13 сом')
  })

  it('accepts decimal strings from the API', () => {
    expect(plain(formatMoney('99.90'))).toBe('99,9 сом')
  })

  it('rejects non-numeric input', () => {
    expect(() => formatMoney('abc')).toThrow(RangeError)
  })
})

describe('dates in Asia/Bishkek (UTC+6)', () => {
  const utc = '2026-10-21T20:30:00Z' // 02:30 next day in Bishkek

  it('formatDate shifts to the Bishkek calendar day', () => {
    expect(formatDate(utc)).toBe('22.10.2026')
  })

  it('formatDateTime includes 24h time', () => {
    expect(formatDateTime(utc)).toBe('22.10.2026, 02:30')
  })

  it('formatTime returns HH:mm', () => {
    expect(formatTime(new Date(utc))).toBe('02:30')
  })

  it('rejects invalid dates', () => {
    expect(() => formatDate('not a date')).toThrow(RangeError)
  })
})

describe('formatPhone', () => {
  it('groups Kyrgyz numbers in any input form', () => {
    expect(formatPhone('+996705133000')).toBe('+996 705 133 000')
    expect(formatPhone('996705133000')).toBe('+996 705 133 000')
    expect(formatPhone('0705 133 000')).toBe('+996 705 133 000')
  })

  it('leaves other numbers as they are', () => {
    expect(formatPhone('+7 900 123-45-67')).toBe('+7 900 123-45-67')
  })
})
