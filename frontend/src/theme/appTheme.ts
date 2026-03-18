import { theme, type ThemeConfig } from 'antd'
import type { ThemeMode } from '../preferences/AppPreferencesProvider'

export const getAntdTheme = (mode: ThemeMode): ThemeConfig => {
  const isDark = mode === 'dark'

  return {
    algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: '#0d6c63',
      colorSuccess: '#3c8a61',
      colorWarning: '#c79b2b',
      colorError: '#cb5c2f',
      colorInfo: '#0d6c63',
      colorBgBase: isDark ? '#101715' : '#f3efe7',
      colorBgLayout: isDark ? '#101715' : '#f3efe7',
      colorBgContainer: isDark ? '#18211e' : '#fffaf2',
      colorTextBase: isDark ? '#eef3ef' : '#1f2520',
      colorBorder: isDark ? 'rgba(228, 236, 230, 0.12)' : 'rgba(31, 37, 32, 0.12)',
      borderRadius: 16,
      boxShadowSecondary: isDark
        ? '0 18px 40px rgba(0, 0, 0, 0.35)'
        : '0 18px 40px rgba(33, 35, 31, 0.12)',
      fontFamily: '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
    },
    components: {
      Layout: {
        bodyBg: 'transparent',
        headerBg: 'transparent',
        siderBg: 'transparent',
      },
      Button: {
        borderRadius: 999,
        controlHeight: 38,
      },
      Card: {
        borderRadiusLG: 20,
      },
      Input: {
        borderRadius: 14,
      },
      Select: {
        borderRadius: 14,
      },
      Dropdown: {
        borderRadiusOuter: 16,
      },
    },
  }
}
