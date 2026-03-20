import api from './api'
import type { ApiResponse, FieldMapping } from '../types'
import { getTaskStatus } from './taskStatus'

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
  use_ai_fallback?: boolean  // 是否启用 AI 兜底（默认 true）
  ai_confidence_threshold?: number  // AI 触发阈值（0.0-1.0，默认 0.7）
}

// 映射来源类型
export enum MappingSourceType {
  MANUAL = 'manual',  // 手动映射
  AI = 'ai'  // 自动映射
}

// 映射状态
export enum MappingStatus {
  PROPOSED = 'proposed',  // 待审核
  CONFIRMED = 'confirmed',  // 已确认
  REJECTED = 'rejected'  // 已拒绝
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
  ai_selected?: boolean  // 是否由 AI 选择
  ai_reason?: string  // AI 选择原因
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
  source?: MappingSourceType  // 映射来源类型
  status?: MappingStatus  // 映射状态
}

export interface FieldMappingSuggestionResponse {
  items: FieldMappingSuggestion[]
  total?: number
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
  taskId: number
): Promise<ApiResponse<{ success: boolean }>> => {
  return api.post(`/async-tasks/${taskId}/cancel`)
}

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
  }
): Promise<ApiResponse<FieldMappingSuggestionResponse>> => {
  return api.get('/field-mappings/suggestions', {
    params: { task_id: taskId, ...params }
  })
}

// 阶段结果相关类型
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

// 阶段化保存相关 API
export const getStageResult = async (
  taskId: number,
  stageNum: number
): Promise<ApiResponse<StageResult>> => {
  return api.get(`/field-mappings/tasks/${taskId}/stage/${stageNum}`)
}

export const resumeTask = async (
  taskId: number
): Promise<ApiResponse<{ task_id: number; status: string; current_stage: number }>> => {
  return api.post(`/field-mappings/tasks/${taskId}/resume`)
}

export const retryStage = async (
  taskId: number,
  stageNum: number
): Promise<ApiResponse<{ task_id: number; retry_stage: number; cleared_stages: number[] }>> => {
  return api.post(`/field-mappings/tasks/${taskId}/retry/${stageNum}`)
}

export const resetTask = async (
  taskId: number
): Promise<ApiResponse<{ task_id: number; status: string }>> => {
  return api.post(`/field-mappings/tasks/${taskId}/reset`)
}


// ==================== 阶段一：历史记录和任务管理 ====================

/**
 * 页面状态类型
 */
export type PageState = 'IDLE' | 'RUNNING' | 'COMPLETED' | 'FAILED'

/**
 * 任务摘要信息
 */
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

/**
 * 任务详情 - 增强版
 */
export interface AsyncTaskDetail extends AsyncTask {
  can_retry: boolean
  retryable_stages: number[]
}

/**
 * 阶段详情 - 增强版
 */
export interface StageDetail extends StageResult {
  key: string
  name: string
  description: string | null
}

/**
 * 任务列表响应
 */
export interface AsyncTaskListResponse {
  total: number
  items: AsyncTaskSummary[]
}

/**
 * 获取异步任务列表
 */
export const listAsyncTasks = async (params: {
  task_type?: string
  project_id?: number
  version_id?: number
  status?: string
  limit?: number
  offset?: number
}): Promise<ApiResponse<AsyncTaskListResponse>> => {
  return api.get('/async-tasks', { params })
}


// ==================== 阶段二：数据缓存工具（P2 优化）====================

/**
 * 缓存键前缀
 */
const CACHE_PREFIX = 'field_mapping_task_'

/**
 * 缓存过期时间（1小时）
 */
const CACHE_EXPIRY = 60 * 60 * 1000

/**
 * 缓存数据结构
 */
interface CacheData<T> {
  data: T
  timestamp: number
}

/**
 * 生成缓存键
 */
const getCacheKey = (key: string): string => {
  return `${CACHE_PREFIX}${key}`
}

/**
 * 保存数据到缓存
 * 
 * 遵循前端代码规范：
 * - 数据校验：确保数据有效
 * - 过期时间：自动处理过期
 * - 异常处理：捕获并记录异常
 */
export const saveToCache = <T>(key: string, data: T): void => {
  try {
    // 数据校验
    if (!key || key.trim() === '') {
      console.warn('[Cache] 无效的缓存键')
      return
    }
    
    if (data === null || data === undefined) {
      console.warn('[Cache] 无效的缓存数据')
      return
    }
    
    const cacheData: CacheData<T> = {
      data,
      timestamp: Date.now()
    }
    
    const cacheKey = getCacheKey(key)
    localStorage.setItem(cacheKey, JSON.stringify(cacheData))
    console.debug(`[Cache] 数据已缓存: ${cacheKey}`)
  } catch (error) {
    console.error('[Cache] 保存缓存失败:', error)
  }
}

/**
 * 从缓存获取数据
 * 
 * 遵循前端代码规范：
 * - 过期检查：自动过期无效数据
 * - 数据校验：确保数据格式正确
 * - 异常处理：返回 null 而非抛出异常
 */
