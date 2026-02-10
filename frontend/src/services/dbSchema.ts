import api from './api'
import type { ApiResponse, DbSchemaListResponse, DbSchemaDetail } from '../types'

export interface DbSchemaImportRequest {
  name: string
  source_type?: string
  source_version?: string
  schema_snapshot: Record<string, any>
}

/**
 * 获取数据库结构列表
 */
export const getDbSchemas = async (
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse<DbSchemaListResponse>> => {
  return api.get('/db-schemas', { params })
}

/**
 * 获取数据库结构详情
 */
export const getDbSchemaDetail = async (
  id: number,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse<DbSchemaDetail>> => {
  if (typeof id !== 'number' || isNaN(id)) {
    throw new Error('无效的结构 ID')
  }
  return api.get(`/db-schemas/${id}`, { params })
}

/**
 * 导入数据库结构
 */
export const importDbSchema = async (
  data: DbSchemaImportRequest,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse<{ id: number }>> => {
  return api.post('/db-schemas/import', data, { params })
}

/**
 * 删除数据库结构
 */
export const deleteDbSchema = async (
  id: number,
  params?: { project_id?: number; version_id?: number }
): Promise<ApiResponse> => {
  if (typeof id !== 'number' || isNaN(id)) {
    throw new Error('无效的结构 ID')
  }
  return api.delete(`/db-schemas/${id}`, { params })
}
