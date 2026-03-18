export type AppLocale = 'zh-CN' | 'en-US'

type MessageTree = {
  [key: string]: string | MessageTree
}

export const messages: Record<AppLocale, MessageTree> = {
  'zh-CN': {
    shell: {
      badge: 'Release Workbench',
      brand: 'BugSeek',
      searchPlaceholder: '搜索页面、命令或资产',
      searchHint: '按 / 快速聚焦',
      language: '语言',
      theme: '主题',
      light: '浅色',
      dark: '深色',
      profile: '个人中心',
      logout: '退出登录',
      workspace: '工作台',
      commandCenter: '指挥台',
      projectContext: '项目上下文',
      projectContextHint: '当前操作默认继承这里的项目与版本。',
      currentProject: '当前项目',
      currentVersion: '当前版本',
      sectionTitle: '导航分区',
      menuTitle: '当前菜单',
      noProject: '未选择项目',
      noVersion: '未选择版本',
      releaseSignal: '发布信号',
      releaseSignalHint: '壳子层先对齐概念稿，业务页在下一阶段逐页迁移。',
      summaryCards: {
        focus: {
          title: '本轮重点',
          value: '壳子重构',
          description: '导航、主题、语言和工作区框架已收口为统一入口。',
        },
        mode: {
          title: '视觉模式',
          value: '双主题',
          description: '浅色对齐概念稿，深色保持同构布局。',
        },
        locale: {
          title: '语言状态',
          value: '双语切换',
          description: '菜单、壳子文案和全局状态支持中英文。',
        },
      },
    },
    nav: {
      overview: {
        label: '总览工作台',
        description: '聚合项目、版本和关键发布信号，优先回答现在该看什么。',
        items: {
          dashboard: {
            label: '发布雷达',
            description: '查看总体状态、执行概览和关键风险。',
          },
          projects: {
            label: '项目空间',
            description: '管理项目入口、成员协作和基础配置。',
          },
          versions: {
            label: '版本节奏',
            description: '围绕当前项目管理版本、里程碑和切换上下文。',
          },
        },
      },
      projectCenter: {
        label: '项目中心',
        description: '项目、版本、环境和鉴权入口。',
        items: {
          projects: {
            label: '项目管理',
            description: '管理项目入口、协作和基础配置。',
          },
          versions: {
            label: '版本管理',
            description: '管理版本切换与里程碑。',
          },
          environments: {
            label: '环境管理',
            description: '管理环境、Header 和变量。',
          },
          authConfig: {
            label: '鉴权配置',
            description: '管理当前项目的鉴权绑定。',
          },
        },
      },
      apiAssets: {
        label: 'API 资产中心',
        description: '统一沉淀接口定义、用例、同步任务和快照资产。',
        items: {
          definitions: {
            label: '接口定义',
            description: '维护接口目录、字段和来源元信息。',
          },
          cases: {
            label: '测试用例',
            description: '查看接口测试用例、断言和执行状态。',
          },
          sync: {
            label: '文档同步',
            description: '管理 OpenAPI 或外部文档同步任务。',
          },
          snapshots: {
            label: '版本快照',
            description: '对比资产快照，跟踪变更和影响范围。',
          },
        },
      },
      scenario: {
        label: '场景编排中心',
        description: '从意图整理到执行闭环，统一管理场景设计和运行过程。',
        items: {
          intentWorkbench: {
            label: '意图工作台',
            description: '整理需求意图、候选流和可执行场景。',
          },
          list: {
            label: '场景目录',
            description: '浏览场景列表、状态和关联资产。',
          },
          detail: {
            label: '场景详情',
            description: '查看场景详情、设计、执行和字段映射。',
          },
          orchestrator: {
            label: '执行编排',
            description: '承接 CI/CD、流程编排和触发策略。',
          },
        },
      },
      operations: {
        label: '运营中心',
        description: '报告、触发和 AI 测试统一入口。',
        items: {
          center: {
            label: '报告与执行触发',
            description: '查看执行报告、触发场景和 AI 测试能力。',
          },
        },
      },
      uiAutomation: {
        label: 'UI 自动化',
        description: '聚焦跨端 UI 自动化任务、编排和回放结果。',
        items: {
          workbench: {
            label: 'UI 工作台',
            description: '集中查看 UI 用例、运行队列和结果。',
          },
        },
      },
      governance: {
        label: '平台与治理',
        description: '管理结构、映射、鉴权、基础设施和质量治理能力。',
        items: {
          dbSchema: {
            label: '数据结构',
            description: '维护版本级数据库结构、DDL 和结构差异。',
          },
          fieldMapping: {
            label: '字段映射',
            description: '管理字段映射规则与发布阶段进度。',
          },
          knowledgeGraph: {
            label: '知识图谱',
            description: '沉淀数据关系、字段链路和关联知识。',
          },
          authConfig: {
            label: '鉴权配置',
            description: '维护项目级鉴权方案和环境绑定。',
          },
          infra: {
            label: '基础设施',
            description: '查看环境、资源和基础支撑能力。',
          },
          requirements: {
            label: '需求洞察',
            description: '沉淀需求分析、缺口和优先级治理。',
          },
          codeQuality: {
            label: '代码质量',
            description: '连接质量指标、静态分析和整改任务。',
          },
        },
      },
    },
    dashboard: {
      heroTitle: '发布雷达',
      heroDescription: '把项目上下文、版本信号、执行进度和关键资产汇总到同一个工作台里，减少在多个菜单和页面之间来回跳转。',
      highlights: {
        structuredNav: '一级导航切到工作流分区，避免顶栏堆叠。',
        globalContext: '项目与版本上下文固定在壳子顶部。',
        visualSystem: '浅色主视觉与概念稿保持一致，深色只换 token。',
      },
      notesTitle: '第一阶段交付',
      notes: {
        nav: '新导航骨架、双侧栏和页头框架已经落位。',
        theme: '支持浅色与深色主题切换，并持久化偏好。',
        locale: '支持中英文切换，后续逐页补全业务文案。',
      },
      metrics: {
        sections: '一级分区',
        themes: '主题模式',
        locales: '语言模式',
      },
      panels: {
        apiAssets: {
          title: 'API 资产中心',
          description: '定义、用例、同步、快照归于一个资产域，后续按模板改造列表与详情页。',
        },
        scenario: {
          title: '场景编排中心',
          description: '意图、设计、执行会重构成连续工作流，而不是分散路由集合。',
        },
        governance: {
          title: '平台与治理',
          description: '数据结构、字段映射、鉴权与基础设施统一到治理域下。',
        },
      },
    },
    auth: {
      loginTitle: '欢迎回来',
      registerTitle: '注册账号',
      username: '用户名',
      email: '邮箱',
      password: '密码',
      confirmPassword: '确认密码',
      nickname: '昵称（可选）',
      login: '登录',
      register: '注册',
      noAccount: '还没有账号？',
      hasAccount: '已有账号？',
      goRegister: '立即注册',
      goLogin: '立即登录',
      loginSuccess: '登录成功',
      registerSuccess: '注册成功，请登录',
      requiredUsername: '请输入用户名',
      requiredEmail: '请输入邮箱',
      requiredPassword: '请输入密码',
      requiredConfirmPassword: '请确认密码',
      invalidEmail: '邮箱格式不正确',
      usernameLength: '用户名长度为 3-50 个字符',
      passwordLength: '密码长度为 6-20 个字符',
      passwordMismatch: '两次输入的密码不一致',
    },
  },
  'en-US': {
    shell: {
      badge: 'Release Workbench',
      brand: 'BugSeek',
      searchPlaceholder: 'Search pages, commands, or assets',
      searchHint: 'Press / to focus',
      language: 'Language',
      theme: 'Theme',
      light: 'Light',
      dark: 'Dark',
      profile: 'Profile',
      logout: 'Sign out',
      workspace: 'Workspace',
      commandCenter: 'Command center',
      projectContext: 'Project context',
      projectContextHint: 'The current project and version are inherited across the workspace.',
      currentProject: 'Current project',
      currentVersion: 'Current version',
      sectionTitle: 'Navigation section',
      menuTitle: 'Current menu',
      noProject: 'No project selected',
      noVersion: 'No version selected',
      releaseSignal: 'Release signal',
      releaseSignalHint: 'Phase 1 aligns the shell to the concept. Business pages move in later phases.',
      summaryCards: {
        focus: {
          title: 'Current focus',
          value: 'Shell redesign',
          description: 'Navigation, theming, locale switching, and workspace framing now share one entry point.',
        },
        mode: {
          title: 'Visual modes',
          value: 'Dual themes',
          description: 'Light mode mirrors the concept. Dark mode keeps the same structure.',
        },
        locale: {
          title: 'Locale state',
          value: 'Bilingual',
          description: 'Menus, shell copy, and global state support Chinese and English.',
        },
      },
    },
    nav: {
      overview: {
        label: 'Overview',
        description: 'Aggregate project, version, and release signals so the next action is obvious.',
        items: {
          dashboard: {
            label: 'Release radar',
            description: 'See overall status, execution coverage, and key risks.',
          },
          projects: {
            label: 'Project space',
            description: 'Manage projects, collaborators, and foundational settings.',
          },
          versions: {
            label: 'Version rhythm',
            description: 'Manage milestones and version switching around the current project.',
          },
        },
      },
      projectCenter: {
        label: 'Project Center',
        description: 'Project, version, environment, and auth entry points.',
        items: {
          projects: {
            label: 'Project management',
            description: 'Manage projects and base settings.',
          },
          versions: {
            label: 'Version management',
            description: 'Manage version switching and milestones.',
          },
          environments: {
            label: 'Environment management',
            description: 'Manage environments, headers, and variables.',
          },
          authConfig: {
            label: 'Auth config',
            description: 'Manage auth bindings for the current project.',
          },
        },
      },
      apiAssets: {
        label: 'API Assets',
        description: 'Unify definitions, cases, sync jobs, and snapshots into one asset domain.',
        items: {
          definitions: {
            label: 'Definitions',
            description: 'Maintain interface catalog, fields, and source metadata.',
          },
          cases: {
            label: 'Test cases',
            description: 'Review API cases, assertions, and execution status.',
          },
          sync: {
            label: 'Document sync',
            description: 'Manage OpenAPI or external document synchronization.',
          },
          snapshots: {
            label: 'Version snapshots',
            description: 'Compare snapshots and track changes with impact scope.',
          },
        },
      },
      scenario: {
        label: 'Scenario Studio',
        description: 'Unify intent shaping, design, and execution into one continuous workflow.',
        items: {
          intentWorkbench: {
            label: 'Intent workbench',
            description: 'Organize intents, candidate flows, and executable scenarios.',
          },
          list: {
            label: 'Scenario catalog',
            description: 'Browse scenarios, states, and linked assets.',
          },
          detail: {
            label: 'Scenario detail',
            description: 'Inspect design, execution, and field mapping in one place.',
          },
          orchestrator: {
            label: 'Execution orchestration',
            description: 'Host CI/CD, workflow orchestration, and trigger strategies.',
          },
        },
      },
      operations: {
        label: 'Operations',
        description: 'Reports, triggers, and AI testing in one place.',
        items: {
          center: {
            label: 'Operations center',
            description: 'Open report, trigger, and AI workflows.',
          },
        },
      },
      uiAutomation: {
        label: 'UI Automation',
        description: 'Focus on cross-surface UI automation, queues, and replay results.',
        items: {
          workbench: {
            label: 'UI workbench',
            description: 'Track UI cases, runs, and result streams.',
          },
        },
      },
      governance: {
        label: 'Platform & Governance',
        description: 'Manage schema, mappings, auth, infrastructure, and quality controls.',
        items: {
          dbSchema: {
            label: 'Schema',
            description: 'Maintain version-level database schema and structure diffs.',
          },
          fieldMapping: {
            label: 'Field mapping',
            description: 'Manage mapping rules and staged delivery progress.',
          },
          knowledgeGraph: {
            label: 'Knowledge graph',
            description: 'Capture relationships, field lineage, and domain knowledge.',
          },
          authConfig: {
            label: 'Auth config',
            description: 'Maintain project-level auth strategies and environment bindings.',
          },
          infra: {
            label: 'Infrastructure',
            description: 'Inspect environments, resources, and support capabilities.',
          },
          requirements: {
            label: 'Requirements',
            description: 'Track analysis gaps, signals, and prioritization.',
          },
          codeQuality: {
            label: 'Code quality',
            description: 'Connect quality metrics, static analysis, and remediation work.',
          },
        },
      },
    },
    dashboard: {
      heroTitle: 'Release radar',
      heroDescription: 'Bring project context, version signals, execution progress, and key assets into one workbench so the team stops bouncing between pages.',
      highlights: {
        structuredNav: 'Primary navigation is grouped by workflow instead of top-bar sprawl.',
        globalContext: 'Project and version context stays pinned in the shell.',
        visualSystem: 'The light theme matches the concept, while dark mode only swaps tokens.',
      },
      notesTitle: 'Phase 1 delivery',
      notes: {
        nav: 'The new navigation shell, dual sidebars, and page framing are in place.',
        theme: 'Light and dark theme switching is supported and persisted.',
        locale: 'Chinese and English switching is enabled. Business copy migrates page by page.',
      },
      metrics: {
        sections: 'Primary sections',
        themes: 'Theme modes',
        locales: 'Locale modes',
      },
      panels: {
        apiAssets: {
          title: 'API Assets',
          description: 'Definitions, cases, sync jobs, and snapshots now belong to a single asset domain.',
        },
        scenario: {
          title: 'Scenario Studio',
          description: 'Intent, design, and execution will be rebuilt as one connected flow.',
        },
        governance: {
          title: 'Platform & Governance',
          description: 'Schema, mappings, auth, and infrastructure move under one governance section.',
        },
      },
    },
    auth: {
      loginTitle: 'Welcome back',
      registerTitle: 'Create account',
      username: 'Username',
      email: 'Email',
      password: 'Password',
      confirmPassword: 'Confirm password',
      nickname: 'Nickname (optional)',
      login: 'Sign in',
      register: 'Sign up',
      noAccount: "Don't have an account?",
      hasAccount: 'Already have an account?',
      goRegister: 'Create one',
      goLogin: 'Sign in now',
      loginSuccess: 'Signed in successfully',
      registerSuccess: 'Registration succeeded. Please sign in.',
      requiredUsername: 'Please enter a username',
      requiredEmail: 'Please enter an email address',
      requiredPassword: 'Please enter a password',
      requiredConfirmPassword: 'Please confirm your password',
      invalidEmail: 'Please enter a valid email address',
      usernameLength: 'Username must be 3-50 characters long',
      passwordLength: 'Password must be 6-20 characters long',
      passwordMismatch: 'The two passwords do not match',
    },
  },
}
