export interface ExecutionSummary {
  id: number
  target_id: number
  parent_execution_id: number | null
  source_execution_id: number | null
  operator_user_id: number | null
  title: string | null
  execution_type: string
  status: string
  result_status: string | null
  project_id: number
  version_id: number | null
  version_name: string | null
  environment_id: number | null
  environment_name: string | null
  triggered_by: string | null
  total: number
  passed: number
  failed: number
  skipped: number
  duration: number | null
  started_at: string | null
  finished_at: string | null
  summary: Record<string, unknown>
}

export interface ExecutionDetail extends ExecutionSummary {
  children_count: number
  stats: {
    total: number
    passed: number
    failed: number
    skipped: number
  }
}

export interface ExecutionResultSummary {
  result_id: number
  case_id: number | null
  definition_id: number | null
  target_name: string | null
  status: string
  response_time: number | null
  response_code: number | null
  assertion_passed_count: number
  assertion_total_count: number
  error_message: string | null
}

export interface ExecutionResultDetail {
  result_id: number
  execution_id: number
  case_id: number | null
  definition_id: number | null
  target_name: string | null
  status: string
  response_time: number | null
  response_code: number | null
  request: {
    headers: Record<string, unknown>
    display_type: string | null
    raw: string | null
    json: unknown
  }
  response: {
    headers: Record<string, unknown>
    display_type: string | null
    raw: string | null
    json: unknown
  }
  assertions: {
    passed: number
    total: number
    items: Array<Record<string, unknown>>
  }
  extracted_variables: Record<string, unknown>
  error_message: string | null
}

export interface ExecutionListResponse {
  total: number
  page: number
  page_size: number
  items: ExecutionSummary[]
}

export interface ExecutionResultListResponse {
  total: number
  page: number
  page_size: number
  items: ExecutionResultSummary[]
}

export interface ExecutionRerunRequest {
  environment_id?: number
  version_id?: number
  variables?: Record<string, unknown>
  max_concurrent?: number
}

export interface ExecutionReportSummary {
  total_executions: number
  total_results: number
  passed_results: number
  failed_results: number
  error_results: number
  skipped_results: number
  pass_rate: number
  fail_rate: number
  avg_response_time: number
}

export interface ExecutionTrendItem {
  bucket: string
  total_results: number
  passed_results: number
  failed_results: number
  pass_rate: number
  avg_response_time: number
}

export interface ExecutionTrendResponse {
  group_by: 'day' | 'week' | 'month'
  items: ExecutionTrendItem[]
}

export interface ExecutionFailureItem {
  definition_id?: number | null
  case_id?: number | null
  target_name?: string | null
  failed_count?: number
  response_code?: number | null
  count?: number
  error_message?: string | null
}

export interface ExecutionFailureResponse {
  by_definition: ExecutionFailureItem[]
  by_case: ExecutionFailureItem[]
  by_status_code: ExecutionFailureItem[]
  by_error_message: ExecutionFailureItem[]
}

export interface ExecutionPerformanceItem {
  case_id?: number | null
  definition_id?: number | null
  target_name: string | null
  avg_response_time: number
  max_response_time: number
}

export interface ExecutionPerformanceResponse {
  slowest_cases: ExecutionPerformanceItem[]
  slowest_definitions: ExecutionPerformanceItem[]
}

export interface ExecutionComparisonItem {
  environment_id?: number | null
  environment_name?: string | null
  version_id?: number | null
  version_number?: string | null
  total_results: number
  pass_rate: number
  avg_response_time: number
}

export interface ExecutionComparisonResponse {
  items: ExecutionComparisonItem[]
}
