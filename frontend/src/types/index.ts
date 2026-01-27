export interface User {
  id: number
  username: string
  email: string
  nickname: string | null
  avatar: string | null
}

export interface ApiDocument {
  id: number
  name: string
  source_type: string
  source_url: string | null
  version: string
  created_at: string
}

export interface ApiEndpoint {
  id: number
  path: string
  method: string
  summary: string | null
  description: string | null
  tags: string[] | null
}

// 环境相关类型
export interface ProjectEnvironment {
  id: number
  name: string
  base_url: string
}

// 项目相关类型
export interface Project {
  id: number
  name: string
  description: string | null
  business_domain: string
  logo_url: string | null
  backend_language: string | null
  backend_framework: string | null
  database: string | null
  frontend_framework: string | null
  created_by: number | null
  owner_id: number | null
  is_deleted: boolean
  created_at: string
  updated_at: string
  // 环境列表
  environments?: ProjectEnvironment[]
  // 环境数量
  environments_count?: number
}

export interface ProjectCreate {
  name: string
  description?: string
  business_domain: string
  logo_url?: string
  backend_language?: string
  backend_framework?: string
  database?: string
  frontend_framework?: string
}

export interface ProjectUpdate {
  name?: string
  description?: string
  business_domain?: string
  logo_url?: string
  backend_language?: string
  backend_framework?: string
  database?: string
  frontend_framework?: string
}

export interface TechStackUpdate {
  backend_language?: string
  backend_framework?: string
  database?: string
  frontend_framework?: string
}

export interface ProjectListResponse {
  total: number
  page: number
  page_size: number
  items: Project[]
}

// 版本相关类型
export interface Version {
  id: number
  project_id: number
  version_number: string
  parent_version_id: number | null
  status: string
  change_summary: string | null
  requirement_doc: string | null
  test_scope: string[] | null
  endpoints_count: number
  test_cases_count: number
  notification_url: string | null
  created_at: string
  updated_at: string
}

export interface VersionCreate {
  project_id: number
  version_number: string
  parent_version_id?: number
  change_summary?: string
  requirement_doc?: string
  test_scope?: string[]
}

export interface VersionUpdate {
  version_number?: string
  status?: string
  change_summary?: string
  requirement_doc?: string
  test_scope?: string[]
  endpoints_count?: number
  test_cases_count?: number
}

export interface VersionListResponse {
  total: number
  page: number
  page_size: number
  items: Version[]
}

// API 响应类型
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}