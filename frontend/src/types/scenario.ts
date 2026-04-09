/**
 * Scenario domain types.
 */

export type ScenarioStatus = 'draft' | 'active' | 'archived'
export type ScenarioLifecycleStatus = 'draft' | 'validated' | 'published' | 'archived'
export type ScenarioSourceType = 'manual' | 'intent' | 'module_chain'
export type ScenarioExecutionMode = 'sequential' | 'dag'
export type ScenarioRuntimeType = 'local' | 'temporal'
export type ScenarioSuggestionStatus = 'pending' | 'accepted' | 'rejected' | 'applied'
export type ScenarioSuggestionType = 'draft' | 'mapping' | 'assertion' | 'failure_rca'

export interface ScenarioNode {
  id?: number
  node_key: string
  node_name?: string
  node_type: string
  ref_type?: 'api_case' | 'api_definition' | 'internal' | string
  ref_id?: number | null
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
  lifecycle_status?: ScenarioLifecycleStatus | string
  labels?: Record<string, unknown> | null
  draft_revision_id?: number | null
  published_revision_id?: number | null
  latest_revision_no?: number | null
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
    scenario_id?: number | null
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
    lifecycle_status?: ScenarioLifecycleStatus | string
  }
  nodes: ScenarioNode[]
  reasoning?: string
  candidate_apis?: Array<Record<string, unknown>>
  confidence?: number | null
  suggestion_id?: number | null
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

export interface ScenarioRevisionListItem {
  id: number
  scenario_id: number
  revision_no: number
  status: string
  published_at?: string | null
}

export interface ScenarioEdge {
  source_node_key: string
  target_node_key: string
  edge_type?: string
  condition_expr?: Record<string, unknown> | null
  order_hint?: number | null
}

export interface ScenarioRevisionSnapshot {
  graph_schema_version?: string
  dsl_schema_version?: string
  scenario?: Record<string, unknown>
  nodes?: ScenarioNode[]
  edges?: ScenarioEdge[]
}

export interface ScenarioRevision {
  id: number
  scenario_id: number
  revision_no: number
  status: string
  graph_schema_version?: string
  snapshot: ScenarioRevisionSnapshot
}

export interface ScenarioRevisionGraph {
  nodes: Array<{
    node_key: string
    node_type: string
    node_name?: string
    depends_on?: string[]
  }>
  edges: ScenarioEdge[]
}

export interface ScenarioValidationError {
  type?: string
  field?: string
  message: string
}

export interface ScenarioValidationResult {
  scenario_id: number
  structural_valid: boolean
  readiness_valid: boolean
  errors: ScenarioValidationError[]
  warnings: ScenarioValidationError[]
}

export interface ScenarioReadinessResult {
  ready: boolean
  errors: ScenarioValidationError[]
  warnings: ScenarioValidationError[]
  effective_environment_id?: number | null
  effective_version_id?: number | null
}

export interface ScenarioRunSummary {
  total?: number
  passed?: number
  failed?: number
  skipped?: number
  duration_ms?: number
  [key: string]: unknown
}

export interface ScenarioRun {
  run_id: number
  scenario_id: number
  revision_id?: number | null
  status: string
  result_status?: string | null
  runtime_type?: ScenarioRuntimeType | string | null
  temporal_workflow_id?: string | null
  temporal_run_id?: string | null
  summary?: ScenarioRunSummary
}

export interface ScenarioRunContext {
  run_id: number
  revision_id?: number | null
  input_context: Record<string, unknown>
  resolved_context: Record<string, unknown>
}

export interface ScenarioNodeAttempt {
  id?: number
  execution_id?: number
  scenario_id?: number
  revision_id?: number
  node_key: string
  node_type: string
  attempt: number
  status: string
  error_message?: string | null
  input_snapshot?: Record<string, unknown>
  output_snapshot?: Record<string, unknown>
  resolved_ref_snapshot?: Record<string, unknown>
  started_at?: string | null
  finished_at?: string | null
  response_time?: number | null
  response_code?: number | null
}

export interface ScenarioNodeRun {
  node_key: string
  node_type: string
  status: string
  attempt: number
  latest_attempt: ScenarioNodeAttempt
  attempts: ScenarioNodeAttempt[]
  error_message?: string | null
}

export interface ScenarioTemplate {
  id: number
  project_id?: number | null
  name: string
  description?: string | null
  category?: string | null
  status: string
  latest_revision_id?: number | null
  latest_revision_no?: number | null
  node_count?: number
  created_at?: string | null
  updated_at?: string | null
}

export interface ScenarioAISuggestion {
  suggestion_id: number
  scenario_id?: number | null
  revision_id?: number | null
  suggestion_type: ScenarioSuggestionType | string
  status: ScenarioSuggestionStatus | string
  confidence?: number | null
  payload?: Record<string, unknown>
}

export interface ScenarioFailureRcaResult {
  failure_type?: string
  root_cause?: string
  suggested_fix?: string
  suggested_rerun_point?: string
  confidence?: number | null
  [key: string]: unknown
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

