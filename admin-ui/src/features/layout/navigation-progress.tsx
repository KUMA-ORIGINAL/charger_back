import { useRouterState } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { cn } from '@/shared/lib/utils'

/**
 * Полоса вверху, пока роутер грузит следующую страницу (данные и код
 * маршрута). Без неё клик по ссылке на медленной связи выглядит как «ничего
 * не произошло». Появляется с задержкой, чтобы не мигать на быстрых переходах.
 */
export function NavigationProgress() {
  const pending = useRouterState({ select: (state) => state.status === 'pending' })
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!pending) {
      setVisible(false)
      return
    }
    const timer = setTimeout(() => setVisible(true), 150)
    return () => clearTimeout(timer)
  }, [pending])

  return (
    <div
      aria-hidden
      className={cn(
        'pointer-events-none fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden transition-opacity',
        visible ? 'opacity-100' : 'opacity-0',
      )}
    >
      <div className="nav-progress h-full w-1/3 bg-primary" />
    </div>
  )
}
