import { createFileRoute } from '@tanstack/react-router'
import { requireSession } from '@/features/auth/session'
import { AppLayout } from '@/features/layout/app-layout'
import { metaQuery } from '@/features/resources/meta'

/** Всё, кроме /login, — только для вошедших сотрудников. */
export const Route = createFileRoute('/_app')({
  beforeLoad: async ({ context, location }) => {
    await requireSession(context.queryClient, location.href)
  },
  loader: ({ context }) => context.queryClient.ensureQueryData(metaQuery()),
  component: AppLayout,
})
