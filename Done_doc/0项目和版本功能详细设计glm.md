
  📋 详细功能设计方案

  0.1 项目管理 (Project Profile)

  前端页面设计

   ┌─────────────────────────────────────────────────────────────────────┐
   │  项目管理                                    [+ 创建项目] [刷新]     │
   ├─────────────────────────────────────────────────────────────────────┤
   │  搜索: [____________] 状态: [全部▼] 排序: [创建时间▼]              │
   ├─────────────────────────────────────────────────────────────────────┤
   │  ┌───────────────────────────────────────────────────────────────┐ │
   │  │ 项目名称        │ 业务领域  │ 版本数 │ 状态  │ 操作      │ │
   │  ├───────────────────────────────────────────────────────────────┤ │
   │  │ BugSeek        │ SaaS      │ 3      │ 激活  │ [详情] [归档]│ │
   │  │ 电商系统       │ 电商      │ 5      │ 激活  │ [详情] [归档]│ │
   │  │ 支付平台       │ 金融      │ 2      │ 归档  │ [详情] [激活]│ │
   │  └───────────────────────────────────────────────────────────────┘ │
   └─────────────────────────────────────────────────────────────────────┘
                       [上一页] 1 / 5 [下一页]

  项目详情弹窗设计

   ┌─────────────────────────────────────────────────────────────────────┐
   │  项目详情                                           [×]              │
   ├─────────────────────────────────────────────────────────────────────┤
   │  基本信息                                                                │
   │  ┌─────────────────────────────────────────────────────────────┐ │
   │  │ 项目名称: BugSeek                                              │ │
   │  │ 项目描述: AI驱动的质量测试平台                                   │ │
   │  │ 业务领域: SaaS                                                 │
   │  │ 创建时间: 2024-01-22                                          │ │
   │  └─────────────────────────────────────────────────────────────┘ │
   │                                                                         │
   │  技术栈画像 [编辑]                                                     │
   │  ┌─────────────────────────────────────────────────────────────┐ │
   │  │ 后端语言: Python                                               │ │
   │  │ 后端框架: Django + FastAPI                                    │ │
   │  │ 数据库: PostgreSQL                                            │ │
   │  │ 前端框架: React + Ant Design                                   │ │
   │  └─────────────────────────────────────────────────────────────┘ │
   │                                                                         │
   │  全局知识库 [上传]                                                    │
   │  ┌─────────────────────────────────────────────────────────────┐ │
   │  │ 📄 数据字典.xlsx    [下载] [删除]                              │ │
   │  │ 📐 架构图.png        [预览] [删除]                              │ │
   │  │ 📝 错误码定义.md    [下载] [删除]                              │ │
   │  └─────────────────────────────────────────────────────────────┘ │
   │                                                                         │
   │                                    [取消]  [保存]                       │
   └─────────────────────────────────────────────────────────────────────┘

  数据模型设计

   class Project(Base, TimestampMixin):
       """项目表"""
       __tablename__ = "projects"

       id = Column(Integer, primary_key=True, index=True)
       name = Column(String(255), nullable=False)
       description = Column(Text, nullable=True)
       business_domain = Column(String(50), nullable=False)  # 电商/金融/SaaS/社交
       logo_url = Column(String(500), nullable=True)

       # 技术栈画像
       backend_language = Column(String(50))  # Java/Python/Go/Node
       backend_framework = Column(String(100))  # Spring Boot/Django/Gin
       database = Column(String(50))  # MySQL/PgSQL/Mongo
       frontend_framework = Column(String(100))  # Vue/React

       # 审计字段
       created_by = Column(Integer, nullable=True)  # 预留：创建者 UID
       owner_id = Column(Integer, nullable=True)  # 预留：所有者 UID
       is_deleted = Column(Boolean, default=False)  # 软删除标记

       __table_args__ = (
           Index('ix_projects_business_domain', 'business_domain'),
           Index('ix_projects_created_by', 'created_by'),
       )

  后端 API 设计


  ┌────────┬───────────────────────────┬────────────────┬──────┐
  │ 方法   │ 路径                      │ 功能           │ 状态 │
  ├────────┼───────────────────────────┼────────────────┼──────┤
  │ POST   │ /projects                 │ 创建项目       │ ❌   │
  │ GET    │ /projects                 │ 获取项目列表   │ ❌   │
  │ GET    │ /projects/{id}            │ 获取项目详情   │ ❌   │
  │ PUT    │ /projects/{id}            │ 更新项目       │ ❌   │
  │ DELETE │ /projects/{id}            │ 归档/删除项目  │ ❌   │
  │ POST   │ /projects/{id}/tech-stack │ 更新技术栈画像 │ ❌   │
  │ POST   │ /projects/{id}/knowledge  │ 上传知识库文件 │ ❌   │
  └────────┴───────────────────────────┴────────────────┴──────┘

  ---

  0.2 版本迭代管理 (Version Control)

  前端页面设计

   ┌─────────────────────────────────────────────────────────────────────┐
   │  版本管理 - BugSeek                                [+ 新建版本] [刷新] │
   ├─────────────────────────────────────────────────────────────────────┤
   │  版本列表                                                                │
   │  ┌───────────────────────────────────────────────────────────────┐ │
   │  │ 版本号   │ 状态    │ 父版本  │ 接口数 │ 用例数 │ 操作      │ │
   │  ├───────────────────────────────────────────────────────────────┤ │
   │  │ V1.2.0  │ 测试中  │ V1.1.0 │ 644   │ 128   │ [详情] [锁定]│ │
   │  │ V1.1.0  │ 已发布  │ V1.0.0 │ 580   │ 115   │ [详情] [锁定]│ │
   │  │ V1.0.0  │ 已发布  │ -      │ 520   │ 100   │ [详情] [锁定]│ │
   │  └─────────────────────────────────────────────────────────────┘ │
   └─────────────────────────────────────────────────────────────────────┘

  新建版本弹窗设计

   ┌─────────────────────────────────────────────────────────────────────┐
   │  新建版本                                           [×]              │
   ├─────────────────────────────────────────────────────────────────────┤
   │                                                                         │
   │  版本号: [V1.2.0____________]                                        │
   │                                                                         │
   │  父版本: [V1.1.0 ▼]                                                   │
   │                                                                         │
   │  继承策略:                                                              │
   │  ☑ 继承接口定义                                                        │
   │  ☑ 继承测试用例                                                        │
   │  ☑ 继承环境配置                                                        │
   │                                                                         │
   │  ┌─────────────────────────────────────────────────────────────┐     │
   │  │ 版本需求规约                                             │     │
   │  │ ┌─────────────────────────────────────────────────────┐ │     │
   │  │ │ 变更摘要:                                             │ │     │
   │  │ │ [新增用户管理模块，优化订单查询性能...]            │ │     │
   │  │ │                                                       │ │     │
   │  │ │ 需求文档: [上传文档] [一键结构化]                     │ │     │
   │  │ │                                                       │ │     │
   │  │ │ 重点测试范围: [x] 用户管理 [x] 订单查询 [ ] 支付      │ │     │
   │  │ └─────────────────────────────────────────────────────┘ │     │
   │  └─────────────────────────────────────────────────────────────┘     │
   │                                                                         │
   │                                    [取消]  [创建]                       │
   └─────────────────────────────────────────────────────────────────────┘

  数据模型设计

   class Version(Base, TimestampMixin):
       """版本表"""
       __tablename__ = "versions"

       id = Column(Integer, primary_key=True, index=True)
       project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
       version_number = Column(String(50), nullable=False)  # V1.2.0
       parent_version_id = Column(Integer, ForeignKey("versions.id"), nullable=True)

       # 状态: planning(规划中) -> developing(开发中) -> testing(测试中) ->
   released(已发布) -> locked(已锁定)
       status = Column(String(20), default="planning")

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

  后端 API 设计


  ┌────────┬─────────────────────────────────────────────┬──────────────┬──────┐
  │ 方法   │ 路径                                        │ 功能         │ 状态 │
  ├────────┼─────────────────────────────────────────────┼──────────────┼──────┤
  │ POST   │ /projects/{project_id}/versions             │ 新建版本     │ ❌   │
  │ GET    │ /projects/{project_id}/versions             │ 获取版本列表 │ ❌   │
  │ GET    │ /projects/{project_id}/versions/{id}        │ 获取版本详情 │ ❌   │
  │ PUT    │ /projects/{project_id}/versions/{id}        │ 更新版本     │ ❌   │
  │ DELETE │ /projects/{project_id}/versions/{id}        │ 删除版本     │ ❌   │
  │ POST   │ /projects/{project_id}/versions/{id}/lock   │ 锁定版本     │ ❌   │
  │ POST   │ /projects/{project_id}/versions/{id}/unlock │ 解锁版本     │ ❌   │
  │ POST   │ /projects/{project_id}/versions/{id}/clone  │ 克隆版本     │ ❌   │
  └────────┴─────────────────────────────────────────────┴──────────────┴──────┘

  ---

  0.3 环境与变量管理 (Env & Config)

  前端页面设计

   ┌─────────────────────────────────────────────────────────────────────┐
   │  环境管理 - BugSeek                                [+ 新建环境] [刷新] │
   ├─────────────────────────────────────────────────────────────────────┤
   │  环境列表                                                                │
   │  ┌───────────────────────────────────────────────────────────────┐ │
   │  │ 环境名称 │ 基础URL              │ 变量数 │ 操作              │ │
   │  ├───────────────────────────────────────────────────────────────┤ │
   │  │ Dev      │ http://dev.api.com     │ 5     │ [编辑] [删除]     │ │
   │  │ Test     │ http://test.api.com    │ 5     │ [编辑] [删除]     │
   │  │ Prod     │ https://api.bugseek.com│ 5     │ [编辑] [删除]     │
   │  └───────────────────────────────────────────────────────────────┘ │
   └─────────────────────────────────────────────────────────────────────┘

  环境详情弹窗设计

   ┌─────────────────────────────────────────────────────────────────────┐
   │  环境详情 - Dev                                    [×]              │
   ├─────────────────────────────────────────────────────────────────────┤
   │  基本信息                                                                │
   │  ┌─────────────────────────────────────────────────────────────┐ │
   │  │ 环境名称: Dev                                                   │ │
   │  │ 基础URL: [http://dev.api.com____________]                       │ │
   │  │ [测试连接]                                                       │ │
   │  └─────────────────────────────────────────────────────────────┘ │
   │                                                                         │
   │  全局变量池 [+ 添加变量]                                            │
   │  ┌─────────────────────────────────────────────────────────────┐ │
   │  │ 变量Key      │ Dev值                │ Test值   │ 敏感 │ 操作   │ │
   │  ├─────────────────────────────────────────────────────────────┤ │
   │  │ token        │ dev_token_123        │ ***      │ ✓    │ [编辑] │ │
   │  │ db_host      │ 192.168.1.1         │ ***      │ ✓    │ [编辑] │ │
   │  │ api_key      │ dev_key_abc          │ ***      │ ✓    │ [编辑] │ │
   │  └─────────────────────────────────────────────────────────────┘ │
   │                                                                         │
   │  数据库连接 [+ 添加数据库]                                          │
   │  ┌─────────────────────────────────────────────────────────────┐ │
   │  │ 别名    │ 连接字符串                    │ 状态   │ 操作   │
   │  ├─────────────────────────────────────────────────────────────┤
   │  │ main    │ postgresql://...            │ ✓      │ [测试] │
   │  │ report  │ postgresql://...            │ ✗      │ [测试] │
   │  └─────────────────────────────────────────────────────────────┘ │
   │                                                                         │
   │                                    [取消]  [保存]                       │
   └─────────────────────────────────────────────────────────────────────┘

  数据模型设计

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
       environment_id = Column(Integer, ForeignKey("environments.id"), nullable=False
   )
       var_key = Column(String(100), nullable=False)
       var_value = Column(Text, nullable=True)
       is_sensitive = Column(Boolean, default=False)  # 敏感标记

       __table_args__ = (
           Index('ix_global_vars_project_id', 'project_id'),
           Index('ix_global_vars_environment_id', 'environment_id'),
           UniqueConstraint('project_id', 'environment_id', 'var_key', name=
   'uq_project_env_var'),
       )


   class DatabaseConfig(Base, TimestampMixin):
       """数据库连接配置表"""
       __tablename__ "database_configs"

       id = Column(Integer, primary_key=True, index=True)
       project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
       alias = Column(String(50), nullable=False)
       connection_string = Column(Text, nullable=True)  # 加密存储
       db_type = Column(String(20), nullable=False)  # MySQL/PgSQL/Mongo

       __table_args__ = (
           Index('ix_database_configs_project_id', 'project_id'),
           UniqueConstraint('project_id', 'alias', name='uq_project_alias'),
       )

  后端 API 设计


  ┌───────┬──────────────────────────────────────────────────┬──────────────┬─────┐
  │ 方法  │ 路径                                             │ 功能         │ 状态 │
  ├───────┼──────────────────────────────────────────────────┼──────────────┼─────┤
  │ POST  │ /projects/{project_id}/environments              │ 新建环境     │ ❌  │
  │ GET   │ /projects/{project_id}/environments              │ 获取环境列表 │ ❌  │
  │ GET   │ /projects/{project_id}/environments/{id}         │ 获取环境详情 │ ❌  │
  │ PUT   │ /projects/{project_id}/environments/{id}         │ 更新环境     │ ❌  │
  │ DE... │ /projects/{project_id}/environments/{id}         │ 删除环境     │ ❌  │
  │ POST  │ /projects/{project_id}/environments/{id}/vars    │ 添加变量     │ ❌  │
  │ PUT   │ `/projects/{project_id}/environments/{id}/var... │ 更新变量     │ ❌  │
  │ DE... │ `/projects/{project_id}/environments/{id}/var... │ 删除变量     │ ❌  │
  │ POST  │ /projects/{project_id}/database-configs          │ 添加数据...  │ ❌  │
  │ POST  │ `/projects/{project_id}/database-configs/{id}... │ 测试数据...  │ ❌  │
  └───────┴──────────────────────────────────────────────────┴──────────────┴─────┘

  ---

  0.4 可拓展性预留

  数据模型预留字段

   # Project 表预留字段
   class Project(Base, TimestampMixin):
       # ... 现有字段 ...
       created_by = Column(Integer, nullable=True)  # 创建者 UID
       owner_id = Column(Integer, nullable=True)  # 所有者 UID
       is_deleted = Column(Boolean, default=False)  # 软删除标记

   # Version 表预留字段
   class Version(Base, TimestampMixin):
       # ... 现有字段 ...
       notification_url = Column(String(500), nullable=True)  # WebHook

   # 所有核心表审计字段
   class AuditMixin:
       """审计混入类"""
       created_at = Column(DateTime, default=datetime.now(timezone.utc))
       updated_at = Column(DateTime, default=datetime.now(timezone.utc),
   onupdate=datetime.now(timezone.utc))
       is_deleted = Column(Boolean, default=False)

  ---

  🔄 核心流程设计

  1. 新建版本流程（资产继承）

   用户创建 V1.2.0
       ↓
   选择父版本 V1.1.0
       ↓
   选择继承策略
       ├─ 继承接口定义 → 深拷贝 api_endpoints 到 V1.2.0
       ├─ 继承测试用例 → 深拷贝 test_cases 到 V1.2.0
       └─ 继承环境配置 → 深拷贝 environments 到 V1.2.0
       ↓
   输入需求规约
       ├─ 变更摘要
       ├─ 需求文档
       └─ 测试范围
       ↓
   创建版本记录
       ↓
   返回版本 ID

  2. 版本状态流转流程

   规划中 (planning)
       ↓ 创建版本
   开发中 (developing)
       ↓ 提交测试
   测试中 (testing)
       ↓ 测试通过
   已发布 (released)
       ↓ 锁定版本
   已锁定 (locked) ← 数据只读

  3. 变量替换流程

   用户选择 Dev 环境运行测试
       ↓
   获取 Dev 环境的所有变量
       ↓
   替换测试脚本中的变量占位符
       ├─ {{token}} → dev_token_123
       ├─ {{db_host}} → 192.168.1.1
       └─ {{api_key}} → dev_key_abc
       ↓
   执行测试

  ---

  📊 数据库表关系图

   projects (1)
   ├── versions (N)
   │   ├── api_documents (N) ←─── document_id (无外键)
   │   ├── test_cases (N)
   │   └── requirements (N)
   ├── environments (N)
   │   └── global_vars (N)
   ├── global_vars (N)
   └── database_configs (N)

   versions (1)
   ├── parent_version_id → versions (自关联)
   └── api_documents (N)

  ---

  🎯 与现有代码的整合方案

  现有代码调整

   1. ApiDocument 表调整
      - 添加 project_id 字段
      - 添加 version_id 字段
      - 移除 is_latest 和 parent_id 字段（版本管理由 Version 表统一管理）

   2. ApiEndpoint 表调整
      - 添加 project_id 字段
      - 添加 version_id 字段
      - 移除 document_id 外键约束（已解耦）

   3. 新增表
      - projects - 项目表
      - versions - 版本表
      - environments - 环境表
      - global_vars - 全局变量表
      - database_configs - 数据库配置表

  ---

  📝 待实现功能清单


  ┌─────┬──────────────────────────┬────────┬────────┐
  │ ID  │ 功能                     │ 优先级 │ 工作量 │
  ├─────┼──────────────────────────┼────────┼────────┤
  │ P1  │ 创建项目表和版本表       │ P0     │ 2h     │
  │ P2  │ 创建环境管理和变量管理表 │ P0     │ 2h     │
  │ P3  │ 实现项目 CRUD 接口       │ P0     │ 3h     │
  │ P4  │ 实现版本管理接口         │ P0     │ 4h     │
  │ P5  │ 实现版本继承逻辑         │ P0     │ 4h     │
  │ P6  │ 实现环境管理接口         │ P1     │ 3h     │
  │ P7  │ 实现变量管理接口         │ P1     │ 2h     │
  │ P8  │ 实现版本状态流转         │ P1     │ 2h     │
  │ P9  │ 前端项目管理页面         │ P0     │ 4h     │
  │ P10 │ 前端版本管理页面         │ P0     │ 4h     │
  │ P11 │ 前端环境管理页面         │ P1     │ 3h     │
  │ P12 │ 前端新建版本弹窗         │ P0     │ 3h     │
  │ P13 │ AI 预处理助手功能        │ P2     │ 4h     │
  └─────┴──────────────────────────┴────────┴────────┘

  ---

✦ 总计: 13 项功能，预计工作量：32 小时