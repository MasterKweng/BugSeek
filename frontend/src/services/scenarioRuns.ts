import * as request from './request'
import type {
  ScenarioFailureRcaResult,
  ScenarioNodeRun,
  ScenarioRun,
  ScenarioRunContext,
} from '../types/scenario'

export interface CreateScenarioRunPayload {
  scenario_id: number
  revision_id?: number | null
  environment_id?: number | null
  version_id?: number | null
  variables?: Record<string, unknown>
}

export interface ScenarioNodeActionPayload {
  node_key: string
  environment_id?: number | null
  version_id?: number | null
  variables?: Record<string, unknown>
}

export interface ScenarioSignalPayload {
  signal_name: string
  payload?: Record<string, unknown>
}

export interface ScenarioNodeActionResult {
  source_run_id: number
  new_run_id: number
  node_key?: string
  continue_from_node_key?: string
  revision_id: number
  status: string
}

export const createScenarioRun = async (payload: CreateScenarioRunPayload): Promise<ScenarioRun> =>
  request.post('/scenario-runs', payload)

export const getScenarioRun = async (runId: number): Promise<ScenarioRun> =>
  request.get(`/scenario-runs/${runId}`)

export const getScenarioRunContext = async (runId: number): Promise<ScenarioRunContext> =>
  request.get(`/scenario-runs/${runId}/context`)

export const getScenarioRunNodes = async (runId: number): Promise<{ run_id: number; items: ScenarioNodeRun[] }> =>
  request.get(`/scenario-runs/${runId}/nodes`)

export const rerunScenarioNode = async (
  runId: number,
  payload: ScenarioNodeActionPayload,
): Promise<ScenarioNodeActionResult> => request.post(`/scenario-runs/${runId}:rerun-node`, payload)

export const continueFromScenarioNode = async (
  runId: number,
  payload: ScenarioNodeActionPayload,
): Promise<ScenarioNodeActionResult> => request.post(`/scenario-runs/${runId}:continue-from-node`, payload)

export const pauseScenarioRun = async (
  runId: number,
): Promise<{ run_id: number; runtime_type?: string; action?: string }> =>
  request.post(`/scenario-runs/${runId}:pause`)

export const resumeScenarioRun = async (
  runId: number,
): Promise<{ run_id: number; runtime_type?: string; action?: string }> =>
  request.post(`/scenario-runs/${runId}:resume`)

export const signalScenarioRun = async (
  runId: number,
  payload: ScenarioSignalPayload,
): Promise<{ run_id: number; runtime_type?: string; action?: string; signal_name?: string }> =>
  request.post(`/scenario-runs/${runId}:signal`, payload)

export const analyzeScenarioFailure = async (runId: number): Promise<ScenarioFailureRcaResult> =>
  request.post(`/scenario-runs/${runId}:analyze-failure`)
