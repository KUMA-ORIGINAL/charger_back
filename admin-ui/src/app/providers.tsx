import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import type { ReactNode } from 'react'
import { I18nextProvider } from 'react-i18next'
import { i18n } from '@/shared/i18n'
import { ThemeProvider } from '@/shared/lib/theme'
import { Toaster } from '@/shared/ui/sonner'
import { TooltipProvider } from '@/shared/ui/tooltip'

interface ProvidersProps {
  queryClient: QueryClient
  children: ReactNode
}

export function Providers({ queryClient, children }: ProvidersProps) {
  return (
    <ThemeProvider>
      <I18nextProvider i18n={i18n}>
        <QueryClientProvider client={queryClient}>
          <TooltipProvider>
            {children}
            <Toaster richColors closeButton position="top-right" />
          </TooltipProvider>
          {import.meta.env.DEV && <ReactQueryDevtools buttonPosition="top-right" />}
        </QueryClientProvider>
      </I18nextProvider>
    </ThemeProvider>
  )
}
