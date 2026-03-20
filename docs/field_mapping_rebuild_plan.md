# 字段映射内核重构实施方案

## 1. 目标

这份方案不是重复 `字段映射优化.md` 的理想化设计，而是基于当前仓库真实代码结构，给出一版可以按阶段执行的落地方案。

本次改造的总目标是：

1. 保留现有外部契约，避免前端、任务调度、历史数据一起重构。
2. 替换当前字段映射核心实现，消除路由层混算法、领域层反向依赖 API 层、阶段恢复语义错误的问题。
3. 用“真实工件”替代“统计摘要式 stage_results”。
4. 为后续接入运行时证据、历史反馈、AI 补全留出稳定扩展位。

最终方向：

- 保留表：`api_field_mappings`、`field_mapping_suggestions`、`field_mapping_traces`、`async_tasks`
- 保留路径：`/field-mappings/*`、`/async-tasks/{task_id}`
- 保留任务名：`app.celery.tasks.execute_field_mapping_task`
- 冻结并逐步下线：`backend/app/domains/data_mapping/*` 旧核心
- 新建：`backend/app/domains/field_mapping_engine/*`

## 2. 当前仓库约束

当前代码状态决定了这次改造不能直接“大爆炸替换”，必须走兼容式分阶段切换。

### 2.1 必须保留的兼容面

- 前端已经依赖 `backend/app/api/v1/field_mappings.py`
- 前端和任务工作台已经依赖 `backend/app/api/v1/field_mappings_async.py`
- Celery 已经注册 `app.celery.tasks.execute_field_mapping_task`
- `field_mapping_suggestions` 已经承担建议工作台的数据来源
- `field_mapping_traces` 已经承担审计与排错数据来源

### 2.2 当前实现中的关键问题

- `backend/app/domains/data_mapping/processor.py` 直接依赖 `app.api.v1.field_mappings`
- `backend/app/api/v1/field_mappings.py` 同时承担路由、字段提取、候选召回、AI fallback
- `stage_results` 当前保存的是摘要统计，不是可恢复的运行工件
- `field_mappings_async.py` 已经围绕旧阶段模型构建了查询、描述、重试接口
- `field_mapping_tasks.py` 直接实例化旧 `FieldMappingProcessor`
- `_common.py` 对结果结构有较强假设，目前只适配 `result["suggestions"]`

### 2.3 已有可复用基础

- `backend/app/platform/db/base.py` 中已有建议表、trace 表、任务表
- `backend/app/domains/data_impact/*` 已有运行时影响分析相关实现
- `api_execution_traces`、`sql_traces`、`api_table_impacts` 已存在
- `backend/app/utils/field_mapping_utils.py` 可拆出最基础的 normalize/tokenize 能力
- `backend/app/domains/data_mapping/constants.py`、`exceptions.py` 中有少量可迁移常量和异常定义

## 3. 实施原则

### 3.1 先并行，后切换

先建新内核，再让 API 和 Celery 逐步改为调用新 service。不要先删旧实现再补新实现。

### 3.2 路由只做控制层

`field_mappings.py` 和 `field_mappings_async.py` 最终都只做：

- 参数校验
- 上下文解析
- service 调用
- 响应封装

### 3.3 阶段结果必须可恢复

所有支持 resume 的阶段，必须存真实工件，不能只存摘要统计。

### 3.4 先做无 AI 版本

第一阶段新引擎先只做规则与证据链路，让结构先稳定；AI 只能作为后置补全层。

### 3.5 双跑验证后再切流

新旧引擎必须有一段并行对比窗口，不能直接全量替换默认执行路径。

## 4. 目标目录结构

第一阶段不要求一次把所有模块都补齐，但目录要按最终职责分层建立。

```text
backend/app/domains/field_mapping_engine/
    __init__.py
    contracts.py
    services.py
    extractor/
        api_schema_extractor.py
        db_schema_extractor.py
        runtime_evidence_extractor.py
    recall/
        lexical_recaller.py
        history_recaller.py
        runtime_recaller.py
    ranking/
        deterministic_rules.py
        ranker.py
    persistence/
        artifact_store.py
        suggestion_writer.py
        trace_writer.py
    orchestration/
        job_runner.py
        resume_manager.py
```

## 5. 分阶段实施计划

---

## Phase 0：冻结旧核心，建立兼容边界

### 目标

停止继续向旧 `data_mapping` 内核加功能，为新引擎切入建立清晰边界。

### 需要做的改造

#### 代码改造

