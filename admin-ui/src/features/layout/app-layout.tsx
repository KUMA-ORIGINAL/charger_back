import { Outlet } from '@tanstack/react-router'
import { Suspense } from 'react'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/shared/ui/sidebar'
import { Skeleton } from '@/shared/ui/skeleton'
import { AppSidebar } from './app-sidebar'
import { BrandMark } from './brand'
import { NavigationProgress } from './navigation-progress'

export function AppLayout() {
  return (
    <SidebarProvider className="bg-background">
      <NavigationProgress />
      <AppSidebar />
      <SidebarInset className="min-w-0">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border/60 bg-background/85 px-4 backdrop-blur md:hidden">
          <SidebarTrigger className="size-10" />
          <BrandMark className="size-8 text-sm" />
          <span className="font-bold">Charger</span>
        </header>
        {/* Контент от края меню и во всю ширину, как в макете; предел — только на сверхшироких. */}
        <main className="@container w-full max-w-[120rem] min-w-0 flex-1 px-4 pt-5 pb-10 md:px-7 md:pt-6">
          <Suspense fallback={<PageSkeleton />}>
            <Outlet />
          </Suspense>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

export function PageSkeleton() {
  return (
    <div className="grid gap-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}
