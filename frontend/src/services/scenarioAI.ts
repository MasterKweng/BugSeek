import * as request from './request'
import type { ScenarioAISuggestion, ScenarioDraft, ScenarioFailureRcaResult } from '../types/scenario'

export interface GenerateScenarioDraftPayload {
  intent_text: string
  project_id?: number
  version_id?: number | null
}

export interface GeneratedScenarioDraftResult {
  suggestion_id: number
  confidence?: number | null
  draft: ScenarioDraft
}

export interface MappingSuggestionPayload {
  source_output?: Record<string, unknown>
  target_input?: Record<string, unknown>
}

export interface AssertionSuggestionPayload {
  response?: Record<string, unknown>
  response_sample?: Record<string, unknown> | null
  status_code?: number | null
  max_response_time_ms?: number | null
}

export interface ApplySuggestionPayload {
  node_key?: string
}

export const generateScenarioDraftFromIntent = async (
  payload: GenerateScenarioDraftPayload,
): Promise<GeneratedScenarioDraftResult> =>
  request.post('/scenario-drafts:generate-from-intent', payload)

export const suggestScenarioMapping = async (
  revisionId: number,
  payload: MappingSuggestionPayload,
): Promise<ScenarioAISuggestion & Record<string, unknown>> =>
  request.post(`/scenario-revisions/${revisionId}:suggest-mapping`, payload)

export const suggestScenarioAssertions = async (
  revisionId: number,
  payload: AssertionSuggestionPayload,
): Promise<ScenarioAISuggestion & Record<string, unknown>> =>
  request.post(`/scenario-revisions/${revisionId}:suggest-assertions`, payload)

export const analyzeScenarioFailureSuggestion = async (runId: number): Promise<ScenarioFailureRcaResult> =>
  request.post(`/scenario-runs/${runId}:analyze-failure`)

export const acceptScenarioSuggestion = async (
  suggestionId: number,
): Promise<{ suggestion_id: number; status: string }> =>
  request.post(`/scenario-ai-suggestions/${suggestionId}:accept`)

export const rejectScenarioSuggestion = async (
  suggestionId: number,
): Promise<{ suggestion_id: number; status: string }> =>
  request.post(`/scenario-ai-suggestions/${suggestionId}:reject`)

export const applyScenarioSuggestionToDraft = async (
  suggestionId: number,
  payload: ApplySuggestionPayload = {},
): Promise<{ suggestion_id: number } & Record<string, unknown>> =>
  request.post(`/scenario-ai-suggestions/${suggestionId}:apply-to-draft`, payload)
