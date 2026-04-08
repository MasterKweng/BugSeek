import api from './api'
import type { ApiResponse, FieldMapping } from '../types'

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

export interface FieldMappingWithDetails extends FieldMapping {
  definition_method?: string
  definition_path?: string
}

export interface FieldMappingWithDetailsResponse {
  total: number
  items: FieldMappingWithDetails[]
}

export interface FieldMappingCloneRequest {
  from_version_id: number
  to_version_id: number
}

export interface FieldMappingAutoApplyRequest {
  min_confidence?: number
}

export interface ProjectFieldDictionary {
  field_name: string
  db_table: string
  db_column: string
  priority: number
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

export interface MappingStatistics {
  total_fields: number
  gravity_table?: string
  ai_fallback_count: number
  high_confidence_count: number
  medium_confidence_count: number
  low_confidence_count: number
  auto_confirmed_count?: number
  proposed_count?: number
  confirmed_count?: number
  rejected_count?: number
}

export const getFieldMappings = async (params?: {
  project_id?: number
  version_id?: number
  definition_id?: number
}): Promise<ApiResponse<FieldMappingWithDetailsResponse>> => api.get('/field-mappings', { params })

export const createFieldMapping = async (
  data: FieldMappingCreateRequest,
  params?: { project_id?: number; version_id?: number },
): Promise<ApiResponse<{ id: number }>> => api.post('/field-mappings', data, { params })

export const updateFieldMapping = async (
  id: number,
  data: FieldMappingUpdateRequest,
  params?: { project_id?: number; version_id?: number },
): Promise<ApiResponse<{ id: number }>> => {
  if (typeof id !== 'number' || Number.isNaN(id)) {
    throw new Error('Invalid field mapping ID')
  }
  return api.put(`/field-mappings/${id}`, data, { params })
}

export const deleteFieldMapping = async (
  id: number,
  params?: { project_id?: number; version_id?: number },
): Promise<ApiResponse> => {
  if (typeof id !== 'number' || Number.isNaN(id)) {
    throw new Error('Invalid field mapping ID')
  }
  return api.delete(`/field-mappings/${id}`, { params })
}

export const cloneFieldMappings = async (
  request: FieldMappingCloneRequest,
  params?: { project_id?: number },
): Promise<ApiResponse<{ cloned_count: number }>> => api.post('/field-mappings/clone', request, { params })

export const autoApplyFieldMappings = async (
  request: FieldMappingAutoApplyRequest,
  params?: { project_id?: number; version_id?: number },
): Promise<ApiResponse<{ updated_count: number }>> => api.post('/field-mappings/auto-apply', request, { params })

export const getFieldDictionary = async (params?: {
  project_id?: number
  version_id?: number
}): Promise<ApiResponse<{ items: ProjectFieldDictionary[]; total: number }>> => api.get('/field-mappings/dictionary', { params })

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
}>> => api.get('/field-mappings/learning-stats', { params })

export const updateFieldMappingStatus = async (
  id: number,
  status: string,
  params?: { project_id?: number; version_id?: number },
): Promise<ApiResponse<{ id: number; status: string }>> => {
  if (typeof id !== 'number' || Number.isNaN(id)) {
    throw new Error('Invalid field mapping ID')
  }
  return api.put(`/field-mappings/${id}/status`, null, {
    params: { ...params, status },
  })
}

export const getPendingFieldMappings = async (params?: {
  project_id?: number
  version_id?: number
}): Promise<ApiResponse<PendingFieldMappingResponse>> => api.get('/field-mappings/pending', { params })
