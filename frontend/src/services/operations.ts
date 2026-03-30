import api from './api'
import * as request from './request'
import { useAuthStore } from '../store/auth'

export interface ScenarioSummary {
  id: number
  project_id: number
  version_id: number | null
  environment_id: number | null
  name: string
  description: string | null
  scenario_type: string
  source_type: string
  source_ref_id: number | null
  context_init: Record<string, any> | null
  execution_mode: string
  timeout_seconds: number
  retry_count: number
  continue_on_failure: boolean
  status: string
  created_at: string
  updated_at: string
  created_by: number | null
  updated_by: number | null
  node_count: number
}

export interface ScenarioListResponse {
  total: number
  items: ScenarioSummary[]
}

export interface ScenarioExecutionSummary {
  id: number
  scenario_id: number
  environment_id: number | null
  status: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  summary: {
    total: number
    passed: number
    failed: number
    skipped: number
    duration_ms: number
  }
}

export interface TriggerScenarioRequest {
  environment_id: number
  async_mode?: boolean
  callback_url?: string | null
}

export interface ReportSummary {
  total_nodes?: number
  passed_nodes?: number
  failed_nodes?: number
  skipped_nodes?: number
  failed_node_keys?: string[]
  duration_ms?: number
  passed_rate?: number
}

const buildScenarioHeaders = () => {
  const authState = useAuthStore.getState()
  const token = authState.token || localStorage.getItem('token')
  const userId = authState.user?.id

  if (!token || !userId) {
    return undefined
  }

  return {
    'X-API-Key': `${userId}:${token}`,
  }
}

export const getProjectScenarios = (projectId: number, limit = 200): Promise<ScenarioListResponse> => {
  return request.get('/scenarios', {
    skip: 0,
    limit,
    project_id: projectId,
  })
}

export const getScenarioExecutions = (
  scenarioId: number,
  status?: string,
  limit = 50,
): Promise<{ total: number; items: ScenarioExecutionSummary[] }> => {
  return request.get(`/scenarios/${scenarioId}/executions`, {
    skip: 0,
    limit,
    status,
  })
}

export const triggerScenario = (
  scenarioId: number,
  payload: TriggerScenarioRequest,
) => {
  return api.post(`/scenarios/${scenarioId}/trigger`, payload, {
    headers: buildScenarioHeaders(),
  })
}

export const getTriggerResult = (scenarioId: number, executionId: number) => {
  return api.get(`/scenarios/${scenarioId}/trigger/${executionId}`, {
    headers: buildScenarioHeaders(),
  })
}

export const getExecutionReportSummary = (scenarioId: number, executionId: number): Promise<ReportSummary> => {
  return request.get(`/scenarios/${scenarioId}/executions/${executionId}/report/summary`)
}

export const getExecutionRca = (scenarioId: number, executionId: number) => {
  return request.get(`/scenarios/${scenarioId}/executions/${executionId}/rca`)
}

export const generateAiScenarioDraft = (projectId: number, intentText: string, saveDraft = false) => {
  return request.post('/ai/scenario/generate', {
    project_id: projectId,
    intent_text: intentText,
    save_draft: saveDraft,
  })
}

export const generateAiTest = (projectId: number, inputData: Record<string, any>) => {
  return request.post('/ai/test/generate', {
    project_id: projectId,
    input_data: inputData,
  })
}

export const analyzeAiFailure = (projectId: number, inputData: Record<string, any>) => {
  return request.post('/ai/test/analyze', {
    project_id: projectId,
    input_data: inputData,
  })
}

export const generateAiAssertions = (projectId: number, inputData: Record<string, any>) => {
  return request.post('/ai/test/assertions', {
    project_id: projectId,
    input_data: inputData,
  })
}

export const mapAiVariables = (projectId: number, inputData: Record<string, any>) => {
  return request.post('/ai/test/variables/map', {
    project_id: projectId,
    input_data: inputData,
  })
}
