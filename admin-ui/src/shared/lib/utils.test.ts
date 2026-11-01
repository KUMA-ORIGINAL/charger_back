import { describe, expect, it } from 'vitest'
import { cn } from './utils'

describe('cn', () => {
  it('merges conflicting tailwind classes and drops falsy values', () => {
    expect(cn('px-2 py-1', 'px-4', undefined, null)).toBe('py-1 px-4')
  })
})
