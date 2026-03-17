/**
 * 鉴权配置 API 服务
 * 符合前端代码规范
 */

import api from './api';
import {
  AuthConfig,
  AuthConfigCreate,
  AuthConfigUpdate,
  ProjectAuthTemplate,
  ProjectAuthTemplateCreate,
  ProjectAuthTemplateUpdate,
  TestAcquisitionRequest,
  TestAcquisitionResponse,
  ApiResponse
} from '../types/auth';

// ==================== 项目模板相关 ====================

/**
 * 获取项目鉴权模板
 * @param projectId 项目 ID
 */
export const getProjectAuthTemplate = (
  projectId: number
): Promise<ApiResponse<ProjectAuthTemplate>> => {
  return api.get(`/projects/${projectId}/auth-template`);
};

/**
 * 创建项目级鉴权模板
 */
export const createProjectAuthTemplate = (
  projectId: number,
  data: ProjectAuthTemplateCreate
): Promise<ApiResponse<ProjectAuthTemplate>> => {
  return api.post(`/projects/${projectId}/auth-template`, data);
};

/**
 * 更新项目级鉴权模板
 */
export const updateProjectAuthTemplate = (
  projectId: number,
  data: ProjectAuthTemplateUpdate
): Promise<ApiResponse<ProjectAuthTemplate>> => {
  return api.put(`/projects/${projectId}/auth-template`, data);
};

/**
 * 删除项目级鉴权模板
 */
export const deleteProjectAuthTemplate = (projectId: number): Promise<ApiResponse<null>> => {
  return api.delete(`/projects/${projectId}/auth-template`);
};

// ==================== 环境级配置相关 ====================

/**
 * 获取环境鉴权配置
 * @param projectId 项目 ID
 * @param environmentId 环境 ID
 */
export const getEnvironmentAuthConfig = (
  projectId: number,
  environmentId: number
): Promise<ApiResponse<AuthConfig>> => {
  return api.get(`/projects/${projectId}/environments/${environmentId}/auth-config`);
};

/**
 * 创建环境级鉴权配置
 * @param projectId 项目 ID
 * @param environmentId 环境 ID
 * @param data 配置数据
 * @param inheritFromProject 是否继承项目模板
 */
export const createEnvironmentAuthConfig = (
  projectId: number,
  environmentId: number,
  data: AuthConfigCreate,
  inheritFromProject: boolean = false
): Promise<ApiResponse<AuthConfig>> => {
  return api.post(
    `/projects/${projectId}/environments/${environmentId}/auth-config`,
    data,
    { params: inheritFromProject ? { inherit_from_project: true } : undefined }
  );
};

/**
 * 更新环境级鉴权配置
 */
export const updateEnvironmentAuthConfig = (
  projectId: number,
  environmentId: number,
  data: AuthConfigUpdate
): Promise<ApiResponse<AuthConfig>> => {
  return api.put(
    `/projects/${projectId}/environments/${environmentId}/auth-config`,
    data
  );
};

/**
 * 删除环境级鉴权配置
 */
export const deleteEnvironmentAuthConfig = (
  projectId: number,
  environmentId: number
): Promise<ApiResponse<null>> => {
  return api.delete(
    `/projects/${projectId}/environments/${environmentId}/auth-config`
  );
};

/**
 * 测试登录与凭证提取
 */
export const testAcquisition = (
  projectId: number,
  data: TestAcquisitionRequest
): Promise<ApiResponse<TestAcquisitionResponse>> => {
  return api.post(`/projects/${projectId}/auth-config/test-acquisition`, data);
};

/**
 * 默认导出
 */
export default {
  getProjectAuthTemplate,
  createProjectAuthTemplate,
  updateProjectAuthTemplate,
  deleteProjectAuthTemplate,
  getEnvironmentAuthConfig,
  createEnvironmentAuthConfig,
  updateEnvironmentAuthConfig,
  deleteEnvironmentAuthConfig,
  testAcquisition
};