- 在 `backend/app/domains/data_mapping/processor.py` 顶部注释中明确标记为 legacy implementation
- 在 `backend/app/api/v1/field_mappings.py` 中标出“仅保留兼容路径，后续逻辑迁入 service”
- 在 `backend/app/api/v1/field_mappings_async.py` 中标出“阶段语义以新引擎为准，旧阶段仅兼容展示”
- 盘点所有直接 import `FieldMappingProcessor` 的地方，限制新增调用

#### 测试改造

- 给现有回归测试分层
- 保留“兼容性测试”用于保障旧接口不回归
- 新增“新引擎测试目录”用于承接后续测试迁移

### 本阶段交付物

- 旧核心冻结说明
- 新引擎实施文档
- 兼容边界清单

### 验证标准

- 没有新增业务逻辑继续堆到 `processor.py`
- 团队对“旧核心只修阻断型 bug”的原则达成一致

---

## Phase 1：搭建新引擎骨架与应用服务层

### 目标

把“路由/任务入口”和“映射内核”解耦，先建立新的 service 层与引擎骨架。

### 需要做的改造

#### 新增目录与文件

- 新建 `backend/app/domains/field_mapping_engine/__init__.py`
- 新建 `backend/app/domains/field_mapping_engine/contracts.py`
- 新建 `backend/app/domains/field_mapping_engine/services.py`
- 新建 `backend/app/domains/field_mapping_engine/orchestration/job_runner.py`
- 新建 `backend/app/domains/field_mapping_engine/persistence/suggestion_writer.py`
- 新建 `backend/app/domains/field_mapping_engine/persistence/trace_writer.py`

#### contract 设计

在 `contracts.py` 定义最小稳定输入输出对象：

- `ApiFieldSpec`
- `ApiDefinitionContext`
- `DbColumnSpec`
- `RuntimeEvidence`
- `CandidateEvidence`
- `DecisionArtifact`
- `StageArtifactEnvelope`

要求：

- 不依赖 FastAPI/Pydantic 路由 DTO
- 允许被 Celery、CLI、离线任务复用

#### service 设计

在 `services.py` 定义两个应用服务：

- `FieldMappingAppService`
- `FieldMappingJobService`

职责如下：

- `FieldMappingAppService` 负责同步 suggest、批量 apply、结果查询编排
- `FieldMappingJobService` 负责创建任务、读取任务参数、驱动 job runner

#### 入口替换准备

- `backend/app/api/v1/field_mappings.py` 先不删旧逻辑，但新增 service 调用入口
- `backend/app/api/v1/field_mappings_async.py` 先不删旧逻辑，但把创建任务逻辑逐步改成走 `FieldMappingJobService`
- `backend/app/celery/tasks/field_mapping_tasks.py` 预留切换位，允许 runner 注入

### 本阶段交付物

- 新引擎空骨架
- 应用服务层
- 新旧入口边界定义

### 验证标准

- 新增的引擎模块不依赖 `app.api.v1.field_mappings`
- 能从 API 层调用到新 service，但不改变现有响应结构

---

## Phase 2：实现无 AI 的最小可用新引擎

### 目标

先让新引擎在不依赖 AI 的情况下完成“提取 -> 召回 -> 规则裁决 -> 落库”闭环。

### 需要做的改造

#### 提取层

新增：

- `extractor/api_schema_extractor.py`
- `extractor/db_schema_extractor.py`

要做的事情：

- 从 `ApiDefinition` 中提取 path/query/body 字段
- 统一字段路径格式
- 提取字段描述、method、path、definition_id、兄弟字段上下文
- 从 `DbSchemaVersion.schema_snapshot` 中拍平表/列/注释/类型

#### 召回层

新增：

- `recall/lexical_recaller.py`
- `recall/history_recaller.py`

要做的事情：

- 把 `field_mapping_utils.py` 中基础 normalize/tokenize 能力迁到 lexical recall
- 基于 `api_field_mappings` 增加历史 confirmed mapping recall
- 先不接向量检索，保证最小链路先跑通

#### 排序层

新增：

- `ranking/deterministic_rules.py`
- `ranking/ranker.py`

要做的事情：

- 定义新的候选特征结构，而不是复用旧 `score`
- 先实现确定性规则
- 再实现简化版 ranker

第一版建议最少支持这些 feature：

- `f_name_exact`
- `f_name_token_overlap`
- `f_comment_similarity`
- `f_history_prior`
- `f_type_compatibility`

#### 持久化层

新增：

