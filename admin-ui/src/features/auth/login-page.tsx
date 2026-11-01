import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Eye, EyeOff, Loader2, Zap } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { getStaffMeQueryKey, staffCsrf, staffLogin } from '@/shared/api/generated/staff'
import { ApiError } from '@/shared/api/http'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { BrandMark } from '../layout/brand'

const schema = z.object({
  phone_number: z.string().trim().min(9, 'Введите номер телефона'),
  password: z.string().min(1, 'Введите пароль'),
})

type LoginValues = z.infer<typeof schema>

/** Вход той же учётной записью, что и в /admin/; сессия общая. */
export function LoginPage({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [showPassword, setShowPassword] = useState(false)
  const form = useForm<LoginValues>({
    resolver: zodResolver(schema),
    defaultValues: { phone_number: '', password: '' },
  })
  const login = useMutation({
    mutationFn: async (values: LoginValues) => {
      await staffCsrf() // кука csrftoken для POST
      return staffLogin(values)
    },
    onSuccess: (me) => {
      queryClient.clear()
      queryClient.setQueryData(getStaffMeQueryKey(), me)
      onSuccess()
    },
  })
  const error =
    login.error instanceof ApiError
      ? login.error.message
      : login.error && 'Сервер не отвечает. Проверьте интернет и попробуйте ещё раз.'
  const { errors } = form.formState

  return (
    <main className="grid min-h-svh lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <section className="relative hidden overflow-hidden bg-sidebar p-12 text-sidebar-foreground lg:flex lg:flex-col">
        <div className="flex items-center gap-3">
          <BrandMark />
          <span className="text-xl font-bold text-white">Charger</span>
        </div>
        <div className="relative z-10 mt-auto max-w-[52%] pb-4">
          <h2 className="text-[2.6rem] leading-[1.08] font-semibold text-white">
            Вся зарядная сеть на&nbsp;виду
          </h2>
          <p className="mt-5 text-lg leading-relaxed text-sidebar-foreground/80">
            Станции, сессии зарядки и платежи в одной панели. Команды станциям отправляются отсюда
            же.
          </p>
        </div>
        <Zap
          aria-hidden
          className="pointer-events-none absolute top-1/2 right-[6%] size-56 -translate-y-1/2 rotate-[-8deg] text-primary/25"
          strokeWidth={1.25}
        />
      </section>

      <section className="flex items-center justify-center px-5 py-12 sm:px-10">
        <div className="w-full max-w-md">
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <BrandMark />
            <span className="text-xl font-bold">Charger</span>
          </div>
          <h1 className="text-3xl font-semibold sm:text-4xl">Вход в панель</h1>
          <p className="mt-3 text-base text-muted-foreground">
            Вход тем же номером и паролем, что в старой админке.
          </p>

          <form
            noValidate
            className="mt-10 grid gap-6"
            onSubmit={form.handleSubmit((values) => login.mutate(values))}
          >
            <div className="grid gap-2.5">
              <Label htmlFor="phone">Телефон</Label>
              <Input
                id="phone"
                type="tel"
                inputMode="tel"
                autoComplete="username"
                placeholder="0555 123 456"
                className="h-12 font-mono text-lg tracking-wide"
                aria-invalid={Boolean(errors.phone_number) || undefined}
                {...form.register('phone_number')}
              />
              {errors.phone_number && (
                <p className="text-sm text-destructive">{errors.phone_number.message}</p>
              )}
            </div>
            <div className="grid gap-2.5">
              <Label htmlFor="password">Пароль</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  className="h-12 pr-12 text-lg"
                  aria-invalid={Boolean(errors.password) || undefined}
                  {...form.register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  className="absolute top-1/2 right-2 grid size-9 -translate-y-1/2 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
                </button>
              </div>
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
            {error && (
              <p
                role="alert"
                className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-[0.95rem] text-destructive"
              >
                {error}
              </p>
            )}
            <Button type="submit" size="lg" className="mt-2 w-full" disabled={login.isPending}>
              {login.isPending ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <ArrowRight className="size-5" />
              )}
              Войти
            </Button>
          </form>

          <p className="mt-10 text-sm text-muted-foreground">
            Нужен раздел, которого здесь пока нет?{' '}
            <a href="/admin/" className="font-semibold text-primary hover:underline">
              Откройте классическую админку
            </a>
          </p>
        </div>
      </section>
    </main>
  )
}
