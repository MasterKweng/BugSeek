import api from './api'
import type { ApiResponse, FieldMappingListResponse } from '../types'

export interface FieldMappingCreateRequest {
  definition_id: number
  api_field_path: string
  db_table: string
  db_column: string
  relation_type?: string
  confidence?: number
  source?: string
}

export interface FieldMappingUpdateRequest {
  api_field_path?: string
  db_table?: string
  db_column?: string
  relation_type?: string
  confidence?: number
  source?: string
}

// 字段映射建议相关类型
export interface FieldMappingSuggestRequest {
  include_paths?: boolean
  include_query?: boolean
  include_body?: boolean
}

export interface FieldMappingCandidate {
  db_table: string
  db_column: string
  score: number
  reasons: string[]
}

export interface FieldMappingSuggestion {
  definition_id: number
  definition_method: string
  definition_path: string
  api_field_path: string
  candidates: FieldMappingCandidate[]
}

export interface FieldMappingSuggestionResponse {
  items: FieldMappingSuggestion[]
}

export interface FieldMappingBatchApplyItem {
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

export interface FieldMappingWithDetails extends FieldMapping {
  definition_method?: string
  definition_path?: string
}

export interface FieldMappingWithDetailsResponse {
  total: number
  items: FieldMappingWithDetails[]
}

export const getFieldMappings = async (params?: {
  project_id?: number
  version_id?: number
  definition_id?: number
}): Promise<ApiResponse<FieldMappingWithDetailsResponse>> => {
  return api.get('/field-mappings', { params })
}

export const createFieldMapping = async (
  data: FieldMappingCreateRequest,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse<{ id: number }>> => {
  return api.post('/field-mappings', data, { params })
}

export const updateFieldMapping = async (
  id: number,
  data: FieldMappingUpdateRequest,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse<{ id: number }>> => {
  if (typeof id !== 'number' || isNaN(id)) {
    throw new Error('无效的映射 ID')
  }
  return api.put(`/field-mappings/${id}`, data, { params })
}

export const deleteFieldMapping = async (
  id: number,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse> => {
  if (typeof id !== 'number' || isNaN(id)) {
    throw new Error('无效的映射 ID')
  }
  return api.delete(`/field-mappings/${id}`, { params })
}

export interface FieldMappingCloneRequest {
  from_version_id: number
  to_version_id: number
}

export const cloneFieldMappings = async (
  request: FieldMappingCloneRequest,
  params?: { project_id?: number }
): Promise<ApiResponse<{ cloned_count: number }>> => {
  return api.post('/field-mappings/clone', request, { params })
}

export interface FieldMappingAutoApplyRequest {
  min_confidence?: number
}

export const autoApplyFieldMappings = async (
  request: FieldMappingAutoApplyRequest,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse<{ updated_count: number }>> => {
  return api.post('/field-mappings/auto-apply', request, { params })
}

export const getFieldDictionary = async (params?: {
  project_id?: number
  version_id?: number
}): Promise<ApiResponse<{ items: ProjectFieldDictionary[]; total: number }>> => {
  return api.get('/field-mappings/dictionary', { params })
}

export interface ProjectFieldDictionary {
  field_name: string
  db_table: string
  db_column: string
  priority: number
}

export const getLearningStats = async (params?: {
  project_id?: number
  version_id?: number
}): Promise<ApiResponse<{
  total_mappings: number
  confirmed_mappings: number
  proposed_mappings: number
  rejected_mappings: number
  avg_confidence: number
  ai_mappings: number
  manual_mappings: number
}>> => {
  return api.get('/field-mappings/learning-stats', { params })
}

// 字段映射建议相关 API
export const suggestFieldMappings = async (
  data: FieldMappingSuggestRequest,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse<FieldMappingSuggestionResponse>> => {
  return api.post('/field-mappings/suggest', data, { params })
}

export const batchApplyFieldMappings = async (
  data: FieldMappingBatchApplyRequest,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse<{ processed_count: number }>> => {
  return api.post('/field-mappings/batch-apply', data, { params })
}

export const updateFieldMappingStatus = async (
  id: number,
  status: string,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse<{ id: number; status: string }>> => {
  if (typeof id !== 'number' || isNaN(id)) {
    throw new Error('无效的映射 ID')
  }
  return api.put(`/field-mappings/${id}/status`, null, { 
    params: { ...params, status } 
  })
}

export interface PendingFieldMapping extends FieldMappingWithDetails {
  id: number
  project_id: number
  version_id: number
  definition_id: number
  definition_method: string
  definition_path: string
  api_field_path: string
  db_table: string
  db_column: string
  relation_type: string
  confidence?: number
  source: string
  status: string
  created_at: string
  updated_at: string
}

export interface PendingFieldMappingResponse {
  items: PendingFieldMapping[]
  total: number
}

export const getPendingFieldMappings = async (params?: {
  project_id?: number
  version_id?: number
}): Promise<ApiResponse<PendingFieldMappingResponse>> => {
  return api.get('/field-mappings/pending', { params })
}

// 异步任务相关类型
export interface AsyncTask {
  id: number
  project_id: number
  user_id?: number
  task_type: string
  task_params?: Record<string, any>
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  progress_message?: string
  current_stage?: string
  stages?: Array<{
    name: string
    status: string
    progress: number
  }>
  statistics?: Record<string, any>
  result?: any
  error_message?: string
  started_at?: string
  finished_at?: string
  created_at: string
  updated_at: string
}

export interface AsyncTaskCreateRequest {
  include_paths?: boolean
  include_query?: boolean
  include_body?: boolean
  use_ai?: boolean
  ai_config?: {
    high_priority_enabled?: boolean
    medium_priority_enabled?: boolean
    low_priority_enabled?: boolean
  }
}

export interface AsyncTaskCreateResponse {
  task_id: number
  status: string
  estimated_duration?: number
  estimated_fields?: number
}

// 异步任务相关 API
export const createFieldMappingSuggestTask = async (
  data: AsyncTaskCreateRequest,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse<AsyncTaskCreateResponse>> => {
  return api.post('/field-mappings/suggest-task', data, { params })
}

export const getAsyncTask = async (
  taskId: number
): Promise<ApiResponse<AsyncTask>> => {
  return api.get(`/async-tasks/${taskId}`)
}

export const cancelAsyncTask = async (
  taskId: number
): Promise<ApiResponse<{ success: boolean }>> => {
  return api.post(`/async-tasks/${taskId}/cancel`)
}

export const getFieldMappingSuggestions = async (
  taskId: number,
  params?: { page?: number; page_size?: number }
): Promise<ApiResponse<FieldMappingSuggestionResponse>> => {
  return api.get('/field-mappings/suggestions', { 
    params: { task_id: taskId, ...params } 
  })
}