export const getFromCache = <T>(key: string): T | null => {
  try {
    // 数据校验
    if (!key || key.trim() === '') {
      console.warn('[Cache] 无效的缓存键')
      return null
    }
    
    const cacheKey = getCacheKey(key)
    const cacheStr = localStorage.getItem(cacheKey)
    
    if (!cacheStr) {
      return null
    }
    
    const cacheData: CacheData<T> = JSON.parse(cacheStr)
    
    // 过期检查
    if (Date.now() - cacheData.timestamp > CACHE_EXPIRY) {
      console.debug(`[Cache] 缓存已过期: ${cacheKey}`)
      localStorage.removeItem(cacheKey)
      return null
    }
    
    console.debug(`[Cache] 命中缓存: ${cacheKey}`)
    return cacheData.data
  } catch (error) {
    console.error('[Cache] 读取缓存失败:', error)
    return null
  }
}

/**
 * 删除缓存
 * 
 * 遵循前端代码规范：
 * - 异常处理：捕获并记录异常
 */
export const removeFromCache = (key: string): void => {
  try {
    if (!key || key.trim() === '') {
      console.warn('[Cache] 无效的缓存键')
      return
    }
    
    const cacheKey = getCacheKey(key)
    localStorage.removeItem(cacheKey)
    console.debug(`[Cache] 缓存已删除: ${cacheKey}`)
  } catch (error) {
    console.error('[Cache] 删除缓存失败:', error)
  }
}

/**
 * 清除所有字段映射缓存
 * 
 * 遵循前端代码规范：
 * - 异常处理：捕获并记录异常
 */
export const clearFieldMappingCache = (): void => {
  try {
    const keys: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.startsWith(CACHE_PREFIX)) {
        keys.push(key)
      }
    }
    
    keys.forEach(key => localStorage.removeItem(key))
    console.log(`[Cache] 已清除 ${keys.length} 个缓存项`)
  } catch (error) {
    console.error('[Cache] 清除缓存失败:', error)
  }
}

/**
 * 带缓存的获取任务结果
 * 
 * 遵循前端代码规范：
 * - NPE 防御：检查数据有效性
 * - 异常处理：返回空数组而非抛出异常
 */
export const getFieldMappingSuggestionsCached = async (
  taskId: number
): Promise<FieldMappingSuggestion[]> => {
  const cacheKey = `suggestions_${taskId}`
  
  // 尝试从缓存获取
  const cached = getFromCache<FieldMappingSuggestion[]>(cacheKey)
  if (cached) {
    return cached
  }
  
  // 缓存未命中，从服务器获取
  try {
    const response = await getFieldMappingSuggestions(taskId)
    
    // NPE 防御
    if (!response || !response.data) {
      console.warn('[Cache] 获取任务结果失败：响应为空')
      return []
    }
    
    const suggestions = response.data.items || []
    
    // 保存到缓存
    saveToCache(cacheKey, suggestions)
    
    return suggestions
  } catch (error) {
    console.error('[Cache] 获取任务结果失败:', error)
    return []
  }
}

/**
 * 带缓存的获取任务详情
 * 
 * 遵循前端代码规范：
 * - NPE 防御：检查数据有效性
 * - 异常处理：返回 null 而非抛出异常
 */
export const getAsyncTaskCached = async (
  taskId: number
): Promise<AsyncTask | null> => {
  const cacheKey = `task_${taskId}`
  
  // 尝试从缓存获取
  const cached = getFromCache<AsyncTask>(cacheKey)
  if (cached) {
    return cached
  }
  
  // 缓存未命中，从服务器获取
  try {
    const response = await getAsyncTask(taskId)
    
    // NPE 防御
    if (!response || !response.data) {
      console.warn('[Cache] 获取任务详情失败：响应为空')
      return null
    }
    
    const task = response.data
    
    // 保存到缓存
    saveToCache(cacheKey, task)
    
    return task
  } catch (error) {
    console.error('[Cache] 获取任务详情失败:', error)
    return null
  }
}

/**
 * 更新任务缓存（任务状态变更时调用）
 */
export const updateTaskCache = (taskId: number, task: AsyncTask): void => {
  const cacheKey = `task_${taskId}`
  saveToCache(cacheKey, task)
}

/**
 * 删除任务缓存（任务取消或重试时调用）
 */
export const deleteTaskCache = (taskId: number): void => {
  const taskCacheKey = `task_${taskId}`
  const suggestionsCacheKey = `suggestions_${taskId}`
  removeFromCache(taskCacheKey)
  removeFromCache(suggestionsCacheKey)
}


// ==================== 映射统计相关类型 ====================

/**
 * 映射统计信息
 */
export interface MappingStatistics {
  total_fields: number  // 总字段数
  gravity_table?: string  // 重心表
  ai_fallback_count: number  // AI 兜底次数
  high_confidence_count: number  // 高置信度（≥0.85）
  medium_confidence_count: number  // 中等置信度（0.6-0.85）
  low_confidence_count: number  // 低置信度（<0.6）
  auto_confirmed_count?: number  // 自动确认数
  proposed_count?: number
  confirmed_count?: number
  rejected_count?: number
}

// ==================== 批量拒绝建议相关类型 ====================

/**
 * 批量拒绝建议请求
 */
export interface FieldMappingSuggestionRejectRequest {
  suggestion_ids: number[]  // 建议ID列表
}

/**
 * 批量拒绝建议
 */
export const batchRejectSuggestions = async (
  request: FieldMappingSuggestionRejectRequest,
  context?: {
    project_id?: number
    version_id?: number
  }
): Promise<ApiResponse<{ processed_count: number }>> => {
  return api.post('/field-mappings/suggestions/reject', request, { params: context })
}
