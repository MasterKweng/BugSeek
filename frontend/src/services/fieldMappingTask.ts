import api from './api'
import { getTaskStatus } from './taskStatus'
import { getFromCache, removeFromCache, saveToCache } from './fieldMappingCache'
import type { ApiResponse } from '../types'

export interface StageResult {
  name: string
  status: 'not_started' | 'running' | 'completed' | 'failed' | 'skipped'
  progress: number
  completed_at?: string
  data?: any
}

export interface TaskProgress {
  current_stage: number
  stage_results: {
    stage1?: StageResult
    stage2?: StageResult
    stage3?: StageResult
    stage4?: StageResult
    stage5?: StageResult
  }
}

export interface AsyncTask {
  id: number
  project_id: number
  user_id?: number
  task_type: string
  task_params?: Record<string, any>
  status: 'pending' | 'running' | 'completed' | 'partial_success' | 'failed' | 'cancelled'
  progress: number
  progress_message?: string
  current_stage?: string
  stage_results?: {
    stage1?: StageResult
    stage2?: StageResult
    stage3?: StageResult
    stage4?: StageResult
    stage5?: StageResult
  }
  stages?: Array<{
    name: string
    status: string
    progress: number
    description?: string | null
  }>
  statistics?: Record<string, any>
  consistency_ok?: boolean | null
  consistency_diff?: number | null
  result_table_mismatch?: boolean | null
  result_trace_mismatch?: boolean | null
  result_artifact_mismatch?: boolean | null
  result?: any
  engine_version?: string
  artifacts_summary?: {
    total_artifacts: number
    by_stage: Record<string, number>
  }
  error_message?: string
  started_at?: string
  finished_at?: string
  created_at: string
  updated_at: string
  can_retry?: boolean
  retryable_stages?: number[]
}

export interface AsyncTaskCreateRequest {
  include_paths?: boolean
  include_query?: boolean
  include_body?: boolean
  use_ai?: boolean
  use_sql_lineage?: boolean
  use_code_lineage?: boolean
  use_runtime_verification?: boolean
  evidence_mode?: 'balanced' | 'conservative' | 'aggressive'
  rebuild_lineage_before_run?: boolean
  selected_execution_ids?: number[]
  workspace_root?: string
  high_priority_enabled?: boolean
  medium_priority_enabled?: boolean
  low_priority_enabled?: boolean
  definition_ids?: number[]
  scenario_id?: number
}

export interface AsyncTaskCreateResponse {
  task_id: number
  status: string
  estimated_duration?: number
  estimated_fields?: number
}

export type PageState = 'IDLE' | 'RUNNING' | 'COMPLETED' | 'FAILED'

export interface AsyncTaskSummary {
  id: number
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'partial_success' | 'failed' | 'cancelled'
  progress: number
  created_at: string
  finished_at: string | null
  duration: number | null
  statistics: {
    total_fields?: number
    auto_confirmed?: number
    ai_enhanced?: number
  }
  result_count: number | null
  error_message?: string
}

export interface AsyncTaskDetail extends AsyncTask {
  can_retry: boolean
  retryable_stages: number[]
}

export interface StageDetail extends StageResult {
  key: string
  name: string
  description: string | null
}

export interface AsyncTaskListResponse {
  total: number
  items: AsyncTaskSummary[]
}

export interface ReplaySuggestionsResponse {
  task_id: number
  suggestions_count: number
  consistency_ok: boolean
  consistency_diff: number
  result_table_mismatch: boolean
  result_trace_mismatch: boolean
  result_artifact_mismatch: boolean
}

export const createFieldMappingSuggestTask = async (
  data: AsyncTaskCreateRequest,
  params?: { project_id?: number; version_id?: number },
): Promise<ApiResponse<AsyncTaskCreateResponse>> => api.post('/field-mappings/suggest-task', data, { params })

export const getAsyncTask = async (
  taskId: number,
): Promise<ApiResponse<AsyncTask>> => {
  const response = await getTaskStatus<AsyncTask>('field-mapping', taskId)
  if (response.code === 0 && response.data?.detail) {
    return {
      ...response,
      data: response.data.detail,
    }
  }
  return api.get(`/async-tasks/${taskId}`)
}

export const cancelAsyncTask = async (
  taskId: number,
): Promise<ApiResponse<{ success: boolean }>> => api.post(`/async-tasks/${taskId}/cancel`)

export const getStageResult = async (
  taskId: number,
  stageNum: number,
): Promise<ApiResponse<StageResult>> => api.get(`/field-mappings/tasks/${taskId}/stage/${stageNum}`)

export const resumeTask = async (
  taskId: number,
): Promise<ApiResponse<{ task_id: number; status: string; current_stage: number }>> => api.post(`/field-mappings/tasks/${taskId}/resume`)

export const retryStage = async (
  taskId: number,
  stageNum: number,
): Promise<ApiResponse<{ task_id: number; retry_stage: number; cleared_stages: number[] }>> => api.post(`/field-mappings/tasks/${taskId}/retry/${stageNum}`)

export const resetTask = async (
  taskId: number,
): Promise<ApiResponse<{ task_id: number; status: string }>> => api.post(`/field-mappings/tasks/${taskId}/reset`)

export const listAsyncTasks = async (params: {
  task_type?: string
  project_id?: number
  version_id?: number
  status?: string
  limit?: number
  offset?: number
}): Promise<ApiResponse<AsyncTaskListResponse>> => api.get('/async-tasks', { params })

export const replayTaskSuggestions = async (
  taskId: number,
): Promise<ApiResponse<ReplaySuggestionsResponse>> => api.post(`/async-tasks/${taskId}/replay-suggestions`)

export const getAsyncTaskCached = async (taskId: number): Promise<AsyncTask | null> => {
  const cacheKey = `task_${taskId}`
  const cached = getFromCache<AsyncTask>(cacheKey)
  if (cached) {
    return cached
  }

  try {
    const response = await getAsyncTask(taskId)
    if (!response || !response.data) {
      return null
    }
    saveToCache(cacheKey, response.data)
    return response.data
  } catch (error) {
    console.error('[Cache] Failed to fetch task detail:', error)
    return null
  }
}

export const updateTaskCache = (taskId: number, task: AsyncTask): void => {
  saveToCache(`task_${taskId}`, task)
}

export const deleteTaskCache = (taskId: number): void => {
  removeFromCache(`task_${taskId}`)
  removeFromCache(`suggestions_${taskId}`)
}
