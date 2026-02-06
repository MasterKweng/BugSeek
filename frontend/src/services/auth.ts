/**
 * 鉴权配置 API 服务
 * 符合前端代码规范
 */

import request from '../services/request';
import {
  AuthConfig,
  AuthConfigCreate,
  AuthConfigUpdate,
  TestAcquisitionRequest,
  TestAcquisitionResponse,
  ApiResponse
} from '../types/auth';

const BASE_URL = '/api/v1';

/**
 * 获取项目鉴权配置
 */
export const getAuthConfig = (projectId: number): Promise<ApiResponse<AuthConfig>> => {
  return request.get(`${BASE_URL}/projects/${projectId}/auth-config`);
};

/**
 * 创建项目鉴权配置
 */
export const createAuthConfig = (
  projectId: number,
  data: AuthConfigCreate
): Promise<ApiResponse<AuthConfig>> => {
  return request.post(`${BASE_URL}/projects/${projectId}/auth-config`, data);
};

/**
 * 更新项目鉴权配置
 */
export const updateAuthConfig = (
  projectId: number,
  data: AuthConfigUpdate
): Promise<ApiResponse<AuthConfig>> => {
  return request.put(`${BASE_URL}/projects/${projectId}/auth-config`, data);
};

/**
 * 删除项目鉴权配置
 */
export const deleteAuthConfig = (projectId: number): Promise<ApiResponse<null>> => {
  return request.delete(`${BASE_URL}/projects/${projectId}/auth-config`);
};

/**
 * 测试登录和提取规则
 */
export const testAcquisition = (
  projectId: number,
  data: TestAcquisitionRequest
): Promise<ApiResponse<TestAcquisitionResponse>> => {
  return request.post(`${BASE_URL}/projects/${projectId}/auth-config/test-acquisition`, data);
};

/**
 * 默认导出
 */
export default {
  getAuthConfig,
  createAuthConfig,
  updateAuthConfig,
  deleteAuthConfig,
  testAcquisition
};