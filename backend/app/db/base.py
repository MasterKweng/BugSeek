"""数据库模型基类"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, Index, UniqueConstraint, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class TimestampMixin:
    """时间戳混入类"""
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class User(Base, TimestampMixin):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)  # bcrypt 加密存储
    nickname = Column(String(50), nullable=True)
    avatar = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)


class UserContext(Base, TimestampMixin):
    """用户上下文表 - 存储用户当前选择的项目和版本"""
    __tablename__ = "user_contexts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    current_project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    current_version_id = Column(Integer, ForeignKey("versions.id"), nullable=True)

    # 关系定义
    user = relationship("User", foreign_keys=[user_id])
    current_project = relationship("Project", foreign_keys=[current_project_id])
    current_version = relationship("Version", foreign_keys=[current_version_id])

    __table_args__ = (
        Index('ix_user_contexts_user_id', 'user_id'),
        Index('ix_user_contexts_current_project_id', 'current_project_id'),
        Index('ix_user_contexts_current_version_id', 'current_version_id'),
    )


class Project(Base, TimestampMixin):
    """项目表"""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    business_domain = Column(String(50), nullable=False)  # 电商/金融/SaaS/社交
    logo_url = Column(String(500), nullable=True)
    
    # 技术栈画像
    backend_language = Column(String(50), nullable=True)  # Java/Python/Go/Node
    backend_framework = Column(String(100), nullable=True)  # Spring Boot/Django/Gin
    database = Column(String(50), nullable=True)  # MySQL/PgSQL/Mongo
    frontend_framework = Column(String(100), nullable=True)  # Vue/React
    
    # 审计字段
    created_by = Column(Integer, nullable=True)  # 创建者 UID
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 所有者 UID
    is_deleted = Column(Boolean, default=False)  # 软删除标记

    __table_args__ = (
        Index('ix_projects_business_domain', 'business_domain'),
        Index('ix_projects_created_by', 'created_by'),
    )


class Version(Base, TimestampMixin):
    """版本表"""
    __tablename__ = "versions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    version_number = Column(String(50), nullable=False)  # V1.2.0
    parent_version_id = Column(Integer, ForeignKey("versions.id"), nullable=True)

    # 状态: planning(规划中) -> developing(开发中) -> testing(测试中) -> released(已发布) -> locked(已锁定)
    status = Column(String(20), default="planning")

    # 需求规约
    change_summary = Column(Text, nullable=True)  # 变更摘要
    requirement_doc = Column(Text, nullable=True)  # 需求文档内容
    test_scope = Column(JSON, nullable=True)  # 重点测试范围 [tags]

    # 预留字段
    notification_url = Column(String(500), nullable=True)  # WebHook

    __table_args__ = (
        Index('ix_versions_project_id', 'project_id'),
        Index('ix_versions_parent_version_id', 'parent_version_id'),
        Index('ix_versions_status', 'status'),
    )


class DbSchemaVersion(Base, TimestampMixin):
    """数据库结构版本（绑定项目与版本）"""
    __tablename__ = "db_schema_versions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    version_id = Column(Integer, ForeignKey("versions.id"), nullable=False)
    name = Column(String(100), nullable=False)
    source_type = Column(String(20), default="upload")  # upload/db
    source_version = Column(String(50), nullable=True)
    schema_snapshot = Column(JSON, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    project = relationship("Project", backref="db_schema_versions")
    version = relationship("Version", backref="db_schema_versions")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    __table_args__ = (
        Index('ix_db_schema_versions_project_id', 'project_id'),
        Index('ix_db_schema_versions_version_id', 'version_id'),
        Index('ix_db_schema_versions_source_type', 'source_type'),
    )


class Environment(Base, TimestampMixin):
    """环境表"""
    __tablename__ = "environments"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(50), nullable=False)  # Dev/Test/Staging/Prod
    base_url = Column(String(500), nullable=False)
    
    # V2.0 新增字段
    headers = Column(JSON, default={})  # 全局 Header 配置
    variables = Column(JSON, default={})  # 环境变量（包括鉴权账号密码等敏感信息等敏感信息）
    is_default = Column(Boolean, default=False)  # 是否为默认环境

    __table_args__ = (
        Index('ix_environments_project_id', 'project_id'),
        Index('ix_environments_name', 'name'),
    )


class GlobalVar(Base, TimestampMixin):
    """全局变量表"""
    __tablename__ = "global_vars"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    environment_id = Column(Integer, ForeignKey("environments.id"), nullable=False)
    var_key = Column(String(100), nullable=False)
    var_value = Column(Text, nullable=True)
    is_sensitive = Column(Boolean, default=False)  # 敏感标记

    __table_args__ = (
        Index('ix_global_vars_project_id', 'project_id'),
        Index('ix_global_vars_environment_id', 'environment_id'),
        Index('uq_project_env_var', 'project_id', 'environment_id', 'var_key', unique=True),
    )


class DatabaseConfig(Base, TimestampMixin):
    """数据库连接配置表"""
    __tablename__ = "database_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    alias = Column(String(50), nullable=False)
    connection_string = Column(Text, nullable=True)  # 加密存储
    db_type = Column(String(20), nullable=False)  # MySQL/PgSQL/Mongo

    __table_args__ = (
        Index('ix_database_configs_project_id', 'project_id'),
        Index('uq_project_alias', 'project_id', 'alias', unique=True),
    )


class ApiDocument(Base, TimestampMixin):
    """接口文档表"""
    __tablename__ = "api_documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    version_id = Column(Integer, ForeignKey("versions.id"), nullable=True)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)  # swagger, yapi, postman
    source_url = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    version = Column(String(50), default="1.0.0")
    parent_id = Column(Integer, ForeignKey("api_documents.id"), nullable=True)  # 父文档ID
    is_latest = Column(Boolean, default=True)  # 是否为最新版本

    __table_args__ = (
        Index('ix_api_documents_project_id', 'project_id'),
        Index('ix_api_documents_version_id', 'version_id'),
        Index('ix_api_documents_parent_id', 'parent_id'),
        Index('ix_api_documents_is_latest', 'is_latest'),
    )


class ApiEndpointGroup(Base, TimestampMixin):
    """接口分组表（用于 API 资产库）"""
    __tablename__ = "api_endpoint_groups"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)

    # 关系定义
    definitions = relationship("ApiDefinition", back_populates="group")

    __table_args__ = (
        Index('ix_api_endpoint_groups_project_id', 'project_id'),
        UniqueConstraint('project_id', 'name', name='uq_project_group_name'),
    )


class ApiDefinition(Base, TimestampMixin):
    """API 定义表（V2.0 层级一 - API 资产库）"""
    __tablename__ = "api_definitions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("api_endpoint_groups.id"), nullable=True)
    method = Column(String(10), nullable=False)  # GET/POST/PUT/DELETE
    path = Column(String(500), nullable=False)
    summary = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # ["user", "auth"]

    # 版本控制相关字段
    version_hash = Column(String(64), nullable=True)  # 接口内容的哈希值（用于版本比较）
    content_hash = Column(String(64), nullable=True)  # schema_snapshot 的哈希值
    source_type = Column(String(50), nullable=True)  # swagger, yapi, postman
    source_url = Column(String(500), nullable=True)
    source_version = Column(String(50), nullable=True)

    # Schema 存储
    schema_snapshot = Column(JSON, nullable=True)  # 完整的接口定义快照（包括 parameters, request_schema, response_schema）
    request_schema = Column(JSON, nullable=True)  # 请求参数结构（不含 parameters）
    response_schema = Column(JSON, nullable=True)  # 响应结构（不含 responses）

    # Mock 数据
    mock_data = Column(JSON, nullable=True)  # Mock 数据
    mock_rules = Column(JSON, nullable=True)  # Mock 规则

    # 状态管理
    status = Column(String(20), default="active")  # active/archived
    sync_status = Column(String(20), default="none")  # none/synced/outdated
    lock_status = Column(String(20), default="unlocked")  # unlocked/locked
    last_sync_at = Column(DateTime, nullable=True)  # 最后同步时间

    # 审计字段
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)

    # 关系定义
    group = relationship("ApiEndpointGroup", foreign_keys=[group_id])
    cases = relationship("ApiCase", back_populates="definition")

    __table_args__ = (
        Index('ix_api_definitions_project_id', 'project_id'),
        Index('ix_api_definitions_group_id', 'group_id'),
        Index('ix_api_definitions_method', 'method'),
        Index('ix_api_definitions_path', 'path'),
        Index('ix_api_definitions_version_hash', 'version_hash'),
        Index('ix_api_definitions_status', 'status'),
        UniqueConstraint('project_id', 'method', 'path', name='uq_project_method_path'),
    )


class ApiCase(Base, TimestampMixin):
    """API 测试用例表（V2.0）- 原子化测试用例，作为接口定义的派生属性"""
    __tablename__ = "api_cases"

    id = Column(Integer, primary_key=True, index=True)
    definition_id = Column(Integer, ForeignKey("api_definitions.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # 基本信息
    name = Column(String(100), nullable=False)  # 正常获取用户列表
    description = Column(Text, nullable=True)
    priority = Column(String(10), default="P2")  # P0/P1/P2/P3
    case_type = Column(String(20), default="business")  # business/performance/security/corner
    
    # 请求数据（Delta 存储格式）
    request_data = Column(JSON, nullable=True)  # 仅存储覆盖的参数值，运行时 Deep Merge
    
    # 执行配置
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="SET NULL"), nullable=True)
    
    # 断言规则（标准化格式）
    assertion_rules = Column(JSON, nullable=True)  # {"field": "data.id", "operator": "equals", "value": 1}
    
    # 变量提取规则（标准化格式）
    extraction_rules = Column(JSON, nullable=True)  # {"field": "data.id", "var_name": "user_id"}
    
    # 数据库操作
    pre_sql = Column(Text, nullable=True)  # 前置 SQL
    post_sql = Column(Text, nullable=True)  # 后置 SQL
    
    # AI 生成相关
    ai_generated = Column(Boolean, default=False)
    ai_confidence = Column(Float, nullable=True)  # 0-1
    ai_suggestions = Column(JSON, nullable=True)
    
    # 状态管理
    status = Column(String(20), default="active")  # active/archived
    fix_status = Column(String(20), default="normal")  # normal/fix_required/fixed
    
    # 审计字段
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # 关系定义
    definition = relationship("ApiDefinition", back_populates="cases")
    project = relationship("Project", backref="api_cases")
    environment = relationship("Environment", backref="api_cases")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    
    __table_args__ = (
        Index('ix_api_cases_definition_id', 'definition_id'),
        Index('ix_api_cases_project_id', 'project_id'),
        Index('ix_api_cases_environment_id', 'environment_id'),
        Index('ix_api_cases_status', 'status'),
        Index('ix_api_cases_priority', 'priority'),
        Index('ix_api_cases_ai_generated', 'ai_generated'),
    )


class SyncTask(Base, TimestampMixin):
    """文档同步任务表（V2.0 层级一 - API 资产库）"""
    __tablename__ = "sync_tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    version_id = Column(Integer, ForeignKey("versions.id"), nullable=True)
    
    # 基本信息
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)  # swagger, yapi, postman
    source_url = Column(String(500), nullable=True)
    source_version = Column(String(50), nullable=True)
    
    # 任务执行信息
    task_id = Column(String(100), nullable=True, unique=True)  # Celery 任务 ID
    status = Column(String(20), default="pending")  # pending/running/completed/failed/cancelled
    progress = Column(Integer, default=0)  # 0-100
    
    # 执行结果
    total_count = Column(Integer, default=0)  # 总接口数
    added_count = Column(Integer, default=0)  # 新增接口数
    updated_count = Column(Integer, default=0)  # 更新接口数
    deleted_count = Column(Integer, default=0)  # 删除接口数
    conflict_count = Column(Integer, default=0)  # 冲突接口数
    
    # 执行详情
    error_message = Column(Text, nullable=True)
    execution_log = Column(JSON, nullable=True)  # 执行日志列表
    
    # 变更数据（V2.0 扩展）
    diff_data = Column(JSON, nullable=True)  # 接口变更详情（新增/删除/变更的接口列表）
    impact_analysis = Column(JSON, nullable=True)  # 影响分析结果（受影响的用例和场景）
    fix_data = Column(JSON, nullable=True)  # AI 修复结果数据
    
    # 执行时间
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 审计字段
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # 关系定义
    project = relationship("Project", backref="sync_tasks")
    version = relationship("Version", backref="sync_tasks")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index('ix_sync_tasks_project_id', 'project_id'),
        Index('ix_sync_tasks_version_id', 'version_id'),
        Index('ix_sync_tasks_status', 'status'),
        Index('ix_sync_tasks_task_id', 'task_id'),
        Index('ix_sync_tasks_source_type', 'source_type'),
    )


class VersionSnapshot(Base, TimestampMixin):
    """版本快照表（V2.0）- 存储单个接口定义的版本历史"""
    __tablename__ = "version_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    definition_id = Column(Integer, ForeignKey("api_definitions.id"), nullable=True)  # 单个接口快照
    version_id = Column(Integer, ForeignKey("versions.id"), nullable=True)  # 可选，批量快照时使用
    
    # 版本信息
    version_hash = Column(String(64), nullable=True)  # 版本哈希，用于快速比对
    version_tag = Column(String(50), nullable=True)  # 版本标签（如 v1.2.3）
    source_version = Column(String(50), nullable=True)  # 文档版本标识
    
    # 快照信息
    name = Column(String(255), nullable=True)  # 快照名称
    description = Column(Text, nullable=True)  # 快照描述
    snapshot_type = Column(String(20), default="manual")  # manual/auto
    
    # 快照数据
    definition_ids = Column(JSON, nullable=False, default=list)  # 保留：批量快照（向后兼容）
    schema_snapshot = Column(JSON, nullable=True)  # 单个接口的 Schema 快照
    snapshot_data = Column(JSON, nullable=True)  # 批量快照数据（向后兼容）
    snapshot_metadata = Column(JSON, nullable=True)  # 元数据（改名为 snapshot_metadata 避免 SQLAlchemy 保留字冲突）

    # 统计信息
    total_definitions = Column(Integer, default=0)  # 快照包含的接口总数
    snapshot_size = Column(Integer, default=0)  # 快照大小（字节）

    # 审计字段
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 关系定义
    definition = relationship("ApiDefinition", foreign_keys=[definition_id])

    __table_args__ = (
        Index('ix_version_snapshots_project_id', 'project_id'),
        Index('ix_version_snapshots_definition_id', 'definition_id'),
        Index('ix_version_snapshots_version_id', 'version_id'),
        Index('ix_version_snapshots_version_hash', 'version_hash'),
        UniqueConstraint('definition_id', 'version_hash', name='uq_definition_version_hash'),
    )


# ==================== API Hub - 版本关联表 ====================

class VersionApiDefinition(Base, TimestampMixin):
    """版本与 API 定义的关联表"""
    __tablename__ = "version_api_definitions"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("versions.id"), nullable=False)
    definition_id = Column(Integer, ForeignKey("api_definitions.id"), nullable=False)
    status = Column(String(20), default="active")  # active/archived

    __table_args__ = (
        Index('ix_version_api_definitions_version_id', 'version_id'),
        Index('ix_version_api_definitions_definition_id', 'definition_id'),
        UniqueConstraint('version_id', 'definition_id', name='uq_version_definition'),
    )


class ApiFieldMapping(Base, TimestampMixin):
    """API 字段与数据库字段映射（绑定版本）"""
    __tablename__ = "api_field_mappings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    version_id = Column(Integer, ForeignKey("versions.id"), nullable=False)
    definition_id = Column(Integer, ForeignKey("api_definitions.id"), nullable=False)
    api_field_path = Column(String(255), nullable=False)  # e.g. body.order_id / path.id
    db_table = Column(String(100), nullable=False)
    db_column = Column(String(100), nullable=False)
    relation_type = Column(String(20), default="direct")  # direct/fk/derived
    confidence = Column(Float, nullable=True)
    source = Column(String(20), default="manual")  # manual/ai
    status = Column(String(20), default="confirmed")  # proposed/confirmed/rejected
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    definition = relationship("ApiDefinition", foreign_keys=[definition_id])
    project = relationship("Project", foreign_keys=[project_id])
    version = relationship("Version", foreign_keys=[version_id])
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    __table_args__ = (
        Index('ix_api_field_mappings_project_id', 'project_id'),
        Index('ix_api_field_mappings_version_id', 'version_id'),
        Index('ix_api_field_mappings_definition_id', 'definition_id'),
        Index('ix_api_field_mappings_status', 'status'),  # 添加状态索引
        UniqueConstraint(
            'project_id', 'version_id', 'definition_id', 'api_field_path', 'db_table', 'db_column',
            name='uq_field_mapping'
        ),
    )


class AsyncTask(Base, TimestampMixin):
    """异步任务表"""
    __tablename__ = "async_tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    task_type = Column(String(50), nullable=False)  # task_type
    task_config = Column(JSON, nullable=True)
    status = Column(String(20), default="pending")  # pending/running/completed/failed
    progress = Column(Integer, default=0)  # 0-100
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_async_tasks_project_id', 'project_id'),
        Index('ix_async_tasks_task_type', 'task_type'),
        Index('ix_async_tasks_status', 'status'),
    )


# ==================== 鉴权配置相关表 ====================

class ProjectAuthTemplate(Base, TimestampMixin):
    """项目级鉴权模板表"""
    __tablename__ = "project_auth_templates"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # 通用配置
    enabled = Column(Boolean, nullable=False, default=False)
    auth_type = Column(String(50), nullable=False)  # none/basic/bearer/api_key/session/custom
    
    # 注入逻辑（Consumer 层）
    injection_target = Column(String(20), nullable=False)  # header/query/cookie
    injection_key = Column(String(100), nullable=True)  # 如 Authorization、X-API-Key
    injection_template = Column(Text, nullable=True)  # 如 "Bearer {{ACCESS_TOKEN}}"
    
    # 来源模式
    source_mode = Column(String(20), nullable=False)  # static/dynamic
    
    # 静态模式数据
    static_value = Column(Text, nullable=True)  # 直接填写的凭证值（加密存储）
    
    # 动态模式数据
    login_api_id = Column(Integer, ForeignKey("api_definitions.id", ondelete="SET NULL"), nullable=True)  # 引用 API 资产库中的接口
    login_auth_type = Column(String(50), nullable=False, default='none')  # 登录接口的鉴权类型（none/basic/bearer/api_key/session/custom）
    
    # 关系定义
    template_mappings = relationship("ProjectAuthTemplateMapping", back_populates="template", cascade="all, delete-orphan")
    template_rules = relationship("ProjectAuthTemplateRule", back_populates="template", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_project_auth_templates_project_id', 'project_id'),
        Index('ix_project_auth_templates_auth_type', 'auth_type'),
        Index('ix_project_auth_templates_source_mode', 'source_mode'),
    )


class ProjectAuthTemplateMapping(Base, TimestampMixin):
    """项目模板参数映射（使用环境变量）"""
    __tablename__ = "project_auth_template_mappings"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("project_auth_templates.id", ondelete="CASCADE"), nullable=False)
    
    param_location = Column(String(20), nullable=False)  # body/query/header
    param_key = Column(String(100), nullable=False)  # 参数名
    param_value = Column(Text, nullable=False)  # 支持环境变量占位符，如 {{auth_username}}
    
    # 关系定义
    template = relationship("ProjectAuthTemplate", back_populates="template_mappings")

    __table_args__ = (
        Index('ix_project_auth_template_mappings_template_id', 'template_id'),
        Index('ix_project_auth_template_mappings_param_location', 'param_location'),
    )


class ProjectAuthTemplateRule(Base, TimestampMixin):
    """项目模板提取规则"""
    __tablename__ = "project_auth_template_rules"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("project_auth_templates.id", ondelete="CASCADE"), nullable=False)
    
    rule_name = Column(String(50), nullable=False)  # 变量名，如 ACCESS_TOKEN
    extract_source = Column(String(20), nullable=False)  # body/header/cookie
    extract_expression = Column(Text, nullable=False)  # JSONPath 或正则表达式
    
    # 关系定义
    template = relationship("ProjectAuthTemplate", back_populates="template_rules")

    __table_args__ = (
        Index('ix_project_auth_template_rules_template_id', 'template_id'),
        Index('ix_project_auth_template_rules_rule_name', 'rule_name'),
        Index('ix_project_auth_template_rules_extract_source', 'extract_source'),
    )


class AuthConfig(Base, TimestampMixin):
    """鉴权配置主表 - 改为环境级"""
    __tablename__ = "auth_configs"

    id = Column(Integer, primary_key=True, index=True)
    
    # 关键改动：从 project_id 改为 environment_id
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # 保留 project_id 作为冗余索引（方便查询）
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # 新增：继承标记
    inherit_from_project = Column(Boolean, default=False)  # 是否继承项目级模板
    
    # 通用配置
    enabled = Column(Boolean, nullable=False, default=False)
    auth_type = Column(String(50), nullable=False)  # none/basic/bearer/api_key/session/custom
    
    # 注入逻辑（Consumer 层）
    injection_target = Column(String(20), nullable=False)  # header/query/cookie
    injection_key = Column(String(100), nullable=True)  # 如 Authorization、X-API-Key
    injection_template = Column(Text, nullable=True)  # 如 "Bearer {{ACCESS_TOKEN}}"
    
    # 来源模式
    source_mode = Column(String(20), nullable=False)  # static/dynamic
    
    # 静态模式数据
    static_value = Column(Text, nullable=True)  # 直接填写的凭证值（加密存储）
    
    # 动态模式数据
    login_api_id = Column(Integer, ForeignKey("api_definitions.id", ondelete="SET NULL"), nullable=True)  # 引用 API 资产库中的接口
    login_auth_type = Column(String(50), nullable=False, default='none')  # 登录接口的鉴权类型（none/basic/bearer/api_key/session/custom）
    
    # 关系定义
    input_mappings = relationship("AuthInputMapping", back_populates="auth_config", cascade="all, delete-orphan")
    extract_rules = relationship("AuthExtractRule", back_populates="auth_config", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_auth_configs_environment_id', 'environment_id'),
        Index('ix_auth_configs_project_id', 'project_id'),
        Index('ix_auth_configs_inherit_from_project', 'inherit_from_project'),
        Index('ix_auth_configs_auth_type', 'auth_type'),
        Index('ix_auth_configs_login_api_id', 'login_api_id'),
        Index('ix_auth_configs_source_mode', 'source_mode'),
    )


class AuthInputMapping(Base, TimestampMixin):
    """鉴权输入参数映射表"""
    __tablename__ = "auth_input_mappings"

    id = Column(Integer, primary_key=True, index=True)
    auth_config_id = Column(Integer, ForeignKey("auth_configs.id", ondelete="CASCADE"), nullable=False)
    
    param_location = Column(String(20), nullable=False)  # body/query/header
    param_key = Column(String(100), nullable=False)  # 参数名
    param_value = Column(Text, nullable=False)  # 支持环境变量 {{env_var}}
    
    # 关系定义
    auth_config = relationship("AuthConfig", back_populates="input_mappings")

    __table_args__ = (
        Index('ix_auth_input_mappings_auth_config_id', 'auth_config_id'),
        Index('ix_auth_input_mappings_param_location', 'param_location'),
    )


class AuthExtractRule(Base, TimestampMixin):
    """鉴权提取规则表"""
    __tablename__ = "auth_extract_rules"

    id = Column(Integer, primary_key=True, index=True)
    auth_config_id = Column(Integer, ForeignKey("auth_configs.id", ondelete="CASCADE"), nullable=False)
    
    rule_name = Column(String(50), nullable=False)  # 变量名，如 ACCESS_TOKEN、CSRF_TOKEN
    extract_source = Column(String(20), nullable=False)  # body/header/cookie
    extract_expression = Column(Text, nullable=False)  # JSONPath 或 Header/Cookie 名
    
    # 关系定义
    auth_config = relationship("AuthConfig", back_populates="extract_rules")

    __table_args__ = (
        Index('ix_auth_extract_rules_auth_config_id', 'auth_config_id'),
        Index('ix_auth_extract_rules_rule_name', 'rule_name'),
        Index('ix_auth_extract_rules_extract_source', 'extract_source'),
    )


class TestExecution(Base, TimestampMixin):
    """统一测试执行记录表（支持单接口、场景、套件）V2.0 层级一"""
    __tablename__ = "test_executions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # 执行类型：single | scenario | suite
    execution_type = Column(String(20), nullable=False, index=True)

    # 关联ID（根据类型不同，指向不同的表）
    target_id = Column(Integer, nullable=False, index=True)  # script_id | scenario_id | suite_id

    # 执行环境
    environment_id = Column(Integer, ForeignKey("environments.id"), nullable=True)

    # 执行配置
    execution_mode = Column(String(20))  # sequential | parallel
    triggered_by = Column(String(50), index=True)  # manual | jenkins | schedule

    # 执行状态
    status = Column(String(20), default="pending", index=True)  # pending | running | completed | failed
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration = Column(Integer)

    # 执行统计
    total = Column(Integer)
    passed = Column(Integer)
    failed = Column(Integer)
    skipped = Column(Integer)

    # Jenkins 相关（仅套件执行需要）
    jenkins_job_name = Column(String(100))
    jenkins_build_number = Column(Integer)
    jenkins_build_url = Column(String(255))

    # CI/CD 回调
    webhook_url = Column(String(255))
    callback_status = Column(String(20))

    # 关系定义
    environment = relationship("Environment", foreign_keys=[environment_id])

    __table_args__ = (
        Index('ix_test_executions_project_id', 'project_id'),
        Index('ix_test_executions_execution_type', 'execution_type'),
        Index('ix_test_executions_target_id', 'target_id'),
        Index('ix_test_executions_status', 'status'),
        Index('ix_test_executions_triggered_by', 'triggered_by'),
    )


class TestExecutionResult(Base, TimestampMixin):
    """测试执行结果明细表 V2.0 层级一"""
    __tablename__ = "test_execution_results"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("test_executions.id"), nullable=False, index=True)

    # 原始数据
    target_type = Column(String(20), index=True)  # script | endpoint
    target_id = Column(Integer, index=True)

    # 执行结果
    status = Column(String(20), index=True)
    response_time = Column(Integer)
    response_code = Column(Integer)
    response_body = Column(JSON)
    request_body = Column(JSON)

    # 断言结果
    assertion_results = Column(JSON)
    extracted_variables = Column(JSON)  # 提取的变量字典
    error_message = Column(Text)

    # 关系定义
    execution = relationship("TestExecution", foreign_keys=[execution_id])

    __table_args__ = (
        Index('ix_test_execution_results_execution_id', 'execution_id'),
        Index('ix_test_execution_results_target_type', 'target_type'),
        Index('ix_test_execution_results_target_id', 'target_id'),
        Index('ix_test_execution_results_status', 'status'),
    )
