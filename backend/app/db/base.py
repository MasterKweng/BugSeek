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
    is_deleted = Column(Boolean, default=False)  # 软删除标记

    # 关系定义
    group = relationship("ApiEndpointGroup", foreign_keys=[group_id])

    __table_args__ = (
        Index('ix_api_endpoints_project_id', 'project_id'),
        Index('ix_api_endpoints_document_id', 'document_id'),
        Index('ix_api_endpoints_path_method', 'path', 'method'),
        Index('ix_api_endpoints_group_id', 'group_id'),
        Index('ix_api_endpoints_is_deleted', 'is_deleted'),
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

    # 模块分析状态
    analysis_status = Column(String(20), default="pending")  # pending | analyzing | completed

    # 模块的输入/输出接口（用于模块间依赖分析）
    input_endpoints = Column(JSON, nullable=True)  # [endpoint_id, ...]
    output_endpoints = Column(JSON, nullable=True)  # [endpoint_id, ...]

    # 模块内的业务链路
    internal_chains = Column(JSON, nullable=True)  # [[endpoint_id, ...], ...]

    # 关系定义
    endpoints = relationship("ApiEndpoint", back_populates="group")

    __table_args__ = (
        Index('ix_api_endpoint_groups_project_id', 'project_id'),
        Index('ix_api_endpoint_groups_analysis_status', 'analysis_status'),
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


class TestExecution(Base, TimestampMixin):
    """统一测试执行记录表（支持单接口、场景、套件）"""
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
    """测试执行结果明细表"""
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
    error_message = Column(Text)

    # 关系定义
    execution = relationship("TestExecution", foreign_keys=[execution_id])

    __table_args__ = (
        Index('ix_test_execution_results_execution_id', 'execution_id'),
        Index('ix_test_execution_results_target_type', 'target_type'),
        Index('ix_test_execution_results_target_id', 'target_id'),
        Index('ix_test_execution_results_status', 'status'),
    )


class ApiDependency(Base, TimestampMixin):
    """接口依赖关系表"""
    __tablename__ = "api_dependencies"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # 依赖关系
    source_endpoint_id = Column(Integer, ForeignKey("api_endpoints.id"), nullable=False)
    target_endpoint_id = Column(Integer, ForeignKey("api_endpoints.id"), nullable=False)
    
    # 映射规则：如何从源接口的响应提取数据，传递到目标接口的请求
    # 示例：{"source_path": "data.order_id", "target_path": "order_id"}
    mapping_rule = Column(JSON, nullable=True)
    
    # 依赖类型
    dependency_type = Column(String(20), nullable=False)  # direct | indirect | reference
    
    # 依赖强度（0-1）：用于计算业务链路的完整性
    dependency_strength = Column(Float, default=1.0)
    
    # 发现方式
    discovery_method = Column(String(50))  # ai_analysis | manual | schema_inference
    
    # 关系定义
    source_endpoint = relationship("ApiEndpoint", foreign_keys=[source_endpoint_id])
    target_endpoint = relationship("ApiEndpoint", foreign_keys=[target_endpoint_id])
    
    __table_args__ = (
        Index('ix_api_dependencies_project_id', 'project_id'),
        Index('ix_api_dependencies_source_endpoint_id', 'source_endpoint_id'),
        Index('ix_api_dependencies_target_endpoint_id', 'target_endpoint_id'),
        Index('ix_api_dependencies_dependency_type', 'dependency_type'),
        UniqueConstraint('source_endpoint_id', 'target_endpoint_id', name='uq_source_target'),
    )


class ApiScenario(Base, TimestampMixin):
    """业务场景表"""
    __tablename__ = "api_scenarios"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # 场景基本信息
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # 场景类型
    scenario_type = Column(String(50), nullable=False)  # business_flow | test_chain | regression
    category = Column(String(50))  # 订单流程 | 用户注册 | 支付流程
    
    # 涉及的接口（按执行顺序）
    endpoint_ids = Column(JSON, nullable=False)  # [1, 5, 9]
    
    # 执行顺序（包含变量传递规则）
    execution_order = Column(JSON, nullable=False)
    # 示例：
    # [
    #   {
    #     "step": 1,
    #     "endpoint_id": 1,
    #     "name": "创建订单",
    #     "variables": {},
    #     "extract": {"order_id": "data.id"}
    #   },
    #   {
    #     "step": 2,
    #     "endpoint_id": 5,
    #     "name": "查询订单",
    #     "variables": {"order_id": "{{step1.order_id}}"},
    #     "depends_on": [1]
    #   }
    # ]
    
    # 场景级变量
    variables = Column(JSON, nullable=True)  # 场景初始化变量
    
    # 场景配置
    timeout = Column(Integer, default=300)  # 超时时间（秒）
    retry_count = Column(Integer, default=0)  # 失败重试次数
    continue_on_failure = Column(Boolean, default=False)  # 失败后是否继续执行
    
    # 统计信息
    endpoint_count = Column(Integer, default=0)
    
    # 状态
    status = Column(String(20), default="active")  # active | archived
    
    # 关系定义
    endpoints = relationship("ApiEndpoint", secondary="scenario_endpoints", backref="scenarios")
    
    __table_args__ = (
        Index('ix_api_scenarios_project_id', 'project_id'),
        Index('ix_api_scenarios_scenario_type', 'scenario_type'),
        Index('ix_api_scenarios_category', 'category'),
        Index('ix_api_scenarios_status', 'status'),
    )


class ScenarioEndpoint(Base, TimestampMixin):
    """场景与接口的关联表"""
    __tablename__ = "scenario_endpoints"
    
    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("api_scenarios.id"), nullable=False)
    endpoint_id = Column(Integer, ForeignKey("api_endpoints.id"), nullable=False)
    step_order = Column(Integer, nullable=False)  # 执行步骤顺序
    
    # 关系定义
    scenario = relationship("ApiScenario", foreign_keys=[scenario_id])
    endpoint = relationship("ApiEndpoint", foreign_keys=[endpoint_id])
    
    __table_args__ = (
        Index('ix_scenario_endpoints_scenario_id', 'scenario_id'),
        Index('ix_scenario_endpoints_endpoint_id', 'endpoint_id'),
        Index('ix_scenario_endpoints_step_order', 'step_order'),
        UniqueConstraint('scenario_id', 'endpoint_id', name='uq_scenario_endpoint'),
    )


class AsyncTask(Base, TimestampMixin):
    """异步任务表"""
    __tablename__ = "async_tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("api_endpoint_groups.id"), nullable=True)  # 分组ID

    # 任务类型
    task_type = Column(String(50), nullable=False, index=True)  # dependency_analysis | code_generation

    # 任务状态
    status = Column(String(20), default="pending", index=True)  # pending | running | completed | failed | cancelled

    # 任务参数
    task_params = Column(JSON, nullable=True)

    # 任务结果
    task_result = Column(JSON, nullable=True)

    # 进度信息
    progress = Column(Integer, default=0)  # 0-100
    progress_message = Column(Text, nullable=True)

    # 错误信息
    error_message = Column(Text, nullable=True)

    # Celery 任务ID
    celery_task_id = Column(String(255), nullable=True, index=True)

    # 任务优先级
    priority = Column(Integer, default=5)  # 0-10，数字越小优先级越高

    # 重试次数
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # 时间信息
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    estimated_duration = Column(Integer, nullable=True)  # 预计耗时（秒）

    # 关系定义
    project = relationship("Project", foreign_keys=[project_id])
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index('ix_async_tasks_project_id', 'project_id'),
        Index('ix_async_tasks_user_id', 'user_id'),
        Index('ix_async_tasks_group_id', 'group_id'),
        Index('ix_async_tasks_task_type', 'task_type'),
        Index('ix_async_tasks_status', 'status'),
        Index('ix_async_tasks_celery_task_id', 'celery_task_id'),
    )


