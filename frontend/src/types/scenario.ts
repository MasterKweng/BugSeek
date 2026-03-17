/**
 * Scenario domain types.
 */

export type ScenarioStatus = 'draft' | 'active' | 'archived'
export type ScenarioSourceType = 'manual' | 'intent' | 'module_chain'
export type ScenarioExecutionMode = 'sequential' | 'dag'

export interface ScenarioNode {
  id?: number
  node_key: string
  node_name?: string
  node_type: string
  ref_type: 'api_case' | 'api_definition' | string
  ref_id: number
  step_order: number
  depends_on: string[]
  input_mapping?: Record<string, unknown>
  extract_rules?: Record<string, unknown> | null
  assertion_overrides?: Record<string, unknown> | null
  timeout_seconds?: number | null
  retry_count: number
  continue_on_failure: boolean
  is_enabled: boolean
  extra_config?: Record<string, unknown> | null
}

export interface ScenarioSummary {
  id: number
  project_id: number
  version_id?: number | null
  environment_id?: number | null
  name: string
  description?: string | null
  scenario_type: string
  source_type: ScenarioSourceType | string
  source_ref_id?: number | null
  context_init?: Record<string, unknown> | null
  execution_mode: ScenarioExecutionMode | string
  timeout_seconds: number
  retry_count: number
  continue_on_failure: boolean
  status: ScenarioStatus | string
  created_at: string
  updated_at: string
  created_by?: number | null
  updated_by?: number | null
  node_count: number
}

export interface ScenarioDetail extends ScenarioSummary {
  nodes: ScenarioNode[]
}

export type Scenario = ScenarioSummary

export interface ScenarioDraft {
  scenario: {
    name?: string
    description?: string
    scenario_type?: string
    source_type?: string
    source_ref_id?: number | null
    project_id?: number | null
    version_id?: number | null
    environment_id?: number | null
    context_init?: Record<string, unknown>
    execution_mode?: string
    timeout_seconds?: number
    retry_count?: number
    continue_on_failure?: boolean
  }
  nodes: ScenarioNode[]
  reasoning?: string
  candidate_apis?: Array<Record<string, unknown>>
}

export interface ScenarioExecutionSummary {
  total: number
  passed: number
  failed: number
  skipped: number
  duration_ms: number
}

export interface ScenarioExecutionNodeResult {
  id?: number
  target_type?: string
  target_id?: number
  status: string
  response_time?: number | null
  response_code?: number | null
  request_body?: unknown
  response_body?: unknown
  assertion_results?: unknown
  extracted_variables?: Record<string, unknown>
  error_message?: string | null
}

export interface ScenarioExecutionDetail {
  id: number
  scenario_id: number
  environment_id?: number | null
  status: string
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  summary: ScenarioExecutionSummary
  error_message?: string | null
  node_results: ScenarioExecutionNodeResult[]
}

export type AnalysisStatus = 'pending' | 'analyzing' | 'completed' | 'failed'

export interface Module {
  id: number
  name: string
  description?: string
  analysis_status: AnalysisStatus
  endpoint_count: number
  internal_chains_count?: number
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

export interface ModuleDependency {
  id: number
  source_group_id: number
  source_group_name: string
  target_group_id: number
  target_group_name: string
  dependency_strength: number
  endpoint_mappings: Record<string, unknown>
}

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
  execution_order?: unknown[]
  endpoint_details?: unknown[]
  chain_structure?: unknown[]
}

export interface ChainDetail extends Chain {
  related_scenario?: {
    id: number
    name: string
    status: string
  }
}

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

export interface Environment {
  id: number
  name: string
  base_url: string
  headers?: Record<string, string>
  variables?: Record<string, string>
  is_default?: boolean
  created_at: string
}

export interface ExecutionResult {
  execution_id?: number
  status: string
  summary?: ScenarioExecutionSummary
  results?: ScenarioExecutionNodeResult[]
}

