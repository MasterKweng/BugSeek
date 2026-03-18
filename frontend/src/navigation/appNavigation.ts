import type { ComponentType } from 'react'
import {
  ApiOutlined,
  AppstoreOutlined,
  BranchesOutlined,
  BuildOutlined,
  ClusterOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  EnvironmentOutlined,
  FundOutlined,
  HomeOutlined,
  ProjectOutlined,
  RobotOutlined,
  SafetyOutlined,
} from '@ant-design/icons'

type IconComponent = ComponentType<{ className?: string }>
type PathMatcher = string | RegExp

export interface NavigationContext {
  currentProjectId?: number | null
}

export interface NavigationItem {
  key: string
  labelKey: string
  descriptionKey: string
  icon?: IconComponent
  hidden?: boolean
  menuKey?: string
  matchers: PathMatcher[]
  getPath: (context: NavigationContext) => string
}

export interface NavigationSection {
  key: string
  labelKey: string
  shortLabel: string
  descriptionKey: string
  icon: IconComponent
  accent: 'brand' | 'accent' | 'gold' | 'slate'
  items: NavigationItem[]
}

const matchesPath = (pathname: string, matcher: PathMatcher) => {
  if (matcher instanceof RegExp) {
    return matcher.test(pathname)
  }

  if (matcher.endsWith('*')) {
    return pathname.startsWith(matcher.slice(0, -1))
  }

  return pathname === matcher
}

const buildProjectPath = (projectId: number | null | undefined, suffix: string) => {
  if (!projectId) {
    return '/projects'
  }

  return `/projects/${projectId}${suffix}`
}

