import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { messages, type AppLocale } from '../i18n/messages'

export type ThemeMode = 'light' | 'dark'

type TranslationValue = string | number | null | undefined

interface AppPreferencesContextValue {
  locale: AppLocale
  themeMode: ThemeMode
  setLocale: (locale: AppLocale) => void
  setThemeMode: (mode: ThemeMode) => void
  toggleLocale: () => void
  toggleThemeMode: () => void
  t: (key: string, fallback?: string, variables?: Record<string, TranslationValue>) => string
}

const STORAGE_KEY = 'bugseek-app-preferences'

const AppPreferencesContext = createContext<AppPreferencesContextValue | null>(null)

const getByPath = (locale: AppLocale, key: string) => {
  const segments = key.split('.')
  let cursor: unknown = messages[locale]

  for (const segment of segments) {
    if (!cursor || typeof cursor !== 'object' || !(segment in cursor)) {
      return undefined
    }

    cursor = (cursor as Record<string, unknown>)[segment]
  }

  return typeof cursor === 'string' ? cursor : undefined
}

const detectInitialLocale = (): AppLocale => {
  const browserLanguage = typeof navigator !== 'undefined' ? navigator.language : 'zh-CN'

  return browserLanguage.toLowerCase().startsWith('en') ? 'en-US' : 'zh-CN'
}

const detectInitialThemeMode = (): ThemeMode => {
  if (typeof window === 'undefined' || !window.matchMedia) {
    return 'light'
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const AppPreferencesProvider = ({ children }: { children: ReactNode }) => {
  const [locale, setLocaleState] = useState<AppLocale>('zh-CN')
  const [themeMode, setThemeModeState] = useState<ThemeMode>('light')
  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    try {
      const raw = window.localStorage.getItem(STORAGE_KEY)

      if (raw) {
        const parsed = JSON.parse(raw) as Partial<{ locale: AppLocale; themeMode: ThemeMode }>

        setLocaleState(parsed.locale === 'en-US' ? 'en-US' : parsed.locale === 'zh-CN' ? 'zh-CN' : detectInitialLocale())
        setThemeModeState(parsed.themeMode === 'dark' ? 'dark' : parsed.themeMode === 'light' ? 'light' : detectInitialThemeMode())
      } else {
        setLocaleState(detectInitialLocale())
        setThemeModeState(detectInitialThemeMode())
      }
    } catch {
      setLocaleState(detectInitialLocale())
      setThemeModeState(detectInitialThemeMode())
    } finally {
      setInitialized(true)
    }
  }, [])

  useEffect(() => {
    if (!initialized || typeof window === 'undefined') {
      return
    }

    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        locale,
        themeMode,
      }),
    )
  }, [initialized, locale, themeMode])

  useEffect(() => {
    document.documentElement.lang = locale
    document.documentElement.dataset.theme = themeMode
  }, [locale, themeMode])

  const translate = (key: string, fallback = key, variables?: Record<string, TranslationValue>) => {
    const template =
      getByPath(locale, key) ??
      getByPath(locale === 'zh-CN' ? 'en-US' : 'zh-CN', key) ??
      fallback

    if (!variables) {
      return template
    }

    return Object.entries(variables).reduce((text, [name, variable]) => {
      return text.split(`{${name}}`).join(String(variable ?? ''))
    }, template)
  }

  const value: AppPreferencesContextValue = {
    locale,
    themeMode,
    setLocale: setLocaleState,
    setThemeMode: setThemeModeState,
    toggleLocale: () => setLocaleState((current) => (current === 'zh-CN' ? 'en-US' : 'zh-CN')),
    toggleThemeMode: () => setThemeModeState((current) => (current === 'light' ? 'dark' : 'light')),
    t: translate,
  }

  return <AppPreferencesContext.Provider value={value}>{children}</AppPreferencesContext.Provider>
}

export const useAppPreferences = () => {
  const context = useContext(AppPreferencesContext)

  if (!context) {
    throw new Error('useAppPreferences must be used within AppPreferencesProvider')
  }

  return context
}