- `persistence/suggestion_writer.py`
- `persistence/trace_writer.py`

要做的事情：

- 把 `_common.py` 中“保存建议”的逻辑迁出为新 writer
- 统一接收 `DecisionArtifact[]`
- 统一落 `field_mapping_suggestions`
- 统一落 `field_mapping_traces`

#### 入口接入

- `field_mapping_tasks.py` 增加开关，允许 task 走新 `JobRunner`
- `field_mappings.py` 新增一个内部调用路径，允许同步 suggest 走新 `FieldMappingAppService`

### 本阶段交付物

- 无 AI 新引擎 MVP
- 规则候选生成与落库闭环

### 验证标准

- 新引擎可针对一批 `ApiDefinition` 生成建议
- 结果能写入 `field_mapping_suggestions`
- 结果能写入 `field_mapping_traces`
- 不依赖 `FieldMappingProcessor`

---

## Phase 3：重建阶段模型与断点恢复

### 目标

彻底替换旧 `stage_results` 语义，使 resume/retry 基于真实工件而不是统计摘要。

### 需要做的改造

#### 数据库改造

新增表：

- `field_mapping_stage_artifacts`

建议字段：

- `id`
- `task_id`
- `stage`
- `artifact_type`
- `artifact_key`
- `payload_json`
- `created_at`

#### 持久化改造

新增：

- `persistence/artifact_store.py`
- `orchestration/resume_manager.py`

要做的事情：

- 每个阶段结束时写真实工件
- `async_tasks.stage_results` 只保留摘要和展示信息
- 真正 resume 时从 `field_mapping_stage_artifacts` 恢复工件

#### 新阶段定义

建议改成 6 个执行阶段：

1. 输入快照
2. 字段提取
3. 候选召回
4. 证据构造与排序
5. 最终裁决
6. 持久化结果

说明：

- AI 补全暂不纳入本阶段，避免新恢复模型再和 AI 耦合
- `field_mappings_async.py` 对旧的 1-5 展示阶段做兼容映射

#### 异步接口改造

修改 `backend/app/api/v1/field_mappings_async.py`：

- `get_async_task` 的阶段描述改为读取新阶段摘要
- `resume`/`retry` 逻辑改为走 `ResumeManager`
- `get stage result` 改为返回真实工件摘要，而不是旧统计结构

### 本阶段交付物

- 新阶段工件表
- 新 resume/retry 机制
- 新旧阶段展示兼容

### 验证标准

- 任务在阶段 2/3/4 中断后可恢复
- 恢复后不会把统计摘要误当运行对象
- `field_mappings_async.py` 页面接口仍可正常展示任务进度

---

## Phase 4：接入向量召回与运行时证据

### 目标

把新引擎从“规则可用”提升为“效果可用”。

### 需要做的改造

#### 向量召回

新增：

- `recall/vector_recaller.py`

要做的事情：

- 复用 `app.platform.vector.vector_index` 能力
- 向量召回只负责 recall，不直接拍板 final score
- 输出召回来源和原始相似度，供 ranker 使用

#### 运行时证据提取

新增：

- `extractor/runtime_evidence_extractor.py`
- `recall/runtime_recaller.py`

要做的事情：

- 从 `api_execution_traces`、`sql_traces`、`api_table_impacts` 提取 API 到表的运行时证据
- 如果可能，进一步把表级命中映射到列级候选
- 把 runtime hit 作为高优先级 feature，而不是日志附件

#### 排序器增强

扩展 `ranker.py` 支持更多特征：

- `f_vector_similarity`
- `f_runtime_table_hit`
- `f_runtime_column_hit`
- `f_table_domain_match`
- `f_graph_distance`

#### trace 增强

调整 `trace_writer.py`：

- 不再只记录 `s_vector/s_exact/s_graph`
- 允许写扩展 evidence 字段到 `decision_trace`
- 现有 `field_mapping_traces` 继续保留最关键的结构化字段

### 本阶段交付物

- 向量召回接入
- 运行时证据接入
- 新版排序特征体系

### 验证标准

- 新引擎能输出“候选来自何种证据”
- 能识别 API 与运行时命中的重点表
- 相比无 runtime 版本，结果相关性有可观提升

---

## Phase 5：接入 AI 补全与 guardrail

### 目标

把 AI 从“现有主干依赖”降级成“受约束的补全层”。

### 需要做的改造

#### 新增模块

- `ai/candidate_expander.py`
- `ai/ai_guardrail.py`

#### AI 接入方式

AI 只做两件事：

