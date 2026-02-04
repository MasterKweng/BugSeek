/**
 * 场景组装相关类型定义
 */

// ==================== 场景类型 ====================

export type ScenarioStatus = 'active' | 'archived' | 'draft'

export type ScenarioType = 'functional' | 'integration' | 'regression' | 'smoke'

export type ScenarioCategory = 'chain-generated' | 'manual' | 'custom'

export interface Scenario {
  id: number
  name: string
  description?: string
  scenario_type: ScenarioType
  category: ScenarioCategory
  endpoint_count: number
  status: ScenarioStatus
  created_at: string
  updated_at: string
}

export interface ScenarioDetail extends Scenario {
  timeout?: number
  retry_count?: number
  continue_on_failure?: boolean
  endpoint_details?: any[]
}

// ==================== 模块类型 ====================

export type AnalysisStatus = 'pending' | 'analyzing' | 'completed' | 'failed'

export interface Module {
  id: number
  name: string
  description?: string
  analysis_status: AnalysisStatus
  endpoint_count: number
  internal_chains_count?: number  // 内部链路数量
  dependency_count?: number
  input_endpoint_count?: number
  output_endpoint_count?: number
}

export interface ModuleDetail {
  group_id: number
  group_name: string
  status: string
  dependency_count: number
  internal_chains: number[][]
  input_endpoints: number[]
  output_endpoints: number[]
}

// ==================== 模块依赖类型 ====================

export interface ModuleDependency {
  id: number
  source_group_id: number
  source_group_name: string
  target_group_id: number
  target_group_name: string
  dependency_strength: number
  endpoint_mappings: Record<string, any>
}

// ==================== 模块链路类型 ====================

export interface ModuleChain {
  id: number
  name: string
  description?: string
  group_ids: number[]
  group_names: string[]
  endpoint_count: number
  group_count: number
  created_at: string
}

// ==================== 链路类型 ====================

export type ChainType = 'internal' | 'cross-module'
export type ChainStatus = 'active' | 'archived'

export interface Chain {
  id: number | string
  name: string
  description?: string
  type: ChainType
  group_id?: number
  group_name?: string
  module_count?: number
  endpoint_count: number
  complexity_score?: number
  auto_generated?: boolean
  status: ChainStatus
  related_scenario_id?: number
  created_at?: string
  updated_at?: string
  endpoint_ids?: number[]
  execution_order?: any[]
  endpoint_details?: any[]
  chain_structure?: any[]
}

export interface ChainDetail extends Chain {
  related_scenario?: {
    id: number
    name: string
    status: string
  }
}

// ==================== 任务进度类型 ====================

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface TaskProgress {
  task_id: number
  status: TaskStatus
  progress: number
  progress_message?: string
  error_message?: string
  task_result?: {
    dependency_count?: number
    chain_count?: number
  }
}

// ==================== 环境类型 ====================

export interface Environment {
  id: number
  name: string
  base_url: string
  created_at: string
}

// ==================== 执行结果类型 ====================

export interface ExecutionResult {
  task_id?: number
  status: string
  steps?: any[]
  summary?: {
    total: number
    success: number
    failed: number
  }
}