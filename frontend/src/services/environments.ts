/**
 * 环境管理 API 服务
 * 符合前端代码规范
 */

import * as request from './request';

/**
 * 环境数据结构
 */
export interface Environment {
  id: number;
  project_id: number;
  name: string;
  base_url: string;
  headers?: Record<string, string>;
  variables?: Record<string, any>;
  is_default?: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * 环境列表响应
 */
export interface EnvironmentListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Environment[];
}

export interface EnvironmentCreate {
  name: string;
  base_url: string;
  headers?: Record<string, string>;
  variables?: Record<string, any>;
  is_default?: boolean;
}

export interface EnvironmentUpdate {
  name?: string;
  base_url?: string;
  headers?: Record<string, string>;
  variables?: Record<string, any>;
  is_default?: boolean;
}

/**
 * 获取项目的环境列表
 * @param projectId 项目 ID
 * @param page 页码
 * @param pageSize 每页数量
 */
export const getProjectEnvironments = (
  projectId: number,
  page: number = 1,
  pageSize: number = 100
): Promise<EnvironmentListResponse> => {
  return request.get(`/projects/${projectId}/environments`, {
    page,
    page_size: pageSize
  });
};

/**
 * 获取环境详情
 * @param projectId 项目 ID
 * @param envId 环境 ID
 */
export const getEnvironment = (
  projectId: number,
  envId: number
): Promise<Environment> => {
  return request.get(`/projects/${projectId}/environments/${envId}`);
};

export const createEnvironment = (
  projectId: number,
  data: EnvironmentCreate
): Promise<{ environment: Environment }> => {
  return request.post(`/projects/${projectId}/environments`, data);
};

export const updateEnvironment = (
  projectId: number,
  envId: number,
  data: EnvironmentUpdate
): Promise<{ environment: Environment }> => {
  return request.put(`/projects/${projectId}/environments/${envId}`, data);
};

export const deleteEnvironment = (
  projectId: number,
  envId: number
): Promise<{ message: string }> => {
  return request.del(`/projects/${projectId}/environments/${envId}`);
};

export default {
  getProjectEnvironments,
  getEnvironment,
  createEnvironment,
  updateEnvironment,
  deleteEnvironment,
};
