/**
 * 场景组装专用 Store
 * 使用 Zustand 管理场景组装相关的状态
 */
import { create } from 'zustand'
import { message } from 'antd'
import api from '../services/api'
import { useProjectStore } from './project'
import type {
  Module,
  Scenario,
  ModuleDependency,
  ModuleChain,
  TaskProgress,
  Environment,
  ScenarioDetail,
  ModuleDetail
} from '../types/scenario'

interface ScenarioStore {
  // ==================== 模块相关状态 ====================
  modules: Module[]
  selectedModuleIds: number[]
  moduleDetail: ModuleDetail | null
  moduleDetailVisible: boolean

  // ==================== 场景相关状态 ====================
  scenarios: Scenario[]
  currentScenario: ScenarioDetail | null

  // ==================== 依赖相关状态 ====================
  dependencies: ModuleDependency[]
  dependencyGraphVisible: boolean

  // ==================== 链路相关状态 ====================
  moduleChains: ModuleChain[]
  internalChains: any[]  // [SCENARIO-A-SOLUTION] 内部链路列表

  // ==================== 任务相关状态 ====================
  currentTaskId: number | null
  taskProgress: TaskProgress | null

  // ==================== 环境相关状态 ====================
  environments: Environment[]
  selectedEnvironmentId: number | null

  // ==================== 加载状态 ====================
  loadingModules: boolean
  loadingScenarios: boolean
  loadingDependencies: boolean
  loadingChains: boolean
  loadingModuleDetail: boolean
  loadingInternalChains: boolean  // [SCENARIO-A-SOLUTION] 内部链路加载状态
  analyzing: boolean
  analyzingCrossModule: boolean

  // ==================== 模块相关 Actions ====================
  loadModules: () => Promise<void>
  analyzeModule: (moduleId: number) => Promise<void>
  analyzeAllModules: () => Promise<void>
  analyzeSelectedModules: () => Promise<void>
  analyzeCrossModuleDependencies: () => Promise<void>
  viewModuleDetail: (module: Module) => Promise<void>
  setModuleDetailVisible: (visible: boolean) => void
  setSelectedModuleIds: (ids: number[]) => void

  // ==================== 场景相关 Actions ====================
  loadScenarios: () => Promise<void>
  loadScenarioDetail: (scenarioId: number) => Promise<void>
  executeScenario: (scenarioId: number, environmentId: number) => Promise<any>
  updateScenario: (scenarioId: number, data: Partial<ScenarioDetail>) => Promise<void>
  deleteScenario: (scenarioId: number) => Promise<void>
  loadScenarioExecutions: (scenarioId: number, page?: number, pageSize?: number, status?: string) => Promise<any>
  loadScenarioExecutionDetail: (scenarioId: number, executionId: number) => Promise<any>

  // ==================== 依赖相关 Actions ====================
  loadDependencies: () => Promise<void>
  setDependencyGraphVisible: (visible: boolean) => void

  // ==================== 链路相关 Actions ====================
  loadModuleChains: () => Promise<void>
  loadInternalChains: (moduleId: number) => Promise<void>  // [SCENARIO-A-SOLUTION] 加载内部链路
  createModuleChain: (data: {
    chain_name: string
    description?: string
    module_chain: number[]
  }) => Promise<void>
  deleteModuleChain: (chainId: number) => Promise<void>

  // ==================== 任务相关 Actions ====================
  refreshTaskProgress: (taskId?: number) => Promise<void>
  setCurrentTaskId: (taskId: number | null) => void

  // ==================== 环境相关 Actions ====================
  loadEnvironments: () => Promise<void>
  setSelectedEnvironmentId: (id: number | null) => void

  // ==================== 清理方法 ====================
  reset: () => void
}

