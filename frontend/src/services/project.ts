import api from './api'
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  TechStackUpdate,
  ProjectListResponse,
  ApiResponse
} from '../types'

/**
 * 创建项目
 */
export const createProject = async (data: ProjectCreate): Promise<ApiResponse<{ project: Project }>> => {
  return api.post('/projects', data)
}

/**
 * 获取项目列表
 */
export const getProjects = async (params?: {
  page?: number
  page_size?: number
  business_domain?: string
  is_deleted?: boolean
}): Promise<ApiResponse<ProjectListResponse>> => {
  return api.get('/projects', { params })
}

/**
 * 获取项目详情
 */
export const getProject = async (projectId: number): Promise<ApiResponse<Project>> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  return api.get(`/projects/${projectId}`)
}

/**
 * 更新项目
 */
export const updateProject = async (
  projectId: number,
  data: ProjectUpdate
): Promise<ApiResponse<{ project: Project }>> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  return api.put(`/projects/${projectId}`, data)
}

/**
 * 删除项目（软删除）
 */
export const deleteProject = async (projectId: number): Promise<ApiResponse> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  return api.delete(`/projects/${projectId}`)
}

/**
 * 更新技术栈画像
 */
export const updateTechStack = async (
  projectId: number,
  data: TechStackUpdate
): Promise<ApiResponse<{ project: Project }>> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  return api.post(`/projects/${projectId}/tech-stack`, data)
}

/**
 * 上传知识库文件（预留）
 */
export const uploadKnowledge = async (projectId: number): Promise<ApiResponse> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  return api.post(`/projects/${projectId}/knowledge`)
}