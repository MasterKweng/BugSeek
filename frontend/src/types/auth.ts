/**
 * 鉴权配置类型定义
 * 符合前端代码规范
 */

// ==================== 枚举类型 ====================

/**
 * 鉴权类型
 */
export enum AuthTypeEnum {
  NONE = 'none',
  BASIC = 'basic',
  BEARER = 'bearer',
  API_KEY = 'api_key',
  SESSION = 'session',
  CUSTOM = 'custom'
}

/**
 * 注入位置
 */
export enum InjectionTargetEnum {
  HEADER = 'header',
  QUERY = 'query',
  COOKIE = 'cookie'
}

/**
 * 来源模式
 */
export enum SourceModeEnum {
  STATIC = 'static',
  DYNAMIC = 'dynamic'
}

/**
 * 提取来源
 */
export enum ExtractSourceEnum {
  BODY = 'body',
  HEADER = 'header',
  COOKIE = 'cookie'
}

/**
 * 参数位置
 */
export enum MappingLocationEnum {
  BODY = 'body',
  HEADER = 'header',
  QUERY = 'query'
}

// ==================== 数据类型 ====================

/**
 * 注入配置
 */
export interface InjectionConfig {
  target: InjectionTargetEnum;
  key?: string;
  value_template: string;
}

/**
 * 参数映射
 */
export interface InputMapping {
  location: MappingLocationEnum;
  key: string;
  value: string;
}

/**
 * 提取规则
 */
export interface ExtractRule {
  name: string;
  source: ExtractSourceEnum;
  expression: string;
}

/**
 * 环境级鉴权配置
 */
export interface AuthConfig {
  id?: number;
  environment_id: number;
  project_id: number;
  enabled: boolean;
  auth_type: AuthTypeEnum;
  injection: InjectionConfig;
  source_mode: SourceModeEnum;
  static_value?: string;
  login_api_id?: number;
  login_auth_type: AuthTypeEnum;
  inherit_from_project: boolean;
  input_mappings: InputMapping[];
  extract_rules: ExtractRule[];
  created_at?: string;
  updated_at?: string;
  _meta?: {
    inherited_from?: string;
    can_override?: boolean;
  };
}

/**
 * 项目级鉴权模板
 */
export interface ProjectAuthTemplate {
  id?: number;
  project_id: number;
  enabled: boolean;
  auth_type: AuthTypeEnum;
  injection: InjectionConfig;
  source_mode: SourceModeEnum;
  static_value?: string;
  login_api_id?: number;
  login_auth_type: AuthTypeEnum;
  input_mappings: InputMapping[];
  extract_rules: ExtractRule[];
  created_at?: string;
  updated_at?: string;
}

/**
 * 创建鉴权配置请求
 */
export interface AuthConfigCreate {
  enabled: boolean;
  auth_type: AuthTypeEnum;
  injection: InjectionConfig;
  source_mode: SourceModeEnum;
  static_value?: string;
  login_api_id?: number;
  login_auth_type: AuthTypeEnum;
  input_mappings?: InputMapping[];
  extract_rules?: ExtractRule[];
}

/**
 * 更新鉴权配置请求
 */
export interface AuthConfigUpdate {
  enabled?: boolean;
  auth_type?: AuthTypeEnum;
  injection?: InjectionConfig;
  source_mode?: SourceModeEnum;
  static_value?: string;
  login_api_id?: number;
  login_auth_type?: AuthTypeEnum;
  input_mappings?: InputMapping[];
  extract_rules?: ExtractRule[];
}

/**
 * 创建项目模板请求
 */
export interface ProjectAuthTemplateCreate {
  enabled: boolean;
  auth_type: AuthTypeEnum;
  injection: InjectionConfig;
  source_mode: SourceModeEnum;
  static_value?: string;
  login_api_id?: number;
  login_auth_type: AuthTypeEnum;
  input_mappings?: InputMapping[];
  extract_rules?: ExtractRule[];
}

/**
 * 更新项目模板请求
 */
export interface ProjectAuthTemplateUpdate {
  enabled?: boolean;
  auth_type?: AuthTypeEnum;
  injection?: InjectionConfig;
  source_mode?: SourceModeEnum;
  static_value?: string;
  login_api_id?: number;
  login_auth_type?: AuthTypeEnum;
  input_mappings?: InputMapping[];
  extract_rules?: ExtractRule[];
}

/**
 * 测试登录请求
 */
export interface TestAcquisitionRequest {
  // 暂时不需要参数
}

/**
 * 测试登录响应
 */
export interface TestAcquisitionResponse {
  success: boolean;
  message: string;
  extracted_vars: Record<string, string>;
  response_data?: string;
  error?: string;
}

/**
 * 统一 API 响应
 */
export interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
}

// ==================== 枚举显示名称 ====================

/**
 * 鉴权类型显示名称
 */
export const AuthTypeLabels: Record<AuthTypeEnum, string> = {
  [AuthTypeEnum.NONE]: '无鉴权',
  [AuthTypeEnum.BASIC]: 'Basic Auth',
  [AuthTypeEnum.BEARER]: 'Bearer Token',
  [AuthTypeEnum.API_KEY]: 'API Key',
  [AuthTypeEnum.SESSION]: 'Session',
  [AuthTypeEnum.CUSTOM]: '自定义'
};

/**
 * 注入位置显示名称
 */
export const InjectionTargetLabels: Record<InjectionTargetEnum, string> = {
  [InjectionTargetEnum.HEADER]: '请求头',
  [InjectionTargetEnum.QUERY]: '查询参数',
  [InjectionTargetEnum.COOKIE]: 'Cookie'
};

/**
 * 来源模式显示名称
 */
export const SourceModeLabels: Record<SourceModeEnum, string> = {
  [SourceModeEnum.STATIC]: '静态凭证',
  [SourceModeEnum.DYNAMIC]: '动态登录'
};

/**
 * 提取来源显示名称
 */
export const ExtractSourceLabels: Record<ExtractSourceEnum, string> = {
  [ExtractSourceEnum.BODY]: '响应体',
  [ExtractSourceEnum.HEADER]: '响应头',
  [ExtractSourceEnum.COOKIE]: 'Cookie'
};

/**
 * 参数位置显示名称
 */
export const MappingLocationLabels: Record<MappingLocationEnum, string> = {
  [MappingLocationEnum.BODY]: '请求体',
  [MappingLocationEnum.HEADER]: '请求头',
  [MappingLocationEnum.QUERY]: '查询参数'
};