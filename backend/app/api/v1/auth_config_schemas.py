"""
鉴权配置 Pydantic 模型

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. 全链路 TraceID：使用 get_trace_id()
3. 完善的错误处理和日志记录
4. 魔法值清理：使用枚举定义状态
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ==================== 枚举定义 ====================

class AuthTypeEnum(str, Enum):
    """鉴权类型枚举"""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    SESSION = "session"
    CUSTOM = "custom"


class InjectionTargetEnum(str, Enum):
    """注入位置枚举"""
    HEADER = "header"
    QUERY = "query"
    COOKIE = "cookie"


class SourceModeEnum(str, Enum):
    """来源模式枚举"""
    STATIC = "static"
    DYNAMIC = "dynamic"


class ExtractSourceEnum(str, Enum):
    """提取来源枚举"""
    BODY = "body"
    HEADER = "header"
    COOKIE = "cookie"


class MappingLocationEnum(str, Enum):
    """参数位置枚举"""
    BODY = "body"
    QUERY = "query"
    HEADER = "header"


# ==================== 注入配置 ====================

class InjectionConfig(BaseModel):
    """注入配置（Consumer 层）"""
    target: InjectionTargetEnum = Field(..., description="注入位置：header/query/cookie")
    key: Optional[str] = Field(None, description="Header/Query/Cookie 名称")
    value_template: Optional[str] = Field(None, description="值模板，支持变量 {{ACCESS_TOKEN}}")

    class Config:
        use_enum_values = True


# ==================== 参数映射 ====================

class InputMapping(BaseModel):
    """参数映射"""
    location: MappingLocationEnum = Field(..., description="参数位置：body/query/header")
    key: str = Field(..., min_length=1, max_length=100, description="参数名")
    value: str = Field(..., description="参数值，支持环境变量 {{env_var}}")

    @validator('value')
    def validate_value(cls, v):
        if not v:
            raise ValueError('参数值不能为空')
        return v

    class Config:
        use_enum_values = True


# ==================== 提取规则 ====================

class ExtractRule(BaseModel):
    """提取规则"""
    name: str = Field(..., min_length=1, max_length=50, description="变量名，如 ACCESS_TOKEN、CSRF_TOKEN")
    source: ExtractSourceEnum = Field(..., description="提取来源：body/header/cookie")
    expression: str = Field(..., min_length=1, description="JSONPath 或 Header/Cookie 名")

    @validator('name')
    def validate_name(cls, v):
        if not v.isidentifier():
            raise ValueError('变量名必须是有效的标识符')
        return v.upper()

    class Config:
        use_enum_values = True


# ==================== 鉴权配置 CRUD ====================

class AuthConfigCreate(BaseModel):
    """创建鉴权配置请求"""
    enabled: bool = Field(default=False, description="是否启用鉴权")
    auth_type: AuthTypeEnum = Field(..., description="鉴权类型")
    injection: InjectionConfig = Field(..., description="注入配置")
    source_mode: SourceModeEnum = Field(default=SourceModeEnum.STATIC, description="来源模式")
    static_value: Optional[str] = Field(None, description="静态凭证值（加密存储）")
    login_api_id: Optional[int] = Field(None, description="登录接口 ID（动态模式）")
    input_mappings: Optional[List[InputMapping]] = Field(default_factory=list, description="参数映射列表")
    extract_rules: Optional[List[ExtractRule]] = Field(default_factory=list, description="提取规则列表")


class AuthConfigUpdate(BaseModel):
    """更新鉴权配置请求"""
    enabled: Optional[bool] = Field(None, description="是否启用鉴权")
    auth_type: Optional[AuthTypeEnum] = Field(None, description="鉴权类型")
    injection: Optional[InjectionConfig] = Field(None, description="注入配置")
    source_mode: Optional[SourceModeEnum] = Field(None, description="来源模式")
    static_value: Optional[str] = Field(None, description="静态凭证值")
    login_api_id: Optional[int] = Field(None, description="登录接口 ID")
    input_mappings: Optional[List[InputMapping]] = Field(None, description="参数映射列表")
    extract_rules: Optional[List[ExtractRule]] = Field(None, description="提取规则列表")


class AuthConfigResponse(BaseModel):
    """鉴权配置响应"""
    id: int
    project_id: int
    enabled: bool
    auth_type: str
    injection: Dict[str, Any]
    source_mode: str
    static_value: Optional[str]
    login_api_id: Optional[int]
    input_mappings: List[InputMapping]
    extract_rules: List[ExtractRule]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


# ==================== 测试登录请求 ====================

class TestAcquisitionRequest(BaseModel):
    """测试登录请求"""
    input_mappings: List[InputMapping] = Field(..., description="参数映射列表")
    extract_rules: List[ExtractRule] = Field(..., description="提取规则列表")


class TestAcquisitionResponse(BaseModel):
    """测试登录响应"""
    success: bool = Field(..., description="是否成功")
    extracted_vars: Dict[str, str] = Field(default_factory=dict, description="提取的变量")
    response_data: Optional[Dict[str, Any]] = Field(None, description="登录接口响应数据")
    error: Optional[str] = Field(None, description="错误信息")


# ==================== 统一响应体 ====================

class ApiResponse(BaseModel):
    """统一 API 响应"""
    code: int = Field(..., description="状态码：0成功，-1失败")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")