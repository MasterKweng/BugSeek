import * as request from './request'
import type {
  ExecutionComparisonResponse,
  ExecutionDetail,
  ExecutionFailureResponse,
  ExecutionListResponse,
  ExecutionPerformanceResponse,
  ExecutionReportSummary,
  ExecutionResultDetail,
  ExecutionResultListResponse,
  ExecutionRerunRequest,
  ExecutionTrendResponse,
} from '../types/execution'

export interface ExecutionQueryParams {
  page?: number
  page_size?: number
  execution_type?: string
  status?: string
  result_status?: string
  environment_id?: number
  version_id?: number
  case_id?: number
  definition_id?: number
  keyword?: string
}

export interface ExecutionReportQueryParams {
  version_id?: number
  environment_id?: number
  started_after?: string
  started_before?: string
}

export const getExecutions = (params: ExecutionQueryParams): Promise<ExecutionListResponse> => {
  return request.get('/executions', params)
}

export const getExecutionDetail = (executionId: number): Promise<ExecutionDetail> => {
  return request.get(`/executions/${executionId}`)
}

export const getExecutionChildren = (
  executionId: number,
  page: number = 1,
  pageSize: number = 100,
): Promise<{ total: number; items: ExecutionDetail[] }> => {
  return request.get(`/executions/${executionId}/children`, {
    page,
    page_size: pageSize,
  })
}

export const getExecutionResults = (
  executionId: number,
  page: number = 1,
  pageSize: number = 100,
  status?: string,
  keyword?: string,
): Promise<ExecutionResultListResponse> => {
  return request.get(`/executions/${executionId}/results`, {
    page,
    page_size: pageSize,
    status,
    keyword,
  })
}

export const getExecutionResultDetail = (resultId: number): Promise<ExecutionResultDetail> => {
  return request.get(`/execution-results/${resultId}`)
}

export const rerunExecution = (
  executionId: number,
  payload: ExecutionRerunRequest,
): Promise<Record<string, unknown>> => {
  return request.post(`/executions/${executionId}/rerun`, payload)
}

export const getExecutionReportSummary = (
  params: ExecutionReportQueryParams,
): Promise<ExecutionReportSummary> => {
  return request.get('/reports/executions/summary', params)
}

export const getExecutionReportTrends = (
  params: ExecutionReportQueryParams & { group_by?: 'day' | 'week' | 'month' },
): Promise<ExecutionTrendResponse> => {
  return request.get('/reports/executions/trends', params)
}

export const getExecutionReportFailures = (
  params: ExecutionReportQueryParams,
): Promise<ExecutionFailureResponse> => {
  return request.get('/reports/executions/failures', params)
}

export const getExecutionReportPerformance = (
  params: ExecutionReportQueryParams,
): Promise<ExecutionPerformanceResponse> => {
  return request.get('/reports/executions/performance', params)
}

export const getExecutionEnvironmentComparison = (
  params: Omit<ExecutionReportQueryParams, 'environment_id'>,
): Promise<ExecutionComparisonResponse> => {
  return request.get('/reports/executions/environment-comparison', params)
}

export const getExecutionVersionComparison = (
  params: Omit<ExecutionReportQueryParams, 'version_id'>,
): Promise<ExecutionComparisonResponse> => {
  return request.get('/reports/executions/version-comparison', params)
}
