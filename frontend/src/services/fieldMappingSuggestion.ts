import api from './api'
import { getFromCache, saveToCache } from './fieldMappingCache'
import type { ApiResponse } from '../types'

export interface FieldMappingSuggestRequest {
  include_paths?: boolean
  include_query?: boolean
  include_body?: boolean
  use_ai_fallback?: boolean
  ai_confidence_threshold?: number
}

export enum MappingSourceType {
  MANUAL = 'manual',
  AI = 'ai',
}

export enum MappingStatus {
  PROPOSED = 'proposed',
  CONFIRMED = 'confirmed',
  REJECTED = 'rejected',
}

export interface FieldMappingCandidate {
  db_table: string
  db_column: string
  score: number
  reasons: string[]
  relation_type?: string
  confidence?: number | null
  negative_evidence?: string[]
  reject_reasons?: string[]
  hard_reject?: boolean
  short_circuit_reason?: string
  recall_sources?: string[]
  features?: Record<string, any>
  ai_selected?: boolean
  ai_reason?: string
}

export interface FieldMappingDecisionArtifact {
  field_name?: string
  top_candidate?: Record<string, any> | null
  candidate_list?: Record<string, any>[]
  relation_type?: string | null
  confidence?: number | null
  decision_source?: string | null
  decision_trace?: Record<string, any>
}

export interface FieldMappingSuggestion {
  id?: number
  definition_id: number
  definition_method: string
  definition_path: string
  api_field_path: string
  top_candidate?: Record<string, any> | null
  candidate_list?: Record<string, any>[]
  relation_type?: string | null
  confidence?: number | null
  decision_source?: string | null
  decision_artifact?: FieldMappingDecisionArtifact | null
  candidates: FieldMappingCandidate[]
  decision_trace?: Record<string, any>
  source?: MappingSourceType
  status?: MappingStatus
}

export interface FieldMappingSuggestionResponse {
  items: FieldMappingSuggestion[]
  total?: number
  page?: number
  size?: number
  pages?: number
  source?: string
}

export interface FieldMappingBatchApplyItem {
  suggestion_id: number
  definition_id: number
  api_field_path: string
  db_table: string
  db_column: string
  relation_type?: string
  source?: string
}

export interface FieldMappingBatchApplyRequest {
  items: FieldMappingBatchApplyItem[]
  mode: string
}

export interface FieldMappingSuggestionRejectRequest {
  suggestion_ids: number[]
}

export const suggestFieldMappings = async (
  data: FieldMappingSuggestRequest,
  params?: { project_id?: number; version_id?: number },
): Promise<ApiResponse<FieldMappingSuggestionResponse>> => api.post('/field-mappings/suggest', data, { params })

export const getFieldMappingSuggestions = async (
  taskId: number,
  params?: {
    page?: number
    size?: number
    search?: string
    status_filter?: string
    method_filter?: string
    field_type_filter?: string
    definition_path_filter?: string
  },
): Promise<ApiResponse<FieldMappingSuggestionResponse>> => api.get('/field-mappings/suggestions', {
  params: { task_id: taskId, ...params },
})

export const getFieldMappingSuggestionsCached = async (
  taskId: number,
): Promise<FieldMappingSuggestion[]> => {
  const cacheKey = `suggestions_${taskId}`
  const cached = getFromCache<FieldMappingSuggestion[]>(cacheKey)
  if (cached) {
    return cached
  }

  try {
    const response = await getFieldMappingSuggestions(taskId)
    if (!response || !response.data) {
      return []
    }
    const suggestions = response.data.items || []
    saveToCache(cacheKey, suggestions)
    return suggestions
  } catch (error) {
    console.error('[Cache] Failed to fetch suggestions:', error)
    return []
  }
}

export const batchApplyFieldMappings = async (
  data: FieldMappingBatchApplyRequest,
  params?: { project_id?: number; version_id?: number },
): Promise<ApiResponse<{ processed_count: number }>> => api.post('/field-mappings/batch-apply', data, { params })

export const batchRejectSuggestions = async (
  request: FieldMappingSuggestionRejectRequest,
  context?: { project_id?: number; version_id?: number },
): Promise<ApiResponse<{ processed_count: number }>> => api.post('/field-mappings/suggestions/reject', request, { params: context })
