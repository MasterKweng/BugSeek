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

export type FieldMappingEvidenceMode = 'balanced' | 'conservative' | 'aggressive'

export interface ProjectAssetConfig {
  repository?: {
    repo_url?: string
    default_branch?: string
    workspace_root?: string
    orm_framework?: string
  }
  dictionary?: {
    enum_rules_text?: string
    business_terms_text?: string
  }
  risk_policy?: {
    high_risk_fields_text?: string
    allow_ai_override?: boolean
    require_manual_review?: boolean
    auto_accept_min_confidence?: number
  }
  field_mapping_defaults?: {
    use_ai?: boolean
    use_sql_lineage?: boolean
    use_code_lineage?: boolean
    use_runtime_verification?: boolean
    evidence_mode?: FieldMappingEvidenceMode
  }
}

export interface VersionMappingConfig {
  schema_binding?: {
    selected_schema_id?: number | null
  }
  runtime_binding?: {
    selected_execution_ids?: number[]
    auto_build_sql_lineage?: boolean
  }
  field_mapping_overrides?: {
    use_sql_lineage?: boolean
    use_code_lineage?: boolean
    use_runtime_verification?: boolean
    allow_ai?: boolean
    high_risk_manual_review?: boolean
    rule_overrides_text?: string
  }
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
  asset_config?: ProjectAssetConfig | null
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
  asset_config?: ProjectAssetConfig
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
  asset_config?: ProjectAssetConfig
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
  mapping_config?: VersionMappingConfig | null
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
  mapping_config?: VersionMappingConfig
}

export interface VersionUpdate {
  version_number?: string
  status?: string
  change_summary?: string
  requirement_doc?: string
  test_scope?: string[]
  mapping_config?: VersionMappingConfig
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

// 数据库结构相关类型
export interface DbSchemaSummary {
  id: number
  project_id: number
  version_id: number
  name: string
  source_type: string
  source_version: string | null
  table_count: number
  created_at: string
  updated_at: string
}

export interface DbSchemaListResponse {
  total: number
  items: DbSchemaSummary[]
}

export interface DbSchemaDetail extends DbSchemaSummary {
  schema_snapshot: Record<string, any>
}

// 字段映射相关类型
export interface FieldMapping {
  id: number
  project_id: number
  version_id: number
  definition_id: number
  definition_method?: string
  definition_path?: string
  api_field_path: string
  db_table: string
  db_column: string
  relation_type?: string
  confidence?: number | null
  source?: string | null
  status?: string  // 新增：映射状态 (proposed/confirmed/rejected)
  created_at: string
  updated_at: string
}

export interface FieldMappingListResponse {
  total: number
  items: FieldMapping[]
}