- 扩充低置信度字段的补充候选
- 生成更可读的解释文本

AI 不允许做的事情：

- 直接输出最终映射并跳过 ranker
- 绕过 schema existence check
- 绕过 domain/runtime/history 约束

#### 代码迁移

- 从 `processor.py` 中迁移 AI prompt 组装和 JSON 解析逻辑
- 将 hallucination 检查和 domain penalty 改造成独立 guardrail
- 旧 `_priority_ai_calling` 仅保留在兼容层，不再作为主链路

#### 持久化改造

在 `decision_trace` 中新增：

- `ai_used`
- `ai_candidates`
- `guardrail_rejections`
- `decision_source`

### 本阶段交付物

- AI 补全层
- guardrail 机制
- 新版 decision trace

### 验证标准

- AI 关闭时新引擎仍可用
- AI 打开时只能扩展候选，不破坏最终裁决链路
- 幻觉候选会被 guardrail 拦截

---

## Phase 6：任务入口、同步接口、工作台全面切换

### 目标

在保留外部契约的前提下，把默认执行流切到新引擎。

### 需要做的改造

#### Celery 切换

修改 `backend/app/celery/tasks/field_mapping_tasks.py`：

- 默认使用新 `JobRunner`
- 旧 `FieldMappingProcessor` 只保留为 fallback 或临时开关

#### 路由切换

修改 `backend/app/api/v1/field_mappings.py`：

- `/field-mappings/suggest` 走 `FieldMappingAppService`
- 保留请求响应结构
- 删除内部算法 helper 的对外暴露

修改 `backend/app/api/v1/field_mappings_async.py`：

- 创建任务、任务详情、重试、回放统一改为基于新 runner/new artifacts

#### `_common.py` 收口

修改 `backend/app/celery/tasks/_common.py`：

- 不再假设 `result["suggestions"]` 为旧结构
- 改成复用新 `suggestion_writer.py`

#### 前端兼容验证

重点验证：

- 任务创建
- 任务轮询
- 建议列表查询
- 批量 apply
- 自动应用高置信度建议

### 本阶段交付物

- 默认流量切换到新引擎
- 旧入口仅保留兼容壳

### 验证标准

- 前端页面无路径变更
- 异步任务全流程可跑通
- 建议结果与任务详情均可查询

---

## Phase 7：双跑、验收、下线旧核心

### 目标

在真实数据上验证新引擎优于旧实现，再清理遗留代码。

### 需要做的改造

#### 双跑机制

为部分任务增加 shadow run 能力：

- 主结果使用旧引擎或新引擎
- 旁路同时跑另一套引擎
- 对比 top1、top3、自动确认准确率、人工驳回率、trace 完整性

#### 验收指标

至少统计：

- top1 命中率
- top3 覆盖率
- 自动确认准确率
- 被人工 reject 的比例
- 无候选比例
- hallucination 拦截率

#### 旧代码清理

在确认切换稳定后：

- 删除 `backend/app/domains/data_mapping/scoring.py`
- 删除 `backend/app/domains/data_mapping/validation.py`
- 删除 `backend/app/domains/data_mapping/domain_inferer.py`
- 删除 `backend/app/domains/data_mapping/graph_builder.py`
- 缩减 `backend/app/domains/data_mapping/processor.py` 为兼容壳，最终再删除
- 清理 `field_mappings.py` 中不再使用的 helper

### 本阶段交付物

- 双跑报告
- 切流报告
- 旧核心下线清单

### 验证标准

- 新引擎在核心指标上稳定不差于旧引擎
- 线上兼容接口无回归
- 旧核心已不再承担默认执行流

## 6. 数据库改造清单

### 必增

- `field_mapping_stage_artifacts`

### 建议新增

- `field_mapping_feedback`
- `field_mapping_runtime_evidence`

### 保持不动

- `api_field_mappings`
- `field_mapping_suggestions`
- `field_mapping_traces`
- `async_tasks`

## 7. 文件级改造映射

### 保留路径，重写内部实现

- `backend/app/api/v1/field_mappings.py`
- `backend/app/api/v1/field_mappings_async.py`
- `backend/app/celery/tasks/field_mapping_tasks.py`
- `backend/app/celery/tasks/_common.py`

### 冻结后逐步下线

- `backend/app/domains/data_mapping/processor.py`
- `backend/app/domains/data_mapping/scoring.py`
- `backend/app/domains/data_mapping/validation.py`
- `backend/app/domains/data_mapping/domain_inferer.py`
- `backend/app/domains/data_mapping/graph_builder.py`

