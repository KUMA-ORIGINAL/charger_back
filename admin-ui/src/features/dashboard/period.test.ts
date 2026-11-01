import { describe, expect, it } from 'vitest'
import { periodRange } from './dashboard-page'

// 21.10.2026 03:00 по Бишкеку — по UTC ещё 20.10: период считается по Бишкеку.
const today = new Date('2026-10-20T21:00:00Z')

describe('periodRange', () => {
  it('covers the current month up to today', () => {
    expect(periodRange('month', today)).toEqual({ date_from: '2026-10-01', date_to: '2026-10-21' })
  })

  it('covers the last 7 and 30 days including today', () => {
    expect(periodRange('7d', today)).toEqual({ date_from: '2026-10-15', date_to: '2026-10-21' })
    expect(periodRange('30d', today).date_from).toBe('2026-09-22')
  })

  it('covers the whole previous month', () => {
    expect(periodRange('prev-month', today)).toEqual({
      date_from: '2026-09-01',
      date_to: '2026-09-30',
    })
  })
})
