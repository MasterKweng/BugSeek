import api from './api'
import type { ApiResponse } from './api'

export type UnifiedTaskKind = 'field-mapping' | 'scenario-execution' | 'sync-task'

export interface UnifiedTaskStage {
  key: string
  name: string
  status: string
  progress: number
  description?: string | null
}

export interface UnifiedTaskStatus<TDetail = Record<string, any>> {
  task_id: number
  task_kind: UnifiedTaskKind | string
  task_type?: string | null
  title?: string | null
  status: string
  progress: number
  progress_message?: string | null
  current_stage?: string | null
  stages: UnifiedTaskStage[]
  statistics?: Record<string, any>
  summary?: Record<string, any> | null
  error_message?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_at?: string | null
  updated_at?: string | null
  metadata?: Record<string, any>
  detail: TDetail
}

export const getTaskStatus = async <TDetail = Record<string, any>>(
  taskKind: UnifiedTaskKind,
  taskId: number
): Promise<ApiResponse<UnifiedTaskStatus<TDetail>>> => {
  return api.get(`/task-status/${taskKind}/${taskId}`)
}

export const isTerminalTaskStatus = (status?: string | null): boolean => {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
}
