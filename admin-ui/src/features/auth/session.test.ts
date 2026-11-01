import { QueryClient } from '@tanstack/react-query'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/http'
import { me } from '@/test/fixtures'
import { server } from '@/test/msw-server'
import { API } from '@/test/render-app'
import { checkSessionAfter } from './session'

describe('checkSessionAfter', () => {
  it('sends to login when the session is gone', async () => {
    server.use(http.get(`${API}/auth/me/`, () => HttpResponse.json({}, { status: 403 })))
    const queryClient = new QueryClient()
    queryClient.setQueryData(['x'], 1)
    const onExpired = vi.fn()

    await checkSessionAfter(new ApiError(403, {}), queryClient, onExpired)

    expect(onExpired).toHaveBeenCalledOnce()
    expect(queryClient.getQueryData(['x'])).toBeUndefined()
  })

  it('keeps the user when it was only a missing permission', async () => {
    server.use(http.get(`${API}/auth/me/`, () => HttpResponse.json(me)))
    const onExpired = vi.fn()

    await checkSessionAfter(new ApiError(403, {}), new QueryClient(), onExpired)
    await checkSessionAfter(new ApiError(500, {}), new QueryClient(), onExpired)

    expect(onExpired).not.toHaveBeenCalled()
  })
})