class GroupDependency(Base, TimestampMixin):
    """分组依赖关系表"""
    __tablename__ = "group_dependencies"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # 分组间的依赖
    source_group_id = Column(Integer, ForeignKey("api_endpoint_groups.id"), nullable=False)
    target_group_id = Column(Integer, ForeignKey("api_endpoint_groups.id"), nullable=False)

    # 依赖强度
    dependency_strength = Column(Float, default=1.0)

    # 依赖类型
    dependency_type = Column(String(20), nullable=False)  # direct | indirect | reference

    # 映射规则
    mapping_rule = Column(JSON, nullable=True)

    # 关系定义
    source_group = relationship("ApiEndpointGroup", foreign_keys=[source_group_id])
    target_group = relationship("ApiEndpointGroup", foreign_keys=[target_group_id])

    __table_args__ = (
        Index('ix_group_dependencies_project_id', 'project_id'),
        Index('ix_group_dependencies_source_group_id', 'source_group_id'),
        Index('ix_group_dependencies_target_group_id', 'target_group_id'),
        UniqueConstraint('source_group_id', 'target_group_id', name='uq_group_source_target'),
    )


class ApiModuleDependency(Base, TimestampMixin):
    """模块依赖关系表"""
    __tablename__ = "api_module_dependencies"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # 依赖关系（模块级）
    source_group_id = Column(Integer, ForeignKey("api_endpoint_groups.id"), nullable=False)
    target_group_id = Column(Integer, ForeignKey("api_endpoint_groups.id"), nullable=False)

    # 跨模块接口映射
    # 哪些接口输出数据，哪些接口接收数据
    endpoint_mappings = Column(JSON, nullable=False, default=list)
    # 示例：
    # {
    #   "outputs": [
    #     {"endpoint_id": 1, "fields": ["user_id", "order_id"]}
    #   ],
    #   "inputs": [
    #     {"endpoint_id": 5, "fields": ["user_id"]}
    #   ]
    # }

    # 依赖强度
    dependency_strength = Column(Float, default=1.0)

    # 关系定义
    source_group = relationship("ApiEndpointGroup", foreign_keys=[source_group_id])
    target_group = relationship("ApiEndpointGroup", foreign_keys=[target_group_id])

    __table_args__ = (
        Index('ix_api_module_dependencies_project_id', 'project_id'),
        Index('ix_api_module_dependencies_source_group_id', 'source_group_id'),
        Index('ix_api_module_dependencies_target_group_id', 'target_group_id'),
        UniqueConstraint('source_group_id', 'target_group_id', name='uq_module_source_target'),
    )


