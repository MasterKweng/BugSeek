import * as request from './request'

export interface Variable {
  id: number
  project_id: number
  environment_id: number
  var_key: string
  var_value: string
  is_sensitive: boolean
  created_at: string
  updated_at: string
}

export interface VariableListResponse {
  total: number
  page: number
  page_size: number
  items: Variable[]
}

export interface VariableCreate {
  var_key: string
  var_value: string
  is_sensitive?: boolean
}

export interface VariableUpdate {
  var_key?: string
  var_value?: string
  is_sensitive?: boolean
}

export const getEnvironmentVariables = (
  projectId: number,
  envId: number,
  page = 1,
  pageSize = 100,
): Promise<VariableListResponse> => {
  return request.get(`/projects/${projectId}/environments/${envId}/vars`, {
    page,
    page_size: pageSize,
  })
}

export const getEnvironmentVariable = (
  projectId: number,
  envId: number,
  varId: number,
): Promise<Variable> => {
  return request.get(`/projects/${projectId}/environments/${envId}/vars/${varId}`)
}

export const createEnvironmentVariable = (
  projectId: number,
  envId: number,
  data: VariableCreate,
): Promise<{ variable: Variable }> => {
  return request.post(`/projects/${projectId}/environments/${envId}/vars`, data)
}

export const updateEnvironmentVariable = (
  projectId: number,
  envId: number,
  varId: number,
  data: VariableUpdate,
): Promise<{ variable: Variable }> => {
  return request.put(`/projects/${projectId}/environments/${envId}/vars/${varId}`, data)
}

export const deleteEnvironmentVariable = (
  projectId: number,
  envId: number,
  varId: number,
): Promise<{ message: string }> => {
  return request.del(`/projects/${projectId}/environments/${envId}/vars/${varId}`)
}

