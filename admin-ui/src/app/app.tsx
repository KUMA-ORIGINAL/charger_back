import { RouterProvider } from '@tanstack/react-router'
import { Providers } from '@/app/providers'
import { queryClient, router } from '@/app/router'

export function App() {
  return (
    <Providers queryClient={queryClient}>
      <RouterProvider router={router} />
    </Providers>
  )
}
