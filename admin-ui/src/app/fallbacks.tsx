import { type ErrorComponentProps, Link, useRouter } from '@tanstack/react-router'
import { ApiError } from '@/shared/api/http'
import { Button } from '@/shared/ui/button'

export function NotFound() {
  return (
    <div className="flex flex-col items-start gap-3 py-16">
      <h1 className="text-2xl font-semibold">Страница не найдена</h1>
      <p className="text-muted-foreground">
        Раздела или объекта нет, либо у вас нет к нему доступа.
      </p>
      <Button asChild variant="outline">
        <Link to="/">На главную</Link>
      </Button>
    </div>
  )
}

export function ErrorFallback({ error, reset }: ErrorComponentProps) {
  const router = useRouter()
  const message = error instanceof ApiError ? error.message : 'Не удалось загрузить страницу'
  return (
    <div className="flex flex-col items-start gap-3 py-16">
      <h1 className="text-2xl font-semibold">Что-то пошло не так</h1>
      <p className="text-muted-foreground">{message}</p>
      <Button
        variant="outline"
        onClick={() => {
          reset()
          void router.invalidate()
        }}
      >
        Повторить
      </Button>
    </div>
  )
}
