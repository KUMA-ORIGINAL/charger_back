import { createContext, type ReactNode, useContext, useEffect, useState } from 'react'

/**
 * Светлая/тёмная тема без inline-скриптов: CSP админки (`script-src 'self'`)
 * их запрещает, поэтому next-themes не подходит. Класс `dark` на <html>
 * ставит этот провайдер; до первого рендера страница в теме системы.
 */

export type Theme = 'light' | 'dark' | 'system'
type Resolved = 'light' | 'dark'

const STORAGE_KEY = 'charger-theme'
const media = () => window.matchMedia('(prefers-color-scheme: dark)')

interface ThemeState {
  theme: Theme
  resolvedTheme: Resolved
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeState | null>(null)

function readStored(): Theme {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStored)
  const [systemDark, setSystemDark] = useState(() => media().matches)

  useEffect(() => {
    const query = media()
    const listener = (event: MediaQueryListEvent) => setSystemDark(event.matches)
    query.addEventListener('change', listener)
    return () => query.removeEventListener('change', listener)
  }, [])

  const resolvedTheme: Resolved = theme === 'system' ? (systemDark ? 'dark' : 'light') : theme

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', resolvedTheme === 'dark')
    root.style.colorScheme = resolvedTheme
  }, [resolvedTheme])

  const setTheme = (next: Theme) => {
    setThemeState(next)
    try {
      if (next === 'system') localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Приватный режим: тема просто не запомнится.
    }
  }

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeState {
  const state = useContext(ThemeContext)
  if (!state) throw new Error('useTheme вне ThemeProvider')
  return state
}
