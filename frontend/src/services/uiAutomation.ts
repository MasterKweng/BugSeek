import api from './api'
import type { ApiResponse } from './api'

export interface UIStepSpec {
  name: string
  action: 'goto' | 'click' | 'fill' | 'press' | 'wait_for' | 'assert_text' | 'assert_url'
  selector?: string | null
  value?: string | null
  timeout_ms?: number
}

export interface UIExecutionSummary {
  execution_id: number
  status: string
  total_steps: number
  passed_steps: number
  failed_steps: number
  duration_ms: number
  steps: Array<{
    index: number
    name: string
    action: string
    selector?: string | null
    status: string
    duration_ms: number
    message?: string | null
    url?: string | null
    error_message?: string | null
  }>
}

export interface UIExecutionRequest {
  name: string
  start_url?: string | null
  steps: UIStepSpec[]
  target_id?: number
  headless?: boolean
}

export const createUIExecution = async (
  projectId: number,
  payload: UIExecutionRequest,
): Promise<ApiResponse<UIExecutionSummary>> => {
  return api.post(`/ui-testing/executions?project_id=${projectId}`, payload)
}

export const getUIExecution = async (
  projectId: number,
  executionId: number,
): Promise<ApiResponse<UIExecutionSummary>> => {
  return api.get(`/ui-testing/executions/${executionId}?project_id=${projectId}`)
}