### 可拆分迁移

- `backend/app/utils/field_mapping_utils.py`
- `backend/app/domains/data_mapping/constants.py`
- `backend/app/domains/data_mapping/exceptions.py`
- `backend/app/domains/data_impact/schema_mapper.py`

## 8. 推荐执行顺序

如果按实际交付节奏排优先级，建议顺序如下：

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 6 的入口切换准备
6. Phase 4
7. Phase 5
8. Phase 6 正式切换
9. Phase 7

原因：

- 先做 MVP 和恢复模型，先解决结构性错误
- 再接效果增强项
- 最后做 AI 和全面切流

## 9. 第一批建议直接开工的任务

如果要开始编码，建议第一批任务只做下面这些：

1. 新建 `backend/app/domains/field_mapping_engine/` 骨架
2. 定义 `contracts.py` 和 `services.py`
3. 把 `field_mapping_tasks.py` 改成通过 service/runner 调度
4. 把 `_common.py` 中建议落库逻辑迁移到 writer
5. 在新引擎里实现无 AI 的 extractor + lexical/history recall + ranker
6. 新增 `field_mapping_stage_artifacts` 表和 `artifact_store.py`

这 6 项做完，仓库就从“旧巨型处理器继续堆逻辑”切换到了“新内核可持续迭代”的轨道上。

## 10. 当前进展

截至本轮改造，Phase 1、Phase 2、Phase 3 已经完成到“可运行 MVP”状态。

### 已落地内容

- 已新增 `backend/app/domains/field_mapping_engine/` 骨架
- 已新增 contracts、service、runner 分层
- 同步 `suggest` 已切到新 `FieldMappingAppService`
- 异步 `field_mapping_suggest` 任务默认已切到 `engine_v2`
- 已新增 `field_mapping_stage_artifacts` 表模型、迁移脚本、`ArtifactStore`、`ResumeManager`
- `engine_v2` 已支持真实工件落库
- `get stage result` / `retry` / `resume` / `reset` 已对 `engine_v2` 做工件模型分流

### 真实验证结果

本地已执行真实数据库验证，不是 mock。

#### 已执行动作

- 执行迁移：
  `python backend/migrations/add_field_mapping_stage_artifacts_table.py`
- 使用真实数据库中的 `project_id=1`、`version_id=1`
- 选取真实 `ApiDefinition`
- 创建真实 `AsyncTask`
- 直接走 `backend/app/celery/tasks/field_mapping_tasks.py` 的任务包装层执行 `engine_v2`

#### 验证结果

- `field_mapping_stage_artifacts` 表创建成功
- `engine_v2` 任务执行成功
- `AsyncTask.status = completed`
- `AsyncTask.result` 已保存
- `field_mapping_suggestions` 已成功落表
- `field_mapping_stage_artifacts` 已成功落表
- `task.stages` 已正确持久化为完成态

一次真实验证中的关键结果如下：

- 任务状态：`completed`
- 建议落表数量：`18`
- 工件落表数量：`5`
- 第一条建议存在且候选数正常

### 在真实验证中发现并已修复的问题

- `field_mapping_tasks.py` 未显式导入 `_save_suggestions_to_db`
  现象：任务被降级为 `partial_success`
  处理：已补导入，恢复建议落表

- `job_runner.py` 中直接原地修改 `task.stages`
  现象：SQLAlchemy JSON 字段状态未正确持久化
  处理：改为重新赋值列表后提交

- `field_mappings_async.py` 在演进过程中曾误把阶段工件查询逻辑插入 `get_async_task`
  现象：出现未定义变量 `stage_num` 风险
  处理：已清理误插代码，并恢复 `get_async_task` 正常逻辑

### 当前仍存在的缺口

- `engine_v2` 目前仍是“无 AI”版本
- 断点恢复目前是“基于真实工件的最小恢复模型”，还不是完整的可中断重算平台
- `_common.py` 里的建议落库仍是旧结构适配逻辑，后续应迁到独立 writer
- 还没有做运行时证据接入
- 还没有做向量召回接入
- 还没有做新旧引擎双跑对比

### 当前结论

当前仓库已经具备进入 Phase 4 的条件。

可以开始做：

- 向量召回接入
- 运行时证据接入
- 排序特征扩展
- 新版 trace/evidence 结构增强

## 11. 最新进展补充（Phase 4 / Phase 5）

截至 2026-03-20，Phase 4 与 Phase 5 已经进入“代码已接通，并完成定向真实验证”的状态。