class ApiModuleChain(Base, TimestampMixin):
    """模块业务链路表"""
    __tablename__ = "api_module_chains"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # 链路信息
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # 涉及的模块（按执行顺序）
    group_ids = Column(JSON, nullable=False, default=list)

    # 链路结构（嵌套的执行顺序）
    # 每个模块内部有自己的执行顺序，模块间有数据传递
    chain_structure = Column(JSON, nullable=False, default=list)
    # 示例：
    # [
    #   {
    #     "step": 1,
    #     "group_id": 1,
    #     "group_name": "用户模块",
    #     "internal_chain": [endpoint_1, endpoint_2],  # 模块内链路
    #     "output_fields": {"user_id": "step1.endpoint_1.data.id"},
    #     "next_group_id": 3
    #   },
    #   {
    #     "step": 2,
    #     "group_id": 3,
    #     "group_name": "订单模块",
    #     "internal_chain": [endpoint_5, endpoint_6],
    #     "input_fields": {"user_id": "{{step1.user_id}}"},
    #     "next_group_id": 5
    #   }
    # ]

    # 统计信息
    endpoint_count = Column(Integer, default=0)
    group_count = Column(Integer, default=0)

    # 状态
    status = Column(String(20), default="active")  # active | archived

    __table_args__ = (
        Index('ix_api_module_chains_project_id', 'project_id'),
        Index('ix_api_module_chains_status', 'status'),
    )
# ==================== 链路管理相关模型 ====================

class ApiInternalChain(Base, TimestampMixin):
    """内部链路表"""
    __tablename__ = "api_internal_chains"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("api_endpoint_groups.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # 基本信息
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # 链路数据
    endpoint_ids = Column(JSON, nullable=False, default=list)
    execution_order = Column(JSON, nullable=False, default=list)
    
    # 链路元数据
    chain_type = Column(String(50), default="business")
    complexity_score = Column(Integer, default=1)
    estimated_duration = Column(Integer, nullable=True)
    
    # 生成标记
    auto_generated = Column(Boolean, default=True)
    analysis_version = Column(String(50), nullable=True)
    
    # 状态
    status = Column(String(20), default="active")
    
    # 统计信息
    endpoint_count = Column(Integer, default=0)
    dependency_count = Column(Integer, default=0)
    
    # 关联
    related_scenario_id = Column(Integer, ForeignKey("api_scenarios.id", ondelete="SET NULL"), nullable=True)
    
    # 关系定义
    group = relationship("ApiEndpointGroup", backref="internal_chains_list")
    project = relationship("Project", backref="internal_chains")
    related_scenario = relationship("ApiScenario", foreign_keys=[related_scenario_id])
    
    __table_args__ = (
        UniqueConstraint('group_id', 'name', name='uq_internal_chain'),
        Index('ix_api_internal_chains_group_id', 'group_id'),
        Index('ix_api_internal_chains_project_id', 'project_id'),
        Index('ix_api_internal_chains_status', 'status'),
        Index('ix_api_internal_chains_auto_generated', 'auto_generated'),
    )


class ApiChainScenario(Base, TimestampMixin):
    """链路与场景关联表"""
    __tablename__ = "api_chain_scenarios"

    id = Column(Integer, primary_key=True, index=True)
    chain_id = Column(Integer, nullable=False)
    chain_type = Column(String(20), nullable=False)  # internal | cross-module
    scenario_id = Column(Integer, ForeignKey("api_scenarios.id", ondelete="CASCADE"), nullable=False)
    
    # 关联信息
    is_primary = Column(Boolean, default=True)
    mapping_config = Column(JSON, nullable=True)
    
    # 关系定义
    scenario = relationship("ApiScenario", backref="chain_associations")
    
    __table_args__ = (
        UniqueConstraint('chain_id', 'chain_type', 'scenario_id', name='uq_chain_scenario'),
        Index('ix_api_chain_scenarios_chain_id', 'chain_id', 'chain_type'),
        Index('ix_api_chain_scenarios_scenario_id', 'scenario_id'),
    )
