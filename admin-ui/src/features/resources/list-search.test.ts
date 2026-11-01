import { describe, expect, it } from 'vitest'
import { flattenListSearch, parseListSearch, toQueryString } from './list-search'

describe('list search', () => {
  it('splits reserved keys from filters', () => {
    expect(
      parseListSearch({
        page: 2,
        search: 'кола',
        ordering: '-id',
        status: 1,
        spot: '3',
        empty: '',
      }),
    ).toEqual({
      page: 2,
      page_size: undefined,
      search: 'кола',
      ordering: '-id',
      filters: { status: '1', spot: '3' },
    })
  })

  it('accepts filters nested by navigate() before the route flattens them', () => {
    expect(parseListSearch({ ordering: '-id', filters: { status: '3', empty: '' } })).toMatchObject(
      {
        ordering: '-id',
        filters: { status: '3' },
      },
    )
  })

  it('drops invalid pagination', () => {
    const parsed = parseListSearch({ page: '-1', page_size: 'abc' })
    expect(parsed.page).toBeUndefined()
    expect(parsed.page_size).toBeUndefined()
  })

  it('flattens back to plain URL params, keeping leading zeros as text', () => {
    expect(
      flattenListSearch({
        page: 1,
        filters: { status: '3', phone: '0555', created_at__gte: '2026-10-01' },
      }),
    ).toEqual({ status: 3, phone: '0555', created_at__gte: '2026-10-01' })
  })

  it('round-trips through the router shape', () => {
    const search = { page: 3, search: 'x', filters: { status: '1' } }
    expect(parseListSearch(flattenListSearch(search))).toMatchObject(search)
  })

  it('builds the API query string', () => {
    expect(toQueryString({ page: 2, ordering: '-total_price', filters: { status: '1' } })).toBe(
      'page=2&ordering=-total_price&status=1',
    )
  })
})
