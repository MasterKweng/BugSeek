import * as request from './request'
import type {
  ScenarioDetail,
  ScenarioReadinessResult,
  ScenarioRevision,
  ScenarioRevisionGraph,
  ScenarioRevisionListItem,
  ScenarioSummary,
  ScenarioValidationResult,
} from '../types/scenario'

export interface ListScenariosParams {
  project_id?: number
  skip?: number
  limit?: number
  status?: string
  source_type?: string
}

export interface UpdateScenarioPayload {
  name?: string
  description?: string | null
  version_id?: number | null
  environment_id?: number | null
  context_init?: Record<string, unknown> | null
  execution_mode?: string
  timeout_seconds?: number | null
  retry_count?: number
  continue_on_failure?: boolean
  status?: string
  nodes?: ScenarioDetail['nodes']
}

export interface PublishScenarioPayload {
  publish_note?: string
}

export interface ScenarioRunRequestPayload {
  environment_id?: number | null
  variables?: Record<string, unknown>
}

export interface LintDslResult {
  revision_id: number
  strict: boolean
  valid: boolean
  errors: Array<Record<string, unknown>>
  warnings: Array<Record<string, unknown>>
}

export interface ScenarioExecutionListItem {
  id: number
  status: string
  environment_id?: number | null
  started_at?: string | null
  finished_at?: string | null
  summary?: Record<string, unknown>
}

export interface ScenarioExecutionDetailLegacy {
  id: number
  scenario_id: number
  environment_id?: number | null
  status: string
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  summary?: Record<string, unknown>
  error_message?: string | null
  node_results?: Array<Record<string, unknown>>
}

export const listScenarios = async (params: ListScenariosParams): Promise<{ total: number; items: ScenarioSummary[] }> =>
  request.get('/scenarios', params)

export const getScenario = async (scenarioId: number): Promise<ScenarioDetail> =>
  request.get(`/scenarios/${scenarioId}`)

export const updateScenario = async (scenarioId: number, payload: UpdateScenarioPayload): Promise<void> => {
  await request.put(`/scenarios/${scenarioId}`, payload)
}

export const validateScenario = async (
  scenarioId: number,
  payload?: ScenarioRunRequestPayload,
): Promise<ScenarioValidationResult> => request.post(`/scenarios/${scenarioId}/validate`, payload)

export const checkScenarioReadiness = async (
  scenarioId: number,
  payload?: ScenarioRunRequestPayload,
): Promise<ScenarioReadinessResult> => request.post(`/scenarios/${scenarioId}/readiness-check`, payload)

export const publishScenario = async (
  scenarioId: number,
  payload?: PublishScenarioPayload,
): Promise<{
  scenario_id: number
  revision_id: number
  revision_no: number
  lifecycle_status: string
  publish_note?: string
}> => request.post(`/scenarios/${scenarioId}/publish`, payload)

export const getScenarioRevisions = async (
  scenarioId: number,
): Promise<{ items: ScenarioRevisionListItem[] }> => request.get(`/scenarios/${scenarioId}/revisions`)

export const getScenarioRevision = async (revisionId: number): Promise<ScenarioRevision> =>
  request.get(`/scenario-revisions/${revisionId}`)

export const getScenarioRevisionGraph = async (revisionId: number): Promise<ScenarioRevisionGraph> =>
  request.get(`/scenario-revisions/${revisionId}/graph`)

export const lintScenarioRevisionDsl = async (
  revisionId: number,
  strict: boolean = true,
): Promise<LintDslResult> => request.post(`/scenario-revisions/${revisionId}/lint-dsl`, { strict })

export const listScenarioExecutionsLegacy = async (
  scenarioId: number,
  params: { skip?: number; limit?: number; status?: string } = {},
): Promise<{ total: number; items: ScenarioExecutionListItem[] }> =>
  request.get(`/scenarios/${scenarioId}/executions`, params)

export const getScenarioExecutionDetailLegacy = async (
  scenarioId: number,
  executionId: number,
): Promise<ScenarioExecutionDetailLegacy> =>
  request.get(`/scenarios/${scenarioId}/executions/${executionId}`)
