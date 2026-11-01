import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { LoginPage } from '@/features/auth/login-page'

export const Route = createFileRoute('/login')({
  validateSearch: (search: Record<string, unknown>): { redirect?: string } => ({
    redirect: typeof search.redirect === 'string' ? search.redirect : undefined,
  }),
  component: LoginRoute,
})

function LoginRoute() {
  const { redirect } = Route.useSearch()
  const navigate = useNavigate()
  return (
    <LoginPage
      onSuccess={() => {
        // Возвращаем туда, откуда выкинуло, но только внутри админки.
        if (redirect?.startsWith('/') && !redirect.startsWith('//')) {
          void navigate({ href: redirect })
        } else {
          void navigate({ to: '/' })
        }
      }}
    />
  )
}
