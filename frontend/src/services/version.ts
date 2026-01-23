import api from './api'
import type {
  Version,
  VersionCreate,
  VersionUpdate,
  VersionListResponse,
  ApiResponse
} from '../types'

/**
 * 创建版本
 */
export const createVersion = async (
  projectId: number,
  data: VersionCreate
): Promise<ApiResponse<{ version: Version }>> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  return api.post(`/projects/${projectId}/versions`, data)
}

/**
 * 获取版本列表
 */
export const getVersions = async (
  projectId: number,
  params?: {
    page?: number
    page_size?: number
    status?: string
  }
): Promise<ApiResponse<VersionListResponse>> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  return api.get(`/projects/${projectId}/versions`, { params })
}

/**
 * 获取版本详情
 */
export const getVersion = async (
  projectId: number,
  versionId: number
): Promise<ApiResponse<Version>> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  if (typeof versionId !== 'number' || isNaN(versionId)) {
    throw new Error('无效的版本 ID')
  }
  return api.get(`/projects/${projectId}/versions/${versionId}`)
}

/**
 * 更新版本
 */
export const updateVersion = async (
  projectId: number,
  versionId: number,
  data: VersionUpdate
): Promise<ApiResponse<{ version: Version }>> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  if (typeof versionId !== 'number' || isNaN(versionId)) {
    throw new Error('无效的版本 ID')
  }
  return api.put(`/projects/${projectId}/versions/${versionId}`, data)
}

/**
 * 删除版本
 */
export const deleteVersion = async (
  projectId: number,
  versionId: number
): Promise<ApiResponse> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  if (typeof versionId !== 'number' || isNaN(versionId)) {
    throw new Error('无效的版本 ID')
  }
  return api.delete(`/projects/${projectId}/versions/${versionId}`)
}

/**
 * 锁定版本
 */
export const lockVersion = async (
  projectId: number,
  versionId: number
): Promise<ApiResponse<{ version: Version }>> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  if (typeof versionId !== 'number' || isNaN(versionId)) {
    throw new Error('无效的版本 ID')
  }
  return api.post(`/projects/${projectId}/versions/${versionId}/lock`)
}

/**
 * 解锁版本
 */
export const unlockVersion = async (
  projectId: number,
  versionId: number
): Promise<ApiResponse<{ version: Version }>> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  if (typeof versionId !== 'number' || isNaN(versionId)) {
    throw new Error('无效的版本 ID')
  }
  return api.post(`/projects/${projectId}/versions/${versionId}/unlock`)
}

/**
 * 克隆版本
 */
export const cloneVersion = async (
  projectId: number,
  versionId: number,
  newVersionNumber: string
): Promise<ApiResponse<{ version: Version }>> => {
  if (typeof projectId !== 'number' || isNaN(projectId)) {
    throw new Error('无效的项目 ID')
  }
  if (typeof versionId !== 'number' || isNaN(versionId)) {
    throw new Error('无效的版本 ID')
  }
  return api.post(`/projects/${projectId}/versions/${versionId}/clone`, null, {
    params: { new_version_number: newVersionNumber }
  })
}