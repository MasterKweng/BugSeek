import { GlobalOutlined, MoonOutlined, SunOutlined } from '@ant-design/icons'
import { useAppPreferences } from '../preferences/AppPreferencesProvider'

const AuthPreferenceBar: React.FC = () => {
  const { locale, setLocale, themeMode, setThemeMode, t } = useAppPreferences()

  return (
    <div className="auth-preferences">
      <button
        type="button"
        className={`app-shell__chip ${locale === 'zh-CN' ? 'is-active' : ''}`}
        onClick={() => setLocale('zh-CN')}
        title={t('shell.language')}
      >
        <GlobalOutlined />
        中文
      </button>
      <button
        type="button"
        className={`app-shell__chip ${locale === 'en-US' ? 'is-active' : ''}`}
        onClick={() => setLocale('en-US')}
        title={t('shell.language')}
      >
        <GlobalOutlined />
        EN
      </button>
      <button
        type="button"
        className={`app-shell__chip ${themeMode === 'light' ? 'is-active' : ''}`}
        onClick={() => setThemeMode('light')}
        title={t('shell.theme')}
      >
        <SunOutlined />
        {t('shell.light')}
      </button>
      <button
        type="button"
        className={`app-shell__chip ${themeMode === 'dark' ? 'is-active' : ''}`}
        onClick={() => setThemeMode('dark')}
        title={t('shell.theme')}
      >
        <MoonOutlined />
        {t('shell.dark')}
      </button>
    </div>
  )
}

export default AuthPreferenceBar
