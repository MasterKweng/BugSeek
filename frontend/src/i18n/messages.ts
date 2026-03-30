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
    environmentManagement: {
      hero: {
        eyebrow: '项目中心',
        title: '环境与变量管理',
        description: '通过真实后端 CRUD 接口统一管理项目环境和环境变量。',
      },
      metrics: {
        environments: '环境数',
        variables: '变量数',
        selectedEnv: '当前环境',
      },
      tabs: {
        environments: '环境',
        variables: '变量',
      },
      actions: {
        refresh: '刷新',
        refreshVariables: '刷新变量',
        newEnvironment: '新建环境',
        newVariable: '新建变量',
        edit: '编辑',
        delete: '删除',
        vars: '变量',
      },
      columns: {
        actions: '操作',
        environment: {
          name: '名称',
          baseUrl: '基础 URL',
          default: '默认',
          headers: '请求头',
          variables: '变量',
        },
        variable: {
          key: '键',
          value: '值',
          sensitive: '敏感',
        },
      },
      labels: {
        environment: '环境',
        defaultEnvironment: '默认环境',
        headersJson: '请求头 JSON',
        variablesJson: '变量 JSON',
      },
      placeholders: {
        selectEnvironment: '选择环境',
      },
      tags: {
        default: '默认',
        defaultLower: '默认',
        normal: '普通',
        yes: '是',
        no: '否',
      },
      empty: {
        environments: '暂无环境',
        variables: '暂无变量',
        selectEnvironmentToManageVariables: '请选择一个环境来管理变量',
      },
      confirm: {
        deleteEnvironmentTitle: '确认删除该环境？',
        deleteVariableTitle: '确认删除该变量？',
        deleteDescription: '该操作不可撤销。',
      },
      modals: {
        editEnvironment: '编辑环境',
        newEnvironment: '新建环境',
        editVariable: '编辑变量',
        newVariable: '新建变量',
      },
      validation: {
        enterName: '请输入名称',
        enterBaseUrl: '请输入基础 URL',
        enterHeadersJson: '请输入请求头 JSON',
        enterVariablesJson: '请输入变量 JSON',
        enterKey: '请输入键',
        enterValue: '请输入值',
      },
      messages: {
        loadEnvironmentsFailed: '加载环境失败',
        loadVariablesFailed: '加载变量失败',
        selectEnvironmentFirst: '请先选择环境',
        environmentUpdated: '环境已更新',
        environmentCreated: '环境已创建',
        saveEnvironmentFailed: '保存环境失败',
        environmentDeleted: '环境已删除',
        deleteEnvironmentFailed: '删除环境失败',
        variableUpdated: '变量已更新',
        variableCreated: '变量已创建',
        saveVariableFailed: '保存变量失败',
        variableDeleted: '变量已删除',
        deleteVariableFailed: '删除变量失败',
        selectProjectFirst: '请先选择项目',
      },
    },
    operationsCenter: {
      hero: {
        eyebrow: '运营中心',
        title: '报告、触发与 AI 测试',
        description: '在同一个工作台中操作真实的场景报告、执行触发与 AI 测试接口。',
      },
      metrics: {
        scenarios: '场景数',
        environments: '环境数',
        selectedScenario: '当前场景',
        selectedEnvironment: '当前环境',
        selectedExecution: '当前执行',
      },
      tabs: {
        trigger: '触发',
        reports: '报告',
        aiTesting: 'AI 测试',
      },
      labels: {
        scenario: '场景',
        environment: '环境',
        execution: '执行',
        asyncMode: '异步模式',
        callbackUrl: '回调地址',
        includeRca: '包含 RCA',
        intentText: '意图文本',
        jsonPayload: 'JSON 载荷',
        saveDraft: '保存草稿',
      },
      placeholders: {
        selectScenario: '选择场景',
        selectEnvironment: '选择环境',
        selectExecution: '选择执行',
        optionalEnvironment: '可选环境',
      },
      actions: {
        refresh: '刷新',
        trigger: '触发',
        refreshResult: '刷新结果',
        refreshSummary: '刷新摘要',
        downloadHtml: '下载 HTML',
        downloadPdf: '下载 PDF',
        generateScenario: '生成场景',
        generateTest: '生成测试',
        analyzeFailure: '分析失败',
        generateAssertions: '生成断言',
        mapVariables: '映射变量',
        runFull: '运行全流程',
        optimize: '优化',
      },
      cards: {
        latestTriggerResult: '最近一次触发结果',
        summary: '摘要',
        rca: 'RCA',
        latestAiResponse: '最近一次 AI 响应',
      },
      empty: {
        noTriggerResultYet: '暂无触发结果',
        noSummary: '暂无摘要',
        noRcaResult: '暂无 RCA 结果',
        noAiResponseYet: '暂无 AI 响应',
      },
      tags: {
        defaultLower: '默认',
      },
      messages: {
        loadOperationsDataFailed: '加载运营中心数据失败',
        loadExecutionsFailed: '加载执行记录失败',
        loadReportSummaryFailed: '加载报告摘要失败',
        selectScenarioAndEnvironmentFirst: '请先选择场景和环境',
        scenarioTriggered: '场景已触发',
        triggerScenarioFailed: '触发场景失败',
        loadTriggerResultFailed: '加载触发结果失败',
        selectScenarioExecutionFirst: '请先选择场景执行记录',
        downloadReportFailed: '下载报告失败',
        selectProjectFirst: '请先选择项目',
        ai: {
          generateScenario: {
            completed: '场景生成已完成',
            failed: '场景生成失败',
          },
          generateTest: {
            completed: '测试生成已完成',
            failed: '测试生成失败',
          },
          analyzeFailure: {
            completed: '失败分析已完成',
            failed: '失败分析失败',
          },
          generateAssertions: {
            completed: '断言生成已完成',
            failed: '断言生成失败',
          },
          mapVariables: {
            completed: '变量映射已完成',
            failed: '变量映射失败',
          },
          runFullFlow: {
            completed: '全流程运行已完成',
            failed: '全流程运行失败',
          },
          optimizeTests: {
            completed: '测试优化已完成',
            failed: '测试优化失败',
          },
        },
      },
    },
    uiAutomationWorkbench: {
      hero: {
        eyebrow: '自动化',
        title: 'UI 执行工作台',
        description: '通过真实 UI Testing API 提交执行任务，并查看结果流。',
        tag: 'UI 自动化',
        note: '这个页面只调用真实的 ui-testing 执行接口。填写执行名称、起始 URL 和步骤 JSON 后即可提交运行。',
      },
      metrics: {
        latestExecution: '最近执行',
        executionStatus: '执行状态',
        stepsPassed: '通过步骤',
      },
      labels: {
        headless: '无头模式',
        executionId: '执行 ID',
        status: '状态',
        steps: '步骤',
        duration: '耗时',
      },
      placeholders: {
        caseName: '执行名称',
        startUrl: '起始 URL',
        stepsJson: '[{"name":"打开首页","action":"goto","value":"https://your-app"}]',
      },
      actions: {
        runTask: '运行任务',
        refreshResult: '刷新结果',
      },
      cards: {
        executionInput: '执行输入',
        executionResult: '执行结果',
      },
      table: {
        name: '名称',
        action: '动作',
        status: '状态',
        message: '信息',
      },
      empty: {
        noSteps: '暂无步骤',
        resultPlaceholder: '运行后，执行日志和结果会显示在这里。',
      },
      messages: {
        selectProjectFirst: '请先选择项目',
        enterExecutionName: '请输入执行名称',
        enterStartUrl: '请输入起始 URL',
        invalidStepsJson: '步骤 JSON 格式不正确',
        executionCompleted: '执行完成，记录 #{executionId}',
        executionFailed: 'UI 自动化执行失败',
        loadExecutionResultFailed: '加载执行结果失败',
        noProjectContext: '当前没有选择项目上下文。请先在顶部栏选择项目，再发起运行。',
      },
    },
    knowledgeGraphPage: {
      hero: {
        eyebrow: '治理',
        title: '知识图谱',
        description: '查看 {project} / {version} 下 API、表、字段节点的真实关系，用于依赖分析、写入链路追踪和字段上下文审查。',
      },
      filters: {
        api: '接口',
        table: '表',
        field: '字段',
      },
      metrics: {
        nodeCount: '节点数',
        currentFilter: '当前筛选',
        currentFocus: '当前焦点',
      },
      actions: {
        refresh: '刷新',
        search: '搜索',
      },
      placeholders: {
        search: '按名称、显示名或 source id 搜索',
      },
      cards: {
        catalog: '目录',
        itemsCount: '{count} 项',
        nodeDetail: '节点详情',
      },
      lane: {
        selectNodeTitle: '选择一个节点以查看图谱上下文',
        selectNodeDescription: '无需手动输入 UUID，也能浏览 API、表和字段关系。',
        apiTitle: 'API -> TABLE + FIELD 上下文',
        tableTitle: 'TABLE <- API + FIELD 上下文',
        fieldTitle: 'FIELD <- API / TABLE 上下文',
        apiDescription: '当前 API 连接了 {primary} 个表节点和 {secondary} 个字段节点。',
        tableDescription: '当前表被 {primary} 个 API 引用，并暴露 {secondary} 个字段节点。',
        fieldDescription: '当前字段关联了 {primary} 个 API 和 {secondary} 个表。',
        selected: '已选中',
        noSourceId: '无 source id',
        primary: {
          api: '写入表',
          table: '上游 API',
          field: '关联 API',
        },
        secondary: {
          api: 'API 字段',
          table: '表字段',
          field: '关联表',
        },
      },
      detail: {
        type: '类型',
        name: '名称',
        display: '显示名',
        sourceId: 'Source ID',
        properties: '属性',
      },
      empty: {
        noGraphNodesFound: '未找到图谱节点',
        selectNodeToInspectGraph: '选择一个节点以查看图谱',
        selectNodeToInspectMetadata: '选择一个节点以查看元数据',
        noItems: '没有 {label}',
        noProperties: '没有属性',
      },
      messages: {
        loadNodesFailed: '加载图谱节点失败',
        loadDetailsFailed: '加载图谱详情失败',
        selectProjectAndVersionTitle: '请先选择项目和版本',
        selectProjectAndVersionSubtitle: '知识图谱浏览依赖当前项目和版本上下文。',
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
    environmentManagement: {
      hero: {
        eyebrow: 'Project Center',
        title: 'Environment & Variable Management',
        description: 'Manage project environments and environment variables using the real backend CRUD APIs.',
      },
      metrics: {
        environments: 'Environments',
        variables: 'Variables',
        selectedEnv: 'Selected env',
      },
      tabs: {
        environments: 'Environments',
        variables: 'Variables',
      },
      actions: {
        refresh: 'Refresh',
        refreshVariables: 'Refresh variables',
        newEnvironment: 'New environment',
        newVariable: 'New variable',
        edit: 'Edit',
        delete: 'Delete',
        vars: 'Vars',
      },
      columns: {
        actions: 'Actions',
        environment: {
          name: 'Name',
          baseUrl: 'Base URL',
          default: 'Default',
          headers: 'Headers',
          variables: 'Variables',
        },
        variable: {
          key: 'Key',
          value: 'Value',
          sensitive: 'Sensitive',
        },
      },
      labels: {
        environment: 'Environment',
        defaultEnvironment: 'Default environment',
        headersJson: 'Headers JSON',
        variablesJson: 'Variables JSON',
      },
      placeholders: {
        selectEnvironment: 'Select environment',
      },
      tags: {
        default: 'Default',
        defaultLower: 'default',
        normal: 'Normal',
        yes: 'Yes',
        no: 'No',
      },
      empty: {
        environments: 'No environments',
        variables: 'No variables',
        selectEnvironmentToManageVariables: 'Select an environment to manage variables',
      },
      confirm: {
        deleteEnvironmentTitle: 'Delete this environment?',
        deleteVariableTitle: 'Delete this variable?',
        deleteDescription: 'This action cannot be undone.',
      },
      modals: {
        editEnvironment: 'Edit environment',
        newEnvironment: 'New environment',
        editVariable: 'Edit variable',
        newVariable: 'New variable',
      },
      validation: {
        enterName: 'Please enter a name',
        enterBaseUrl: 'Please enter a base URL',
        enterHeadersJson: 'Please enter headers JSON',
        enterVariablesJson: 'Please enter variables JSON',
        enterKey: 'Please enter a key',
        enterValue: 'Please enter a value',
      },
      messages: {
        loadEnvironmentsFailed: 'Failed to load environments',
        loadVariablesFailed: 'Failed to load variables',
        selectEnvironmentFirst: 'Select an environment first',
        environmentUpdated: 'Environment updated',
        environmentCreated: 'Environment created',
        saveEnvironmentFailed: 'Failed to save environment',
        environmentDeleted: 'Environment deleted',
        deleteEnvironmentFailed: 'Failed to delete environment',
        variableUpdated: 'Variable updated',
        variableCreated: 'Variable created',
        saveVariableFailed: 'Failed to save variable',
        variableDeleted: 'Variable deleted',
        deleteVariableFailed: 'Failed to delete variable',
        selectProjectFirst: 'Select a project first',
      },
    },
    operationsCenter: {
      hero: {
        eyebrow: 'Operations',
        title: 'Report, Trigger, and AI Testing',
        description: 'Operate the real scenario report, execution trigger, and AI testing endpoints from one workspace.',
      },
      metrics: {
        scenarios: 'Scenarios',
        environments: 'Environments',
        selectedScenario: 'Selected scenario',
        selectedEnvironment: 'Selected environment',
        selectedExecution: 'Selected execution',
      },
      tabs: {
        trigger: 'Trigger',
        reports: 'Reports',
        aiTesting: 'AI Testing',
      },
      labels: {
        scenario: 'Scenario',
        environment: 'Environment',
        execution: 'Execution',
        asyncMode: 'Async mode',
        callbackUrl: 'Callback URL',
        includeRca: 'Include RCA',
        intentText: 'Intent text',
        jsonPayload: 'JSON payload',
        saveDraft: 'Save draft',
      },
      placeholders: {
        selectScenario: 'Select scenario',
        selectEnvironment: 'Select environment',
        selectExecution: 'Select execution',
        optionalEnvironment: 'Optional environment',
      },
      actions: {
        refresh: 'Refresh',
        trigger: 'Trigger',
        refreshResult: 'Refresh result',
        refreshSummary: 'Refresh summary',
        downloadHtml: 'Download HTML',
        downloadPdf: 'Download PDF',
        generateScenario: 'Generate scenario',
        generateTest: 'Generate test',
        analyzeFailure: 'Analyze failure',
        generateAssertions: 'Generate assertions',
        mapVariables: 'Map variables',
        runFull: 'Run full',
        optimize: 'Optimize',
      },
      cards: {
        latestTriggerResult: 'Latest trigger result',
        summary: 'Summary',
        rca: 'RCA',
        latestAiResponse: 'Latest AI response',
      },
      empty: {
        noTriggerResultYet: 'No trigger result yet',
        noSummary: 'No summary',
        noRcaResult: 'No RCA result',
        noAiResponseYet: 'No AI response yet',
      },
      tags: {
        defaultLower: 'default',
      },
      messages: {
        loadOperationsDataFailed: 'Failed to load operations data',
        loadExecutionsFailed: 'Failed to load executions',
        loadReportSummaryFailed: 'Failed to load report summary',
        selectScenarioAndEnvironmentFirst: 'Select a scenario and environment first',
        scenarioTriggered: 'Scenario triggered',
        triggerScenarioFailed: 'Failed to trigger scenario',
        loadTriggerResultFailed: 'Failed to load trigger result',
        selectScenarioExecutionFirst: 'Select a scenario execution first',
        downloadReportFailed: 'Failed to download report',
        selectProjectFirst: 'Select a project first',
        ai: {
          generateScenario: {
            completed: 'Generate scenario completed',
            failed: 'Generate scenario failed',
          },
          generateTest: {
            completed: 'Generate test completed',
            failed: 'Generate test failed',
          },
          analyzeFailure: {
            completed: 'Analyze failure completed',
            failed: 'Analyze failure failed',
          },
          generateAssertions: {
            completed: 'Generate assertions completed',
            failed: 'Generate assertions failed',
          },
          mapVariables: {
            completed: 'Map variables completed',
            failed: 'Map variables failed',
          },
          runFullFlow: {
            completed: 'Run full flow completed',
            failed: 'Run full flow failed',
          },
          optimizeTests: {
            completed: 'Optimize tests completed',
            failed: 'Optimize tests failed',
          },
        },
      },
    },
    uiAutomationWorkbench: {
      hero: {
        eyebrow: 'Automation',
        title: 'UI Execution Workbench',
        description: 'Submit executions through the real UI Testing API and inspect the result stream.',
        tag: 'UI Automation',
        note: 'This page only calls the real ui-testing execution endpoint. Fill in the execution name, start URL, and steps JSON, then submit the run.',
      },
      metrics: {
        latestExecution: 'Latest execution',
        executionStatus: 'Execution status',
        stepsPassed: 'Steps passed',
      },
      labels: {
        headless: 'Headless',
        executionId: 'Execution ID',
        status: 'Status',
        steps: 'Steps',
        duration: 'Duration',
      },
      placeholders: {
        caseName: 'Case name',
        startUrl: 'Start URL',
        stepsJson: '[{"name":"Open home","action":"goto","value":"https://your-app"}]',
      },
      actions: {
        runTask: 'Run task',
        refreshResult: 'Refresh result',
      },
      cards: {
        executionInput: 'Execution Input',
        executionResult: 'Execution Result',
      },
      table: {
        name: 'Name',
        action: 'Action',
        status: 'Status',
        message: 'Message',
      },
      empty: {
        noSteps: 'No steps',
        resultPlaceholder: 'Execution logs and results will appear here after a run.',
      },
      messages: {
        selectProjectFirst: 'Please select a project first',
        enterExecutionName: 'Please enter an execution name',
        enterStartUrl: 'Please enter a start URL',
        invalidStepsJson: 'Invalid steps JSON',
        executionCompleted: 'Execution completed, record #{executionId}',
        executionFailed: 'UI automation execution failed',
        loadExecutionResultFailed: 'Failed to load execution result',
        noProjectContext: 'No project context is selected. Choose a project from the top bar before running.',
      },
    },
    knowledgeGraphPage: {
      hero: {
        eyebrow: 'Governance',
        title: 'Knowledge Graph',
        description: 'Browse the real relationships between API, table, and field nodes under {project} / {version} for dependency analysis, write-path tracing, and field context review.',
      },
      filters: {
        api: 'APIs',
        table: 'Tables',
        field: 'Fields',
      },
      metrics: {
        nodeCount: 'Node count',
        currentFilter: 'Current filter',
        currentFocus: 'Current focus',
      },
      actions: {
        refresh: 'Refresh',
        search: 'Search',
      },
      placeholders: {
        search: 'Search by name, display name, or source id',
      },
      cards: {
        catalog: 'Catalog',
        itemsCount: '{count} items',
        nodeDetail: 'Node Detail',
      },
      lane: {
        selectNodeTitle: 'Select a node to inspect its graph context',
        selectNodeDescription: 'Browse APIs, tables, and fields without entering UUIDs.',
        apiTitle: 'API -> TABLE + FIELD context',
        tableTitle: 'TABLE <- API + FIELD context',
        fieldTitle: 'FIELD <- API / TABLE context',
        apiDescription: 'This API currently connects to {primary} tables and {secondary} field nodes.',
        tableDescription: 'This table is currently referenced by {primary} APIs and exposes {secondary} field nodes.',
        fieldDescription: 'This field is attached to {primary} APIs and {secondary} tables.',
        selected: 'Selected',
        noSourceId: 'No source id',
        primary: {
          api: 'Written Tables',
          table: 'Upstream APIs',
          field: 'Related APIs',
        },
        secondary: {
          api: 'API Fields',
          table: 'Table Fields',
          field: 'Related Tables',
        },
      },
      detail: {
        type: 'Type',
        name: 'Name',
        display: 'Display',
        sourceId: 'Source ID',
        properties: 'Properties',
      },
      empty: {
        noGraphNodesFound: 'No graph nodes found',
        selectNodeToInspectGraph: 'Select a node to inspect the graph',
        selectNodeToInspectMetadata: 'Select a node to inspect metadata',
        noItems: 'No {label}',
        noProperties: 'No properties',
      },
      messages: {
        loadNodesFailed: 'Failed to load graph nodes',
        loadDetailsFailed: 'Failed to load graph details',
        selectProjectAndVersionTitle: 'Please select a project and version first',
        selectProjectAndVersionSubtitle: 'Knowledge graph browsing depends on the current project and version context.',
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