### 11.1 Phase 4 已完成内容

- 已新增 `backend/app/domains/field_mapping_engine/recall/vector_recaller.py`
- 已新增 `backend/app/domains/field_mapping_engine/recall/runtime_recaller.py`
- `backend/app/domains/field_mapping_engine/services.py` 已接入 lexical / vector / runtime 三路候选合并
- `backend/app/domains/field_mapping_engine/ranking/ranker.py` 已扩展 `f_vector_similarity`、`f_runtime_table_hit`、`f_runtime_field_hit`
- `engine_v2` 的建议结果已能在 `decision_trace` 中标记 `engine_v2_phase4`

### 11.2 Phase 4 真实验证结论

本地真实数据库验证已完成，结论如下：

- `api_table_impacts` 已可作为运行时 prior 接入新引擎
- 真实任务执行后，候选结果中已出现 `runtime_table` / `runtime` / `vector` recall source
- 真实任务建议中已能看到：
  - `f_runtime_table_hit`
  - `f_runtime_field_hit`
  - `f_vector_similarity`
- 在真实 `ApiDefinition=2586` 的验证中，`body.code -> common_projectcode.code` 已可由 Phase 4 链路稳定命中

同时，在 Phase 4 验证过程中还修复了一个影响本地离线向量效果的问题：

- `backend/app/platform/vector/vector_index.py`
  - `_fallback_encode()` 的分词正则写法有误
  - 修复后，本地无网环境下的 fallback 向量召回不再出现大面积 `0.0 / 1.0` 异常分数

### 11.3 Phase 5 已完成内容

- 已新增 `backend/app/domains/field_mapping_engine/ai/enricher.py`
- 已新增 `backend/app/domains/field_mapping_engine/ai/__init__.py`
- `backend/app/domains/field_mapping_engine/services.py` 已拆成：
  - `rank_recall_items(...)`
  - `optimize_ranked_items(...)`
  - `build_suggestions_from_ranked_items(...)`
- AI 现在只会对低置信度字段触发，触发条件为：
  - `top rule score < ai_confidence_threshold`
- AI 与规则结果采用“同台竞技”策略：
  - AI 更强：`decision_source = ai`
  - AI 更弱：`decision_source = fallback`
  - 未触发 AI：`decision_source = rule`
- `backend/app/domains/field_mapping_engine/orchestration/job_runner.py`
  已将 Stage 4 从固定 `skipped` 改为真实落工件：
  - `artifact_type = ai_ranked_items`
- 同步接口 `backend/app/api/v1/field_mappings.py`
  已接回：
  - `use_ai_fallback`
  - `ai_confidence_threshold`
- 异步接口 `backend/app/api/v1/field_mappings_async.py`
  已补齐：
  - `ai_confidence_threshold`
  - 并透传到 `task_params`

### 11.4 Phase 5 测试与真实验证

已新增 / 更新测试：

- `backend/tests/test_field_mapping_engine_phase5.py`
- `backend/tests/test_field_mapping_async_engine_v2.py`

已执行回归：

- `pytest backend/tests/test_field_mapping_engine_phase5.py backend/tests/test_field_mapping_async_engine_v2.py -q`
- 结果通过

已完成一条真实数据库上的 Phase 5 端到端验证，方式为：

- 使用真实 `AsyncTask`
- 使用真实 `engine_v2`
- 使用真实 `field_mapping_suggestions` / `field_mapping_stage_artifacts`
- 在执行期临时 mock `AIService.execute(...)` 返回确定性候选

验证结果：

- 任务完成：`status = completed`
- Stage 4 工件已落库：`artifact_type = ai_ranked_items`
- `decision_trace.engine_version = engine_v2_phase5`
- `decision_trace.decision_source = ai`
- 最终候选中已出现：
  - `ai_selected = true`
  - `ai_reason`
  - `f_ai_confidence`
- 任务统计中已出现：
  - `ai_enhanced = 1`

说明：

- 当前已验证的是“真实数据库 + 真实任务链路 + 可控 AI 返回”的 Phase 5 执行路径
- 还没有对真实外部大模型调用做稳定性验收，这部分应放到后续联调阶段完成

### 11.5 当前状态判断

截至当前，仓库状态应更新为：

- Phase 1：完成
- Phase 2：完成
- Phase 3：完成
- Phase 4：完成
- Phase 5：完成（最小可用版）

下一阶段应进入 Phase 6：默认入口、任务工作台、同步 / 异步接口的全面切换与清理。
