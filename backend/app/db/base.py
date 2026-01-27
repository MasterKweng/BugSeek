"""数据库模型基类"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, Index, UniqueConstraint
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

    # 继承策略（引用方式）
    inherit_endpoints = Column(Boolean, default=True)   # 是否继承接口定义
    inherit_test_cases = Column(Boolean, default=True)  # 是否继承测试用例
    inherit_environments = Column(Boolean, default=True) # 是否继承环境配置

    # 需求规约
    change_summary = Column(Text, nullable=True)  # 变更摘要
    requirement_doc = Column(Text, nullable=True)  # 需求文档内容
    test_scope = Column(JSON, nullable=True)  # 重点测试范围 [tags]

    # 统计数据
    endpoints_count = Column(Integer, default=0)
    test_cases_count = Column(Integer, default=0)

    # 预留字段
    notification_url = Column(String(500), nullable=True)  # WebHook

    __table_args__ = (
        Index('ix_versions_project_id', 'project_id'),
        Index('ix_versions_parent_version_id', 'parent_version_id'),
        Index('ix_versions_status', 'status'),
    )


class Environment(Base, TimestampMixin):
    """环境表"""
    __tablename__ = "environments"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(50), nullable=False)  # Dev/Test/Staging/Prod
    base_url = Column(String(500), nullable=False)

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


class ApiEndpoint(Base, TimestampMixin):
    """接口定义表"""
    __tablename__ = "api_endpoints"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    document_id = Column(Integer, nullable=True)  # 移除外键约束，改为普通字段
    path = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False)
    summary = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    request_schema = Column(JSON, nullable=True)
    response_schema = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)  # ["user", "auth"]
    group_id = Column(Integer, ForeignKey("api_endpoint_groups.id"), nullable=True)

    # 关系定义
    group = relationship("ApiEndpointGroup", foreign_keys=[group_id])

    __table_args__ = (
        Index('ix_api_endpoints_project_id', 'project_id'),
        Index('ix_api_endpoints_document_id', 'document_id'),
        Index('ix_api_endpoints_path_method', 'path', 'method'),
        Index('ix_api_endpoints_group_id', 'group_id'),
    )


class VersionEndpoint(Base, TimestampMixin):
    """版本与接口的关联表"""
    __tablename__ = "version_endpoints"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("versions.id"), nullable=False)
    endpoint_id = Column(Integer, ForeignKey("api_endpoints.id"), nullable=False)


class ApiEndpointGroup(Base, TimestampMixin):
    """接口分组表"""
    __tablename__ = "api_endpoint_groups"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)

    # 关系定义
    endpoints = relationship("ApiEndpoint", back_populates="group")

    __table_args__ = (
        Index('ix_api_endpoint_groups_project_id', 'project_id'),
        UniqueConstraint('project_id', 'name', name='uq_project_group_name'),
    )


class ApiTestScript(Base, TimestampMixin):
    """测试脚本表"""
    __tablename__ = "api_test_scripts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    endpoint_id = Column(Integer, ForeignKey("api_endpoints.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    script_content = Column(JSON, nullable=False)  # 脚本内容（JSON格式）
    test_type = Column(String(50), nullable=False)  # positive/negative/boundary/exception
    generated_by = Column(String(50), default="ai")  # ai/manual
    status = Column(String(20), default="active")  # active/archived

    # 关系定义
    endpoint = relationship("ApiEndpoint", foreign_keys=[endpoint_id])

    __table_args__ = (
        Index('ix_api_test_scripts_project_id', 'project_id'),
        Index('ix_api_test_scripts_endpoint_id', 'endpoint_id'),
        Index('ix_api_test_scripts_test_type', 'test_type'),
    )


class TestType(Base, TimestampMixin):
    """测试类型配置表"""
    __tablename__ = "test_types"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(50), nullable=False)
    code = Column(String(50), nullable=False)
    description = Column(Text)
    is_preset = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    
    __table_args__ = (
        Index('ix_test_types_project_id', 'project_id'),
        UniqueConstraint('project_id', 'code', name='uq_project_type_code'),
    )


class ScriptGeneration(Base, TimestampMixin):
    """脚本生成记录表"""
    __tablename__ = "script_generations"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    endpoint_id = Column(Integer, ForeignKey("api_endpoints.id"), nullable=False)
    test_types = Column(JSON, nullable=False)
    generated_count = Column(Integer, default=0)
    status = Column(String(20), default="completed")
    error_message = Column(Text)
    
    __table_args__ = (
        Index('ix_script_generations_project_id', 'project_id'),
        Index('ix_script_generations_endpoint_id', 'endpoint_id'),
    )


class ScriptExecution(Base, TimestampMixin):
    """脚本执行记录表"""
    __tablename__ = "script_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    script_id = Column(Integer, ForeignKey("api_test_scripts.id"), nullable=False)
    endpoint_id = Column(Integer, ForeignKey("api_endpoints.id"), nullable=False)
    environment_id = Column(Integer, ForeignKey("environments.id"), nullable=False)
    
    status = Column(String(20), default="pending")
    duration_ms = Column(Integer)
    
    request_url = Column(String(500))
    request_method = Column(String(10))
    request_headers = Column(JSON)
    request_body = Column(JSON)
    request_size = Column(Integer)

    response_status_code = Column(Integer)
    response_headers = Column(JSON)
    response_body = Column(JSON)
    response_size = Column(Integer)
    response_time_ms = Column(Integer)

    # 性能分析
    dns_time_ms = Column(Integer)
    tcp_time_ms = Column(Integer)
    tls_time_ms = Column(Integer)
    transfer_time_ms = Column(Integer)
    
    assertion_results = Column(JSON)
    error_message = Column(Text)
    
    # 关系定义
    script = relationship("ApiTestScript", foreign_keys=[script_id])
    endpoint = relationship("ApiEndpoint", foreign_keys=[endpoint_id])
    environment = relationship("Environment", foreign_keys=[environment_id])
    
    __table_args__ = (
        Index('ix_script_executions_project_id', 'project_id'),
        Index('ix_script_executions_script_id', 'script_id'),
        Index('ix_script_executions_endpoint_id', 'endpoint_id'),
        Index('ix_script_executions_environment_id', 'environment_id'),
    )