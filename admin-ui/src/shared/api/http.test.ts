import { HttpResponse, http } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'
import { server } from '@/test/msw-server'
import { ApiError, apiFetch, apiFetchMaybeFile, isDownloadedFile } from './http'

describe('apiFetch', () => {
  afterEach(() => {
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
  })

  it('sends the CSRF token on unsafe methods only', async () => {
    document.cookie = 'csrftoken=abc123'
    const seen: Record<string, string | null> = {}
    server.use(
      http.get('/api/x', ({ request }) => {
        seen.get = request.headers.get('X-CSRFToken')
        return HttpResponse.json({ ok: true })
      }),
      http.post('/api/x', ({ request }) => {
        seen.post = request.headers.get('X-CSRFToken')
        return HttpResponse.json({ ok: true })
      }),
    )
    await apiFetch('/api/x')
    await apiFetch('/api/x', { method: 'POST' })
    expect(seen).toEqual({ get: null, post: 'abc123' })
  })

  it('turns DRF validation errors into field errors', async () => {
    server.use(
      http.post('/api/x', () =>
        HttpResponse.json({ categories: ['Обязательное поле.'], name: 'плохо' }, { status: 400 }),
      ),
    )
    const error = await apiFetch('/api/x', { method: 'POST' }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).fieldErrors).toEqual({
      categories: ['Обязательное поле.'],
      name: ['плохо'],
    })
  })

  it('uses the server detail as the message', async () => {
    server.use(
      http.get('/api/x', () =>
        HttpResponse.json({ detail: 'Недостаточно прав.' }, { status: 403 }),
      ),
    )
    await expect(apiFetch('/api/x')).rejects.toThrow('Недостаточно прав.')
  })
})

describe('apiFetchMaybeFile', () => {
  it('returns JSON or a named file', async () => {
    server.use(
      http.post('/api/json', () => HttpResponse.json({ message: 'ok', level: 'success' })),
      http.post(
        '/api/file',
        () =>
          new HttpResponse('PNG', {
            headers: {
              'Content-Type': 'image/png',
              'Content-Disposition': 'attachment; filename="qr_code_spot_1.png"',
            },
          }),
      ),
    )
    expect(await apiFetchMaybeFile('/api/json', { method: 'POST' })).toEqual({
      message: 'ok',
      level: 'success',
    })
    const file = await apiFetchMaybeFile('/api/file', { method: 'POST' })
    expect(isDownloadedFile(file) && file.filename).toBe('qr_code_spot_1.png')
  })
})