export const navigationSections: NavigationSection[] = [
  {
    key: 'overview',
    labelKey: 'nav.overview.label',
    shortLabel: 'Home',
    descriptionKey: 'nav.overview.description',
    icon: HomeOutlined,
    accent: 'brand',
    items: [
      {
        key: '/dashboard',
        labelKey: 'nav.overview.items.dashboard.label',
        descriptionKey: 'nav.overview.items.dashboard.description',
        icon: HomeOutlined,
        matchers: ['/', '/dashboard'],
        getPath: () => '/dashboard',
      },
    ],
  },
  {
    key: 'project-center',
    labelKey: 'nav.projectCenter.label',
    shortLabel: 'Project',
    descriptionKey: 'nav.projectCenter.description',
    icon: ProjectOutlined,
    accent: 'accent',
    items: [
      {
        key: '/projects',
        labelKey: 'nav.projectCenter.items.projects.label',
        descriptionKey: 'nav.projectCenter.items.projects.description',
        icon: ProjectOutlined,
        matchers: ['/projects'],
        getPath: () => '/projects',
      },
      {
        key: 'versions',
        menuKey: 'versions',
        labelKey: 'nav.projectCenter.items.versions.label',
        descriptionKey: 'nav.projectCenter.items.versions.description',
        icon: BranchesOutlined,
        matchers: [/^\/projects\/[^/]+\/versions(?:\/|$)/],
        getPath: ({ currentProjectId }) => buildProjectPath(currentProjectId, '/versions'),
      },
      {
        key: '/project-center/environments',
        labelKey: 'nav.projectCenter.items.environments.label',
        descriptionKey: 'nav.projectCenter.items.environments.description',
        icon: EnvironmentOutlined,
        matchers: ['/project-center/environments', '/project-center/environments/*'],
        getPath: () => '/project-center/environments',
      },
      {
        key: 'auth-config',
        menuKey: 'auth-config',
        labelKey: 'nav.projectCenter.items.authConfig.label',
        descriptionKey: 'nav.projectCenter.items.authConfig.description',
        icon: SafetyOutlined,
        matchers: [/^\/projects\/[^/]+\/auth-config(?:\/|$)/],
        getPath: ({ currentProjectId }) => buildProjectPath(currentProjectId, '/auth-config'),
      },
    ],
  },
  {
    key: 'api-assets',
    labelKey: 'nav.apiAssets.label',
    shortLabel: 'API',
    descriptionKey: 'nav.apiAssets.description',
    icon: ApiOutlined,
    accent: 'accent',
    items: [
      {
        key: '/api-hub/definitions',
        labelKey: 'nav.apiAssets.items.definitions.label',
        descriptionKey: 'nav.apiAssets.items.definitions.description',
        icon: ApiOutlined,
        matchers: ['/api-hub/definitions', '/api-hub/definitions/*'],
        getPath: () => '/api-hub/definitions',
      },
      {
        key: '/api-hub/cases',
        labelKey: 'nav.apiAssets.items.cases.label',
        descriptionKey: 'nav.apiAssets.items.cases.description',
        icon: AppstoreOutlined,
        matchers: ['/api-hub/cases', '/api-hub/cases/*'],
        getPath: () => '/api-hub/cases',
      },
      {
        key: '/api-hub/sync',
        labelKey: 'nav.apiAssets.items.sync.label',
        descriptionKey: 'nav.apiAssets.items.sync.description',
        icon: DeploymentUnitOutlined,
        matchers: ['/api-hub/sync', '/api-hub/sync/*'],
        getPath: () => '/api-hub/sync',
      },
      {
        key: '/api-hub/snapshots',
        labelKey: 'nav.apiAssets.items.snapshots.label',
        descriptionKey: 'nav.apiAssets.items.snapshots.description',
        icon: ClusterOutlined,
        matchers: ['/api-hub/snapshots', '/api-hub/snapshots/*'],
        getPath: () => '/api-hub/snapshots',
      },
    ],
  },
  {
    key: 'scenario',
    labelKey: 'nav.scenario.label',
    shortLabel: 'Flow',
    descriptionKey: 'nav.scenario.description',
    icon: ClusterOutlined,
    accent: 'gold',
    items: [
      {
        key: '/scenario/intent-workbench',
        labelKey: 'nav.scenario.items.intentWorkbench.label',
        descriptionKey: 'nav.scenario.items.intentWorkbench.description',
        icon: FundOutlined,
        matchers: ['/scenario/intent-workbench', '/scenario/intent-workbench/*'],
        getPath: () => '/scenario/intent-workbench',
      },
      {
        key: '/scenario/list',
        labelKey: 'nav.scenario.items.list.label',
        descriptionKey: 'nav.scenario.items.list.description',
        icon: AppstoreOutlined,
        matchers: ['/scenario/list'],
        getPath: () => '/scenario/list',
      },
      {
        key: 'scenario-detail',
        menuKey: '/scenario/list',
        labelKey: 'nav.scenario.items.detail.label',
        descriptionKey: 'nav.scenario.items.detail.description',
        icon: AppstoreOutlined,
        hidden: true,
        matchers: [
          /^\/scenario\/[^/]+$/,
          /^\/scenario\/[^/]+\/design(?:\/|$)/,
          /^\/scenario\/[^/]+\/execution\/[^/]+(?:\/|$)/,
          /^\/scenario\/[^/]+\/field-mapping(?:\/|$)/,
        ],
        getPath: () => '/scenario/list',
      },
    ],
  },
  {
    key: 'operations',
    labelKey: 'nav.operations.label',
    shortLabel: 'Ops',
    descriptionKey: 'nav.operations.description',
    icon: DeploymentUnitOutlined,
    accent: 'slate',
    items: [
      {
        key: '/operations',
        labelKey: 'nav.operations.items.center.label',
        descriptionKey: 'nav.operations.items.center.description',
        icon: DeploymentUnitOutlined,
        matchers: ['/operations', '/operations/*'],
        getPath: () => '/operations',
      },
    ],
  },
  {
    key: 'ui-automation',
    labelKey: 'nav.uiAutomation.label',
    shortLabel: 'UI',
    descriptionKey: 'nav.uiAutomation.description',
    icon: RobotOutlined,
    accent: 'brand',
    items: [
      {
        key: '/ui-automation',
        labelKey: 'nav.uiAutomation.items.workbench.label',
        descriptionKey: 'nav.uiAutomation.items.workbench.description',
        icon: RobotOutlined,
        matchers: ['/ui-automation', '/ui-automation/*'],
        getPath: () => '/ui-automation',
      },
    ],
  },
  {
    key: 'governance',
    labelKey: 'nav.governance.label',
    shortLabel: 'Gov',
    descriptionKey: 'nav.governance.description',
    icon: SafetyOutlined,
    accent: 'slate',
    items: [
      {
        key: '/version-center/db-schema',
        labelKey: 'nav.governance.items.dbSchema.label',
        descriptionKey: 'nav.governance.items.dbSchema.description',
        icon: DatabaseOutlined,
        matchers: ['/version-center/db-schema', '/version-center/db-schema/*'],
        getPath: () => '/version-center/db-schema',
      },
      {
        key: '/version-center/field-mapping',
        labelKey: 'nav.governance.items.fieldMapping.label',
        descriptionKey: 'nav.governance.items.fieldMapping.description',
        icon: BuildOutlined,
        matchers: ['/version-center/field-mapping', '/version-center/field-mapping/*'],
        getPath: () => '/version-center/field-mapping',
      },
      {
        key: '/knowledge-graph',
        labelKey: 'nav.governance.items.knowledgeGraph.label',
        descriptionKey: 'nav.governance.items.knowledgeGraph.description',
        icon: ClusterOutlined,
        matchers: ['/knowledge-graph', '/knowledge-graph/*'],
        getPath: () => '/knowledge-graph',
      },
    ],
  },
]

export const findNavigationSection = (sectionKey: string) =>
  navigationSections.find((section) => section.key === sectionKey)

export const resolveNavigationState = (pathname: string) => {
  let matchedSection: NavigationSection | undefined
  let matchedItem: NavigationItem | undefined
  let bestScore = -1

  navigationSections.forEach((section) => {
    section.items.forEach((item) => {
      item.matchers.forEach((matcher) => {
        if (!matchesPath(pathname, matcher)) {
          return
        }

        const score =
          matcher instanceof RegExp
            ? 1000
            : matcher.endsWith('*')
              ? matcher.length - 1
              : matcher.length + 100

        if (score > bestScore) {
          matchedSection = section
          matchedItem = item
          bestScore = score
        }
      })
    })
  })

  return {
    section: matchedSection ?? navigationSections[0],
    item: matchedItem ?? navigationSections[0].items[0],
  }
}
