• 以下是“只做规划、不改代码”的详细改造计划。
  目标是按你给的 0优化方案.md 落地，并且贴合当前代码现状。

  前置结论

  1. 你现在是“能力有积木，但主干断层”：CaseExecutor、字段映射、AI 网关、Celery 都有；场景主链路不完整。
  2. 先补“场景数据模型 + 场景执行引擎 + 场景API”，再接“意图工作台 + JIT映射”，最后做“CI/CD + 报告”。
  3. 当前存在两个需要先处理的断点：

  - change_detector 依赖 ApiScenario，但主模型里没有该类。
  - sync_tasks 里调用 execute_sync_task，但 Celery 任务文件里没有该任务实现。

  ———

  模块 0：基线收敛（先做）

  1. 目标：把“历史代码残留”和“主干代码”对齐，避免后续改造建立在不一致状态上。
  2. 改动范围：

  - 主模型文件： backend/app/db/base.py
  - 历史模型参考： backend/app/db/base_backup.py
  - 影响分析器： backend/app/core/sync/change_detector.py
  - 同步任务路由： backend/app/api/v1/sync_tasks.py
  - Celery任务： backend/app/celery/tasks.py

  3. 计划动作：

  - 明确“以哪个场景模型为准”（建议以 api_scenarios 体系为准，弃用零散旧命名）。
  - 修正 change_detector 依赖的模型可用性。
  - 校验 sync_tasks 的异步执行链是否完整（任务定义、路由调用、状态回写一致）。

  4. 验收：

  - 后端可正常启动。
  - 同步任务和字段映射任务都能走通基础流程。
  - change_detector 相关导入和调用不报错。

  ———

  模块 1：数据层（Scenario & Node）

  1. 目标：建立“场景”一等公民数据结构，不破坏现有 ApiCase。
  2. 改动范围：

  - 模型： backend/app/db/base.py
  - 迁移脚本目录： backend/migrations
  - 历史迁移参考： backend/migrations/add_scenario_tables.py

  3. 计划动作：

  - 新增/恢复 api_scenarios。
  - 设计 scenario_nodes（建议替代旧 scenario_endpoints，支持 DAG 节点语义）。
  - 节点字段建议包含：node_key、node_type(case/definition)、ref_id、depends_on[]、input_mapping、extract_rules、
    assertion_overrides、retry/timeout/continue_on_failure。
  - 场景字段建议包含：name、description、source_type(manual/intent)、context_init、execution_mode、status、versioning字
    段。
  - 保留 test_executions 作为统一执行主表，新增“节点级结果扩展表”或扩展 test_execution_results 承载 node_key。

  4. 验收：

  - 场景可落库、可查询、可更新。
  - 一个场景可表达串行与并行依赖。

  ———

  模块 2：场景执行引擎（Context Bus + DAG）

  1. 目标：把占位的 ScenarioExecutor 变成可生产执行器。
  2. 改动范围：

  - 执行器： backend/app/core/test_execution.py
  - 日志配置： backend/app/core/logging_config.py

  3. 计划动作：

  - 实现 DAG 校验：无环校验、孤立节点校验、依赖合法性校验。
  - 实现拓扑执行：按层执行，层内并发，跨层串行。
  - 实现 Context Bus：
  - 初始化 context = {}。
  - 每个节点执行后把 extracted_variables 写入 context（命名空间建议 node.<node_key>.* + 全局别名）。
  - 下游节点执行前做模板渲染（沿用现有变量替换机制并增强路径解析）。
  - 复用 CaseExecutor.execute_case 执行单节点，避免重复实现 HTTP/鉴权/断言逻辑。
  - 执行失败策略支持：fail_fast、continue_on_failure、节点级重试。

  4. 验收：

  - 3节点链路（A提取变量->B使用变量->C断言）可跑通。
  - 并行分支场景可执行并汇总结果。

  ———

  模块 3：场景 API（管理 + 执行）

  1. 目标：提供场景全生命周期接口。
  2. 改动范围：

  - 新增路由文件（建议）：backend/app/api/v1/scenarios.py
  - 路由注册： backend/app/api/v1/init.py
  - 依赖与上下文： backend/app/context.py

  3. 计划动作：

  - CRUD：创建、更新、列表、详情、归档。
  - 执行接口：POST /scenarios/{id}/execute
  - 执行记录接口：GET /scenarios/{id}/executions、GET /executions/{id}
  - 统一返回结构保持 {code,message,data}。
  - 全接口补齐 IDOR 校验（项目归属、版本归属）。

  4. 验收：

  - 前端可通过 API 完整管理场景并触发执行。
  - 执行记录可回放节点级细节。

  ———

  模块 4：意图工作台（Intent -> Scenario）

  1. 目标：把“自然语言意图”转成可执行场景。
  2. 改动范围：

  - AI网关： backend/app/ai/gateway.py
  - AI服务： backend/app/ai/service.py
  - Prompt： backend/app/ai/prompts.py
  - 向量检索： backend/app/utils/vector_index.py

  3. 计划动作：

  - 新增 intent_scenario_generation 任务类型。
  - 两阶段 LLM：
  - 阶段A：从意图抽取业务步骤。
  - 阶段B：基于候选 API 生成 DAG + 变量映射建议。
  - 接口资产检索：
  - 关键词/语义召回 API definition。
  - 结合 method/path/tags/summary 做重排。
  - 输出结构约束为可直接落库 api_scenarios + scenario_nodes 的 JSON。
  - 增加低置信度回退策略：要求用户确认缺失节点或映射。

  4. 验收：

  - 输入一句业务意图，返回可视化可执行草案。
  - 一次确认后能生成并执行场景。

  ———

  模块 5：字段映射改造为 JIT 场景内计算

  1. 目标：从“项目全量映射”切到“场景子集即时映射”。
  2. 改动范围：

  - 异步入口： backend/app/api/v1/field_mappings_async.py
  - 同步入口： backend/app/api/v1/field_mappings.py
  - 处理器： backend/app/field_mapping/processor.py
  - Celery任务： backend/app/celery/tasks.py

  2. 计划动作：

  - 给 field_mapping_suggest 新增 definition_ids 参数，限定处理范围。
  - 保留全量能力但降级为“高级入口/后台维护入口”。
  - 在“意图生成场景后”自动触发 JIT 映射任务。
  - 返回映射建议时标注“来源场景ID、节点ID、置信度、证据链（decision_trace）”。

  3. 验收：

  - 5个接口组成的场景，建议生成时间显著低于全量任务。
  - 建议质量可在 UI 一次性确认并固化。

  ———

  模块 6：前端信息架构与页面落地

  1. 目标：让新能力在前端可用且可操作。
  2. 改动范围：

  - 路由： frontend/src/App.tsx
  - 导航： frontend/src/components/MainLayout.tsx
  - 现有场景Store： frontend/src/store/scenario.ts
  - 场景类型： frontend/src/types/scenario.ts

  3. 计划动作：

  - 新增页面：
  - 意图工作台（输入意图、候选API、生成草案）。
  - 场景编排页（DAG可视化、节点配置、变量连线）。
  - 场景执行页（实时进度、节点状态、Trace）。
  - 场景报告页（摘要+详情+错误定位）。
  - 现有 scenario store 中 /api-integration/* 的旧接口契约需重映射到新后端路由。

  4. 验收：

  - 从“输入意图”到“执行场景”前端完整闭环。
  - 失败节点可定位并查看上下文变量。

  ———

  模块 7：前端字段映射页面联动场景

  1. 目标：让映射确认成为场景流程的一部分，而不是独立全局流程。
  2. 改动范围：

  - 映射页面： frontend/src/pages/FieldMappingSuggestions.tsx
  - 映射服务： frontend/src/services/fieldMapping.ts

  3. 计划动作：

  - 增加“按场景查看建议”模式（task 与 scenario 绑定）。
  - 提供连线视图（source field -> target field）。
  - 支持批量确认后直接回写场景节点 input mapping。
  - 默认入口从“全局生成建议”切到“场景生成后自动建议”。

  4. 验收：

  - 场景级建议可一键确认并立即执行场景。
  - 用户无需切换多个页面手动拼装。

  ———

  模块 8：CI/CD 集成（Webhook + CLI）

  1. 目标：外部流水线可触发场景并拿到结果。
  2. 改动范围：

  - 新增触发路由（建议）：backend/app/api/v1/execution_triggers.py
  - 执行记录复用： backend/app/db/base.py
  - 文档与脚本：backend/scripts（新增 CLI）

  3. 计划动作：

  - 提供统一触发接口：POST /api/v1/scenarios/{id}/trigger
  - 鉴权采用 API Key 或 Token（与现有 auth 体系兼容）。
  - 支持同步短轮询结果和异步回调两种模式。
  - 提供最小 CLI：传 base_url、token、scenario_id、environment_id，返回退出码用于流水线门禁。

  4. 验收：

  - Jenkins/GitLab/GitHub Actions 任一可用一行命令触发并判断成功失败。

  ———

  模块 9：场景级报告（Trace 聚合 + RCA）

  1. 目标：输出可交付的质量报告，而不是只看日志。
  2. 改动范围：

  - 执行结果数据源： backend/app/db/base.py
  - Trace能力： backend/app/core/trace.py
  - 报告生成服务（新增）：backend/app/core/reporting/*

  3. 计划动作：

  - 报告模型：摘要、节点级明细、断言统计、失败Top、耗时分布、变量链路。
  - 输出格式：HTML（首选），PDF（可选）。
  - RCA 生成：失败节点上下文 + 错误日志 + 断言差异，调用 LLM 生成根因建议。

  4. 验收：

  - 每次场景执行都可生成可访问报告链接。
  - 报告可回溯到节点、请求、响应、断言。

  ———

  模块 10：异步任务体系统一

  1. 目标：避免“本地 asyncio 队列”和“Celery 队列”双轨混乱。
  2. 改动范围：

  - 任务管理器： backend/app/core/async_task/manager.py
  - 执行器： backend/app/core/async_task/executor.py
  - Celery任务： backend/app/celery/tasks.py

  3. 计划动作：

  - 明确生产主通路统一走 Celery。
  - async_task.manager 保留为兼容层或彻底下线，避免状态源冲突。
  - 统一任务状态机：pending/running/completed/partial_success/failed/cancelled。

  4. 验收：

  - 同一任务不会出现双执行。
  - 前端轮询状态稳定一致。

  ———

  模块 11：测试与回归体系

  1. 目标：每个里程碑有可重复验证，避免边改边坏。
  2. 改动范围：

  - 后端测试目录： backend/tests
  - 前端关键页面测试（需补）：frontend/src/pages/*（新增）

  3. 计划动作：

  - 新增用例集：
  - 场景DAG执行正确性（串行/并行/失败重试）。
  - Context Bus 变量传递正确性。
  - 意图生成结构校验。
  - JIT映射范围正确性。
  - CI触发与报告生成链路。
  - 增加回归用例确保原有 api-cases 单用例执行不退化。

  4. 验收：

  - 自动化测试覆盖核心链路。
  - 关键接口有契约测试，前后端字段不漂移。

  ———

  模块 12：发布与迁移计划

  1. 目标：低风险上线，不影响现有用户流程。
  2. 计划动作：

  - 采用 feature flag：
  - scenario_v2_enabled
  - intent_workbench_enabled
  - jit_mapping_enabled
  - 分阶段上线：
  - 阶段1：仅内部可见（不开放入口）。
  - 阶段2：灰度项目开启。
  - 阶段3：全量开启并下线旧入口。
  - 数据迁移策略：
  - 旧链路数据按“可读兼容，不强迁移”处理。
  - 新建表从空跑，避免一次性高风险迁移。

  3. 验收：

  - 可回滚、可灰度、可观测。

  ———

  建议的实施顺序（与你文档一致但更工程化）

  1. Sprint 0（1周）：模块0 + 模块1（基线收敛 + 场景模型）。
  2. Sprint 1（1-2周）：模块2 + 模块3（执行引擎 + 场景API）。
  3. Sprint 2（1-2周）：模块4 + 模块5 + 模块7（意图工作台 + JIT映射 + 前端联动）。
  4. Sprint 3（1周）：模块8 + 模块9（CI触发 + 报告）。
  5. Sprint 4（持续）：模块10 + 模块11 + 模块12（统一异步、测试补齐、灰度上线）。

  ———