export const useScenarioStore = create<ScenarioStore>((set, get) => ({
  // ==================== 初始状态 ====================
  modules: [],
  selectedModuleIds: [],
  moduleDetail: null,
  moduleDetailVisible: false,

  scenarios: [],
  currentScenario: null,

  dependencies: [],
  dependencyGraphVisible: false,

  moduleChains: [],
  internalChains: [],

  currentTaskId: null,
  taskProgress: null,

  environments: [],
  selectedEnvironmentId: null,

  loadingModules: false,
  loadingScenarios: false,
  loadingDependencies: false,
  loadingChains: false,
  loadingModuleDetail: false,
  loadingInternalChains: false,  // [SCENARIO-A-SOLUTION] 内部链路加载状态
  analyzing: false,
  analyzingCrossModule: false,

  // ==================== 模块相关 Actions ====================
  loadModules: async () => {
    const { currentProject } = useProjectStore.getState()
    if (!currentProject?.id) {
      message.warning('请先选择项目')
      return
    }

    set({ loadingModules: true })
    try {
      const response = await api.get(`/api-integration/modules?project_id=${currentProject.id}`)
      if (response.code === 0) {
        set({ modules: response.data.modules || [] })
      } else {
        message.error(response.message || '加载模块列表失败')
      }
    } catch (error: any) {
      message.error(error.message || '加载模块列表失败')
    } finally {
      set({ loadingModules: false })
    }
  },

  analyzeModule: async (moduleId: number) => {
    const { currentProject } = useProjectStore.getState()
    if (!currentProject?.id) return

    try {
      await api.post(`/api-integration/modules/${moduleId}/analyze`, {
        project_id: currentProject.id
      })
      message.success('模块分析任务已创建')
      get().loadModules()
    } catch (error: any) {
      message.error(error.message || '创建模块分析任务失败')
    }
  },

  analyzeAllModules: async () => {
    const { currentProject } = useProjectStore.getState()
    if (!currentProject?.id) return

    set({ analyzing: true })
    try {
      const response = await api.post('/api-integration/modules/analyze-all', {
        project_id: currentProject.id
      })
      if (response.code === 0) {
        const taskId = response.data?.task_id
        if (taskId) {
          set({ currentTaskId: taskId })
          await get().refreshTaskProgress(taskId)
        }
        message.success('模块分析任务已创建，请点击"刷新进度"查看分析状态')
        get().loadModules()
      } else {
        message.error(response.message || '创建分析任务失败')
      }
    } catch (error: any) {
      message.error(error.message || '创建分析任务失败')
    } finally {
      set({ analyzing: false })
    }
  },

  analyzeSelectedModules: async () => {
    const { currentProject } = useProjectStore.getState()
    const { selectedModuleIds } = get()
    if (!currentProject?.id) return
    if (selectedModuleIds.length === 0) {
      message.warning('请先选择要分析的模块')
      return
    }

    set({ analyzing: true })
    try {
      const promises = selectedModuleIds.map(moduleId =>
        api.post(`/api-integration/modules/${moduleId}/analyze`, {
          project_id: currentProject.id
        })
      )
      await Promise.all(promises)
      message.success(`已创建 ${selectedModuleIds.length} 个模块的分析任务`)
      set({ selectedModuleIds: [] })
      await get().loadModules()
    } catch (error: any) {
      message.error(error.message || '创建分析任务失败')
    } finally {
      set({ analyzing: false })
    }
  },

  analyzeCrossModuleDependencies: async () => {
    const { currentProject } = useProjectStore.getState()
    if (!currentProject?.id) return

    set({ analyzingCrossModule: true })
    try {
      const response = await api.post('/api-integration/modules/analyze-cross-module', {
        project_id: currentProject.id
      })
      if (response.code === 0) {
        message.success('模块间依赖分析完成')
        get().loadDependencies()
      } else {
        message.error(response.message || '模块间依赖分析失败')
      }
    } catch (error: any) {
      message.error(error.message || '模块间依赖分析失败')
    } finally {
      set({ analyzingCrossModule: false })
    }
  },

  viewModuleDetail: async (module: Module) => {
    try {
      const response = await api.get(`/api-integration/modules/${module.id}/status`)
      if (response.code === 0) {
        const moduleData = response.data
        // [SCENARIO-A-SOLUTION] 处理内部链路数据 - 使用详细数据
        const internalChains = (moduleData.internal_chains_detail || []).map((chain: any[], index: number) => ({
          chain_id: index + 1,
          step_count: chain.length,
          start_endpoint: chain[0] || null,
          end_endpoint: chain[chain.length - 1] || null,
          steps: chain
        }))
        set({ 
          moduleDetail: moduleData, 
          moduleDetailVisible: true,
          internalChains  // [SCENARIO-A-SOLUTION] 同时设置内部链路
        })
      }
    } catch (error: any) {
      message.error(error.message || '加载模块详情失败')
    }
  },

  setModuleDetailVisible: (visible: boolean) => {
    set({ moduleDetailVisible: visible })
  },

  setSelectedModuleIds: (ids: number[]) => {
    set({ selectedModuleIds: ids })
  },

  // ==================== 场景相关 Actions ====================
  loadScenarios: async () => {
    const { currentProject } = useProjectStore.getState()
    if (!currentProject) {
      message.warning('请先选择项目')
      return
    }

    set({ loadingScenarios: true })
    try {
      // BSK-SC-021: 更新为新的 API 路径
      const response = await api.get(`/scenarios?project_id=${currentProject.id}`)
      if (response.code === 0) {
        set({ scenarios: response.data.items || [] })
      } else {
        message.error(response.message || '加载场景列表失败')
      }
    } catch (error: any) {
      message.error(error.message || '加载场景列表失败')
    } finally {
      set({ loadingScenarios: false })
    }
  },

  loadScenarioDetail: async (scenarioId: number) => {
    try {
      // BSK-SC-021: 更新为新的 API 路径
      const response = await api.get(`/scenarios/${scenarioId}`)
      if (response.code === 0) {
        set({ currentScenario: response.data })
      } else {
        message.error(response.message || '获取场景详情失败')
      }
    } catch (error: any) {
      message.error(error.message || '获取场景详情失败')
    }
  },

  executeScenario: async (scenarioId: number, environmentId: number) => {
    try {
      // BSK-SC-021: 更新为新的 API 路径
      const response = await api.post(`/scenarios/${scenarioId}/execute`, {
        environment_id: environmentId,
      })
      return response.data
    } catch (error: any) {
      message.error(error.message || '场景执行失败')
      throw error
    }
  },

  updateScenario: async (scenarioId: number, data: Partial<ScenarioDetail>) => {
    try {
      // BSK-SC-021: 更新为新的 API 路径
      const response = await api.put(`/scenarios/${scenarioId}`, data)
      if (response.code === 0) {
        message.success('场景保存成功')
        get().loadScenarios()
      } else {
        message.error(response.message || '场景保存失败')
      }
    } catch (error: any) {
      message.error(error.message || '场景保存失败')
      throw error
    }
  },

  deleteScenario: async (scenarioId: number) => {
    try {
      // BSK-SC-021: 更新为新的 API 路径
      const response = await api.delete(`/scenarios/${scenarioId}`)
      if (response.code === 0) {
        message.success('场景删除成功')
        get().loadScenarios()
      } else {
        message.error(response.message || '场景删除失败')
      }
    } catch (error: any) {
      message.error(error.message || '场景删除失败')
      throw error
    }
  },

  loadScenarioExecutions: async (scenarioId: number, page: number = 1, pageSize: number = 20, status?: string) => {
    try {
      // BSK-SC-021: 更新为新的 API 路径
      const skip = Math.max(page - 1, 0) * pageSize
      let url = `/scenarios/${scenarioId}/executions?skip=${skip}&limit=${pageSize}`
      if (status) {
        url += `&status=${status}`
      }
      const response = await api.get(url)
      if (response.code === 0) {
        return response.data
      } else {
        message.error(response.message || '获取执行历史失败')
        return null
      }
    } catch (error: any) {
      message.error(error.message || '获取执行历史失败')
      return null
    }
  },

  loadScenarioExecutionDetail: async (scenarioId: number, executionId: number) => {
    try {
      // BSK-SC-021: 更新为新的 API 路径
      const response = await api.get(`/scenarios/${scenarioId}/executions/${executionId}`)
      if (response.code === 0) {
        return response.data
      } else {
        message.error(response.message || '获取执行详情失败')
        return null
      }
    } catch (error: any) {
      message.error(error.message || '获取执行详情失败')
      return null
    }
  },

  // ==================== 依赖相关 Actions ====================
  loadDependencies: async () => {
    const { currentProject } = useProjectStore.getState()
    if (!currentProject?.id) return

    set({ loadingDependencies: true })
    try {
      const response = await api.get(`/api-integration/modules/dependencies?project_id=${currentProject.id}`)
      if (response.code === 0) {
        set({ dependencies: response.data.dependencies || [] })
      }
    } catch (error: any) {
      message.error(error.message || '加载模块间依赖失败')
    } finally {
      set({ loadingDependencies: false })
    }
  },

  setDependencyGraphVisible: (visible: boolean) => {
    set({ dependencyGraphVisible: visible })
  },

  // ==================== 链路相关 Actions ====================
  loadModuleChains: async () => {
    const { currentProject } = useProjectStore.getState()
    if (!currentProject?.id) return

    set({ loadingChains: true })
    try {
      const response = await api.get(`/api-integration/modules/chains?project_id=${currentProject.id}`)
      if (response.code === 0) {
        set({ moduleChains: response.data.chains || [] })
      }
    } catch (error: any) {
      message.error(error.message || '加载模块链路列表失败')
    } finally {
      set({ loadingChains: false })
    }
  },

  // [SCENARIO-A-SOLUTION] 加载内部链路 - 修正：从 moduleDetail 中获取，不单独调用接口
  loadInternalChains: async (_moduleId: number) => {
    // 内部链路数据已经包含在 moduleDetail 中，无需额外调用接口
    // moduleDetail.internal_chains 包含了链路数据
    set({ loadingInternalChains: false })
  },

  createModuleChain: async (data) => {
    const { currentProject } = useProjectStore.getState()
    if (!currentProject) {
      message.warning('请先选择项目')
      return
    }
    try {
      const response = await api.post('/api-integration/modules/compose', {
        project_id: currentProject.id,
        ...data
      })
      if (response.code === 0) {
        message.success('跨模块场景组合成功')
        get().loadModuleChains()
        get().loadScenarios()
      } else {
        message.error(response.message || '跨模块场景组合失败')
      }
    } catch (error: any) {
      message.error(error.message || '跨模块场景组合失败')
      throw error
    }
  },

  deleteModuleChain: async (chainId: number) => {
    try {
      const response = await api.delete(`/api-integration/modules/chains/${chainId}`)
      if (response.code === 0) {
        message.success('删除成功')
        get().loadModuleChains()
      } else {
        message.error(response.message || '删除失败')
      }
    } catch (error: any) {
      message.error(error.message || '删除失败')
      throw error
    }
  },

  // ==================== 任务相关 Actions ====================
  refreshTaskProgress: async (taskId?: number) => {
    const targetTaskId = taskId || get().currentTaskId
    
    // 严格检查：必须是有效的整数且大于0
    if (!targetTaskId || !Number.isInteger(targetTaskId) || targetTaskId <= 0) {
      message.warning('没有可查询的任务')
      return
    }

    try {
      const response = await api.get(`/api-integration/scenarios/analyze/progress/${targetTaskId}`)
      if (response.code === 0) {
        const taskData = response.data
        set({ taskProgress: taskData })

        if (taskData.status === 'completed') {
          message.success('模块分析完成')
          get().loadModules()
          setTimeout(() => {
            set({ currentTaskId: null, taskProgress: null })
          }, 5000)
        } else if (taskData.status === 'failed') {
          message.error(`分析失败: ${taskData.error_message || '未知错误'}`)
        }
      } else {
        message.error(response.message || '刷新进度失败')
      }
    } catch (error: any) {
      message.error(error.message || '刷新进度失败')
    }
  },

  setCurrentTaskId: (taskId: number | null) => {
    set({ currentTaskId: taskId })
  },

  // ==================== 环境相关 Actions ====================
  loadEnvironments: async () => {
    const { currentProject } = useProjectStore.getState()
    if (!currentProject) return

    try {
      const response = await api.get(`/environments?project_id=${currentProject.id}`)
      if (response.code === 0) {
        const envs = response.data.environments || []
        set({ environments: envs })
        if (envs.length > 0 && !get().selectedEnvironmentId) {
          set({ selectedEnvironmentId: envs[0].id })
        }
      }
    } catch (error: any) {
      message.error(error.message || '加载环境列表失败')
    }
  },

  setSelectedEnvironmentId: (id: number | null) => {
    set({ selectedEnvironmentId: id })
  },

  // ==================== 清理方法 ====================
  reset: () => {
    set({
      modules: [],
      selectedModuleIds: [],
      moduleDetail: null,
      moduleDetailVisible: false,
      scenarios: [],
      currentScenario: null,
      dependencies: [],
      dependencyGraphVisible: false,
      moduleChains: [],
        internalChains: [],  // [SCENARIO-A-SOLUTION] 内部链路列表
        currentTaskId: null,      taskProgress: null,
      environments: [],
      selectedEnvironmentId: null,
      loadingModules: false,
      loadingScenarios: false,
      loadingDependencies: false,
      loadingChains: false,
      analyzing: false,
      analyzingCrossModule: false,
    })
  },
}))
