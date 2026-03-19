import React, { useEffect, useState } from 'react'
import { Avatar, Dropdown, Input, Select, Tooltip } from 'antd'
import {
  GlobalOutlined,
  LogoutOutlined,
  MoonOutlined,
  SearchOutlined,
  SmileOutlined,
  SunOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { useProjectStore } from '../store/project'
import {
  findNavigationSection,
  navigationSections,
  resolveNavigationState,
} from '../navigation/appNavigation'
import { useAppPreferences } from '../preferences/AppPreferencesProvider'

const MainLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { logout, user } = useAuthStore()
  const {
    initializeFromStorage,
    fetchProjects,
    currentProject,
    currentVersion,
    projects,
    versions,
    setCurrentProject,
    setCurrentVersion,
  } = useProjectStore()
  const { locale, setLocale, themeMode, setThemeMode, t } = useAppPreferences()

  useEffect(() => {
    initializeFromStorage()
    fetchProjects()
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const { section: activeSection, item: activeItem } = resolveNavigationState(location.pathname)
  const navContext = { currentProjectId: currentProject?.id }
  const secondaryItems = activeSection.items.filter((item) => !item.hidden)
  const sectionIcon = activeSection.icon
  const activeItemKey = activeItem.menuKey ?? activeItem.key
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [contextSelectorWidth, setContextSelectorWidth] = useState(120)

  const projectOptions = projects.map((project) => ({
    label: project.name,
    value: project.id,
  }))

  const versionOptions = versions.map((version) => ({
    label: version.version_number,
    value: version.id,
  }))

  useEffect(() => {
    const projectName = currentProject?.name?.trim() || ''
    const fallbackWidth = 120

    if (!projectName) {
      setContextSelectorWidth(fallbackWidth)
      return
    }

    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d')
    if (!context) {
      const estimated = Math.max(96, Math.min(320, projectName.length * 14 + 40))
      setContextSelectorWidth(estimated)
      return
    }

    context.font = '500 13px "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    const measured = Math.ceil(context.measureText(projectName).width)
    const width = Math.max(96, Math.min(320, measured + 40))
    setContextSelectorWidth(width)
  }, [currentProject?.id, currentProject?.name])

  return (
    <div className="app-shell">
      <div className={`app-shell__canvas ${isSidebarCollapsed ? 'is-sidebar-collapsed' : ''}`}>
        <aside className="app-shell__rail">
          <button
            type="button"
            className="app-shell__rail-toggle"
            onClick={() => setIsSidebarCollapsed((prev) => !prev)}
            title={isSidebarCollapsed ? '展开菜单' : '收起菜单'}
          >
            <span
              aria-hidden="true"
              className={`app-shell__rail-toggle-icon ${isSidebarCollapsed ? 'is-plus' : 'is-minus'}`}
            />
          </button>

          <div className="app-shell__brand">
            <div className="app-shell__brand-mark">BS</div>
          </div>

          <nav className="app-shell__rail-nav" aria-label={t('shell.sectionTitle')}>
            {navigationSections.map((section) => {
              const Icon = section.icon
              const isActive = section.key === activeSection.key
              const firstVisibleItem = section.items.find((item) => !item.hidden)
              const sectionLabel = t(section.labelKey, section.shortLabel)
              const itemLabel =
                section.key === activeSection.key
                  ? t(activeItem.labelKey)
                  : firstVisibleItem
                    ? t(firstVisibleItem.labelKey)
                    : ''
              const breadcrumbTitle = itemLabel ? `${sectionLabel} / ${itemLabel}` : sectionLabel

              const railButton = (
                <button
                  type="button"
                  className={`app-shell__rail-button ${isActive ? 'is-active' : ''}`}
                  onClick={() => {
                    const targetSection = findNavigationSection(section.key)
                    const firstVisibleItem = targetSection?.items.find((item) => !item.hidden)

                    if (firstVisibleItem) {
                      navigate(firstVisibleItem.getPath(navContext))
                    }
                  }}
                  title={isSidebarCollapsed ? breadcrumbTitle : sectionLabel}
                >
                  <Icon />
                </button>
              )

              if (isSidebarCollapsed) {
                return (
                  <Tooltip key={section.key} placement="right" title={breadcrumbTitle}>
                    {railButton}
                  </Tooltip>
                )
              }

              return <React.Fragment key={section.key}>{railButton}</React.Fragment>
            })}
          </nav>

          <div className="app-shell__rail-footer">
            <button
              type="button"
              className="app-shell__rail-button"
              onClick={() => setThemeMode(themeMode === 'light' ? 'dark' : 'light')}
              title={t('shell.theme')}
            >
              {themeMode === 'light' ? <MoonOutlined /> : <SunOutlined />}
            </button>
            <button
              type="button"
              className="app-shell__rail-button"
              onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
              title={t('shell.language')}
            >
              <GlobalOutlined />
            </button>
          </div>
        </aside>

        {!isSidebarCollapsed && (
          <aside className="app-shell__sidebar">
            <div className="app-shell__sidebar-head">
              <span className="app-shell__eyebrow">{t('shell.menuTitle')}</span>
              <div className="app-shell__section-title">
                {React.createElement(sectionIcon)}
                <div>
                  <h2>{t(activeSection.labelKey, activeSection.shortLabel)}</h2>
                  <p>{t(activeSection.descriptionKey)}</p>
                </div>
              </div>
            </div>

            <div className="app-shell__menu-list">
              {secondaryItems.map((item) => {
                const Icon = item.icon ?? activeSection.icon
                const key = item.menuKey ?? item.key
                const isActive = key === activeItemKey

                return (
                  <button
                    key={item.key}
                    type="button"
                    className={`app-shell__menu-item ${isActive ? 'is-active' : ''}`}
                    onClick={() => navigate(item.getPath(navContext))}
                  >
                    <span className="app-shell__menu-icon">
                      <Icon />
                    </span>
                    <span className="app-shell__menu-copy">
                      <strong>{t(item.labelKey)}</strong>
                    </span>
                  </button>
                )
              })}
            </div>
          </aside>
        )}

        <main className="app-shell__workspace">
          <header className="app-shell__workspace-topbar">
            <div className="app-shell__search">
              <SearchOutlined />
              <Input
                bordered={false}
                placeholder={t('shell.searchPlaceholder')}
                readOnly
                value=""
              />
              <span className="app-shell__search-hint">{t('shell.searchHint')}</span>
            </div>

            <div className="app-shell__toolbar">
              <div className="app-shell__context-selectors">
                <div
                  className="app-shell__selector-group app-shell__selector-group--project"
                  style={{ width: contextSelectorWidth + 84 }}
                >
                  <span>{t('shell.currentProject')}</span>
                  <Select
                    className="app-shell__selector app-shell__selector--project"
                    style={{ width: contextSelectorWidth }}
                    value={currentProject?.id}
                    options={projectOptions}
                    placeholder={t('shell.noProject')}
                    onChange={(projectId) => {
                      const selectedProject = projects.find((project) => project.id === projectId)
                      if (selectedProject) {
                        setCurrentProject(selectedProject)
                      }
                    }}
                  />
                </div>
                <div
                  className="app-shell__selector-group app-shell__selector-group--version"
                  style={{ width: contextSelectorWidth + 84 }}
                >
                  <span>{t('shell.currentVersion')}</span>
                  <Select
                    className="app-shell__selector app-shell__selector--version"
                    style={{ width: contextSelectorWidth }}
                    value={currentVersion?.id}
                    options={versionOptions}
                    placeholder={t('shell.noVersion')}
                    disabled={!currentProject}
                    onChange={(versionId) => {
                      const selectedVersion = versions.find((version) => version.id === versionId)
                      if (selectedVersion) {
                        setCurrentVersion(selectedVersion)
                      }
                    }}
                  />
                </div>
              </div>

              <Dropdown
                placement="bottomRight"
                menu={{
                  items: [
                    {
                      key: 'profile',
                      icon: <UserOutlined />,
                      label: t('shell.profile'),
                      onClick: () => navigate('/profile'),
                    },
                    {
                      type: 'divider',
                    },
                    {
                      key: 'logout',
                      icon: <LogoutOutlined />,
                      label: t('shell.logout'),
                      onClick: handleLogout,
                    },
                  ],
                }}
              >
                <button
                  type="button"
                  className="app-shell__user-button app-shell__user-button--icon"
                  title={user?.nickname || user?.username || 'User'}
                >
                  <Avatar className="app-shell__user-avatar" icon={<SmileOutlined />} />
                </button>
              </Dropdown>
            </div>
          </header>

          <section className="app-shell__workspace-body">
            <div className="app-shell__content-panel">
              <Outlet />
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}

export default MainLayout
