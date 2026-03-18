import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import App from './App'
import './index.css'
import { AppPreferencesProvider, useAppPreferences } from './preferences/AppPreferencesProvider'
import { getAntdTheme } from './theme/appTheme'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const AppRuntime = () => {
  const { locale, themeMode } = useAppPreferences()

  return (
    <ConfigProvider
      locale={locale === 'zh-CN' ? zhCN : enUS}
      theme={getAntdTheme(themeMode)}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppPreferencesProvider>
        <AppRuntime />
      </AppPreferencesProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
