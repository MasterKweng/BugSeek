# 观测与日志规范文档

**BSK-SC-034: 观测与日志规范补齐**

## 文档概述

本文档定义了 BugSeek 平台的统一日志字段规范，确保每次执行都具备完整的可观测性标识，便于问题追踪、性能分析和系统监控。

## 核心原则

1. **全链路追踪**: 每个请求/执行都有唯一的 trace_id
2. **结构化日志**: 使用结构化字段，便于日志分析和查询
3. **上下文关联**: 日志中包含业务上下文（scenario_id、node_key 等）
4. **分级记录**: 根据日志级别合理记录信息
5. **性能敏感**: 避免过度日志影响性能

## 核心标识字段

### 1. TraceID（追踪标识）

**定义**: 全局唯一的追踪标识，用于关联整个执行链路

**格式**: 32 位十六进制字符串（UUID 去除横线）

**示例**: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

**使用场景**:
- 用户请求从进入系统到响应完成的全过程
- 场景执行的完整生命周期
- 异步任务的执行链路
- 跨服务的调用链

**实现**:
```python
from app.core.trace import get_trace_id, set_trace_id

# 获取当前 trace_id
trace_id = get_trace_id()

# 设置新的 trace_id（通常在请求入口）
set_trace_id(new_trace_id)
```

**日志格式**: `[trace_id]` 或 `trace_id=xxx`

### 2. ScenarioID（场景标识）

**定义**: 场景的唯一标识

**格式**: 整数

**示例**: `123`

**使用场景**:
- 场景执行的开始和结束
- 场景级别的日志记录
- 场景性能指标

**实现**:
```python
logger.info(
    f"[{trace_id}] 场景执行开始: scenario_id={scenario_id}, "
    f"scenario_name={scenario.name}, environment_id={environment_id}"
)
```

**日志格式**: `scenario_id=xxx`

### 3. NodeKey（节点标识）

**定义**: 场景节点的唯一标识

**格式**: 字符串（通常由用户定义）

**示例**: `create_user`, `get_user_info`, `validate_order`

**使用场景**:
- 节点级别的日志记录
- 节点执行状态变化
- 节点间的依赖关系

**实现**:
```python
logger.info(
    f"[{trace_id}] 节点执行开始: scenario_id={scenario_id}, "
    f"node_key={node_key}, node_name={node_name}"
)
```

**日志格式**: `node_key=xxx`

### 4. ExecutionID（执行标识）

**定义**: 场景单次执行的唯一标识

**格式**: 整数

**示例**: `456789`

**使用场景**:
- 单次场景执行的记录
- 执行结果的关联
- 执行历史的查询

**实现**:
```python
logger.info(
    f"[{trace_id}] 场景执行记录已创建: execution_id={execution_id}, "
    f"scenario_id={scenario_id}"
)
```

**日志格式**: `execution_id=xxx`

### 5. ProjectID（项目标识）

**定义**: 项目的唯一标识

**格式**: 整数

**示例**: `1`

**使用场景**:
- 项目级别的资源访问
- 项目隔离和权限控制
- 项目级别的统计分析

**实现**:
```python
logger.info(
    f"[{trace_id}] API 调用: project_id={project_id}, "
    f"endpoint={endpoint_path}"
)
```

**日志格式**: `project_id=xxx`

### 6. UserID（用户标识）

**定义**: 用户的唯一标识

**格式**: 整数

**示例**: `1001`

**使用场景**:
- 用户操作审计
- 用户行为分析
- 用户级别的资源访问

**实现**:
```python
logger.info(
    f"[{trace_id}] 用户登录: user_id={user_id}, "
    f"username={username}, ip_address={ip_address}"
)
```

**日志格式**: `user_id=xxx`

### 7. TaskID（任务标识）

**定义**: 异步任务的唯一标识

**格式**: 整数

**示例**: `789012`

**使用场景**:
- 异步任务的执行记录
- 任务状态的追踪
- 任务结果的通知

**实现**:
```python
logger.info(
    f"[{trace_id}] 异步任务创建: task_id={task_id}, "
    f"task_type={task_type}, status=pending"
)
```

**日志格式**: `task_id=xxx`

## 日志级别规范

### DEBUG

**用途**: 详细的调试信息，用于开发和问题诊断

**内容**:
- 变量的值
- 函数的参数
- 内部计算过程
- 数据结构的详细信息

**示例**:
```python
logger.debug(
    f"[{trace_id}] 场景图校验通过: scenario_id={scenario_id}, "
    f"nodes={len(nodes)}, levels={len(levels)}"
)
```

**使用频率**: 开发环境高频使用，生产环境谨慎使用

### INFO

**用途**: 关键的业务流程节点和系统状态信息

**内容**:
- 业务流程的开始和结束
- 重要状态的变化
- 关键操作的执行结果
- 系统启动和关闭

**示例**:
```python
logger.info(
    f"[{trace_id}] 场景执行开始: scenario_id={scenario_id}, "
    f"scenario_name={scenario.name}, total_nodes={total_nodes}"
)
```

**使用频率**: 生产环境的主要日志级别

### WARNING

**用途**: 潜在的问题和异常情况，但系统仍可继续运行

**内容**:
- 可恢复的错误
- 降级的处理
- 性能问题
- 配置警告

**示例**:
```python
logger.warning(
    f"[{trace_id}] 检测到孤立节点: scenario_id={scenario_id}, "
    f"isolated_nodes={isolated_nodes}"
)
```

**使用频率**: 需要关注但不需要立即处理的情况

### ERROR

**用途**: 错误和异常情况，影响功能但系统仍可运行

**内容**:
- 操作失败的错误
- 异常的堆栈信息
- 失败的原因和上下文

**示例**:
```python
logger.error(
    f"[{trace_id}] 场景执行失败: scenario_id={scenario_id}, "
    f"node_key={node_key}, error={str(e)}",
    exc_info=True
)
```

**使用频率**: 需要立即关注和处理的情况

### CRITICAL

**用途**: 严重错误，导致系统或关键功能无法运行

**内容**:
- 系统崩溃
- 关键服务不可用
- 数据丢失或损坏

**示例**:
```python
logger.critical(
    f"[{trace_id}] 数据库连接失败: error={str(e)}, "
    f"impact=所有场景执行不可用"
)
```

**使用频率**: 极少使用，需要立即处理

## 场景执行日志规范

### 场景生命周期

#### 1. 场景开始执行

```python
logger.info(
    f"[{trace_id}] 场景执行开始: "
    f"scenario_id={scenario_id}, "
    f"scenario_name={scenario.name}, "
    f"environment_id={environment_id}, "
    f"total_nodes={total_nodes}, "
    f"execution_mode={scenario.execution_mode}"
)
```

**必须包含字段**: `trace_id`, `scenario_id`, `environment_id`, `total_nodes`

#### 2. 场景执行完成

```python
logger.info(
    f"[{trace_id}] 场景执行完成: "
    f"scenario_id={scenario_id}, "
    f"execution_id={execution_id}, "
    f"status={status}, "
    f"passed_nodes={passed_nodes}, "
    f"failed_nodes={failed_nodes}, "
    f"skipped_nodes={skipped_nodes}, "
    f"total_duration_ms={total_duration_ms}"
)
```

**必须包含字段**: `trace_id`, `scenario_id`, `execution_id`, `status`, `passed_nodes`, `failed_nodes`, `total_duration_ms`

### 节点生命周期

#### 1. 节点开始执行

```python
logger.info(
    f"[{trace_id}] 节点执行开始: "
    f"scenario_id={scenario_id}, "
    f"execution_id={execution_id}, "
    f"node_key={node_key}, "
    f"node_name={node_name}, "
    f"node_type={node_type}"
)
```

**必须包含字段**: `trace_id`, `scenario_id`, `execution_id`, `node_key`, `node_type`

#### 2. 节点执行完成

```python
logger.info(
    f"[{trace_id}] 节点执行完成: "
    f"scenario_id={scenario_id}, "
    f"execution_id={execution_id}, "
    f"node_key={node_key}, "
    f"status={status}, "
    f"response_time_ms={response_time}, "
    f"response_code={response_code}"
)
```

**必须包含字段**: `trace_id`, `scenario_id`, `execution_id`, `node_key`, `status`, `response_time_ms`, `response_code`

#### 3. 节点执行失败

```python
logger.error(
    f"[{trace_id}] 节点执行失败: "
    f"scenario_id={scenario_id}, "
    f"execution_id={execution_id}, "
    f"node_key={node_key}, "
    f"error_type={type(e).__name__}, "
    f"error_message={str(e)}",
    exc_info=True
)
```

**必须包含字段**: `trace_id`, `scenario_id`, `execution_id`, `node_key`, `error_type`, `error_message`

### 变量传递日志

#### 1. 变量提取

```python
logger.debug(
    f"[{trace_id}] 变量提取: "
    f"scenario_id={scenario_id}, "
    f"execution_id={execution_id}, "
    f"node_key={node_key}, "
    f"extracted_vars={list(extracted_variables.keys())}"
)
```

#### 2. 变量注入

```python
logger.debug(
    f"[{trace_id}] 变量注入: "
    f"scenario_id={scenario_id}, "
    f"execution_id={execution_id}, "
    f"node_key={node_key}, "
    f"injected_vars={list(context['vars'].keys())}"
)
```

## API 请求日志规范

### 请求进入

```python
logger.info(
    f"[{trace_id}] API 请求: "
    f"method={request.method}, "
    f"path={request.url.path}, "
    f"user_id={user_id}, "
    f"project_id={project_id}, "
    f"client_ip={client_ip}"
)
```

### 响应返回

```python
logger.info(
    f"[{trace_id}] API 响应: "
    f"method={request.method}, "
    f"path={request.url.path}, "
    f"status_code={status_code}, "
    f"duration_ms={duration_ms}"
)
```

### 请求错误

```python
logger.error(
    f"[{trace_id}] API 错误: "
    f"method={request.method}, "
    f"path={request.url.path}, "
    f"status_code={status_code}, "
    f"error_message={error_message}"
)
```

## 异步任务日志规范

### 任务创建

```python
logger.info(
    f"[{trace_id}] 异步任务创建: "
    f"task_id={task_id}, "
    f"task_type={task_type}, "
    f"project_id={project_id}, "
    f"params={params}"
)
```

### 任务开始执行

```python
logger.info(
    f"[{trace_id}] 异步任务开始: "
    f"task_id={task_id}, "
    f"task_type={task_type}"
)
```

### 任务执行完成

```python
logger.info(
    f"[{trace_id}] 异步任务完成: "
    f"task_id={task_id}, "
    f"task_type={task_type}, "
    f"status={status}, "
    f"duration_ms={duration_ms}, "
    f"result_summary={result_summary}"
)
```

### 任务执行失败

```python
logger.error(
    f"[{trace_id}] 异步任务失败: "
    f"task_id={task_id}, "
    f"task_type={task_type}, "
    f"error_type={type(e).__name__}, "
    f"error_message={str(e)}",
    exc_info=True
)
```

## 性能日志规范

### API 响应时间

```python
# INFO: 正常响应 (< 1s)
# WARNING: 慢响应 (1s - 3s)
# ERROR: 超慢响应 (> 3s)

if duration_ms < 1000:
    logger.info(f"[{trace_id}] API 响应时间: {duration_ms}ms")
elif duration_ms < 3000:
    logger.warning(f"[{trace_id}] API 响应时间较慢: {duration_ms}ms")
else:
    logger.error(f"[{trace_id}] API 响应时间过慢: {duration_ms}ms")
```

### 数据库查询时间

```python
# INFO: 快速查询 (< 100ms)
# WARNING: 慢查询 (100ms - 1s)
# ERROR: 超慢查询 (> 1s)

if query_time_ms < 100:
    logger.debug(f"[{trace_id}] 数据库查询: {query_time_ms}ms")
elif query_time_ms < 1000:
    logger.warning(f"[{trace_id}] 数据库慢查询: {query_time_ms}ms, sql={sql}")
else:
    logger.error(f"[{trace_id}] 数据库超慢查询: {query_time_ms}ms, sql={sql}")
```

### 场景执行时间

```python
logger.info(
    f"[{trace_id}] 场景执行时间: "
    f"scenario_id={scenario_id}, "
    f"total_duration_ms={total_duration_ms}, "
    f"avg_node_duration_ms={total_duration_ms / total_nodes}"
)
```

## 安全日志规范

### 用户登录

```python
logger.info(
    f"[{trace_id}] 用户登录: "
    f"user_id={user_id}, "
    f"username={username}, "
    f"login_method={login_method}, "
    f"ip_address={ip_address}, "
    f"user_agent={user_agent}"
)
```

### 权限检查

```python
logger.warning(
    f"[{trace_id}] 权限拒绝: "
    f"user_id={user_id}, "
    f"resource_type={resource_type}, "
    f"resource_id={resource_id}, "
    f"action={action}, "
    f"reason={reason}"
)
```

### 敏感操作

```python
logger.info(
    f"[{trace_id}] 敏感操作: "
    f"user_id={user_id}, "
    f"operation={operation}, "
    f"resource_type={resource_type}, "
    f"resource_id={resource_id}"
)
```

## 日志格式规范

### 统一格式

```
%(asctime)s | %(levelname)s | [%(trace_id)s] | %(name)s | %(message)s
```

### 示例输出

```
2026-03-10 14:30:45 | INFO | [a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6] | app.core.test_execution | 场景执行开始: scenario_id=123, scenario_name=用户管理流程测试, environment_id=1, total_nodes=3
2026-03-10 14:30:45 | INFO | [a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6] | app.core.test_execution | 节点执行开始: scenario_id=123, execution_id=456789, node_key=create_user, node_name=创建用户, node_type=api_call
2026-03-10 14:30:46 | INFO | [a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6] | app.core.test_execution | 节点执行完成: scenario_id=123, execution_id=456789, node_key=create_user, status=passed, response_time_ms=120, response_code=201
2026-03-10 14:30:46 | INFO | [a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6] | app.core.test_execution | 场景执行完成: scenario_id=123, execution_id=456789, status=completed, passed_nodes=3, failed_nodes=0, skipped_nodes=0, total_duration_ms=450
```

## 日志文件组织

### 按级别分包

- `debug.log`: DEBUG 级别日志
- `info.log`: INFO 级别日志
- `warning.log`: WARNING 级别日志
- `error.log`: ERROR 级别日志

### 按模块分包

- `api.log`: API 请求日志
- `celery.log`: Celery 异步任务日志
- `database.log`: 数据库查询日志
- `scenario.log`: 场景相关日志
- `execution.log`: 测试执行日志
- `dependency.log`: 依赖分析日志

### 日志轮转

- **轮转周期**: 每天午夜（when='midnight'）
- **保留天数**: 30 天（backupCount=30）
- **编码**: UTF-8

## 日志查询规范

### 按追踪标识查询

```bash
# 查询特定 trace_id 的所有日志
grep "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6" logs/*.log
```

### 按场景查询

```bash
# 查询特定场景的所有日志
grep "scenario_id=123" logs/*.log
```

### 按执行查询

```bash
# 查询特定执行的所有日志
grep "execution_id=456789" logs/*.log
```

### 按错误查询

```bash
# 查询所有错误日志
grep "ERROR" logs/error.log
```

### 按时间查询

```bash
# 查询特定时间段的日志
grep "2026-03-10 14:" logs/*.log
```

## 日志分析工具

### 推荐工具

1. **ELK Stack** (Elasticsearch + Logstash + Kibana)
   - 强大的日志搜索和分析能力
   - 可视化仪表板
   - 实时监控和告警

2. **Grafana Loki**
   - 轻量级日志聚合系统
   - 与 Grafana 集成
   - 成本较低

3. **Splunk**
   - 企业级日志分析平台
   - 功能强大
   - 成本较高

4. **云服务**
   - AWS CloudWatch Logs
   - Azure Monitor Logs
   - Google Cloud Logging

### 自定义脚本

```python
import re
from pathlib import Path

def analyze_scenario_logs(log_dir: str, scenario_id: int):
    """分析场景执行日志"""
    trace_ids = set()
    node_results = {}
    
    for log_file in Path(log_dir).glob("*.log"):
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                # 提取 trace_id
                trace_id_match = re.search(r'\[([a-f0-9]{32})\]', line)
                if trace_id_match:
                    trace_ids.add(trace_id_match.group(1))
                
                # 提取节点结果
                node_match = re.search(r'node_key=(\w+),\s*status=(\w+)', line)
                if node_match:
                    node_key, status = node_match.groups()
                    if node_key not in node_results:
                        node_results[node_key] = []
                    node_results[node_key].append(status)
    
    return {
        'trace_ids': trace_ids,
        'node_results': node_results
    }
```

## 最佳实践

### 1. 日志级别选择

- **DEBUG**: 开发和调试时使用
- **INFO**: 正常业务流程
- **WARNING**: 可恢复的问题
- **ERROR**: 需要关注的错误
- **CRITICAL**: 严重错误

### 2. 日志内容

- **简洁明了**: 避免冗余信息
- **结构化**: 使用键值对格式
- **上下文完整**: 包含必要的标识字段
- **避免敏感信息**: 不记录密码、token 等

### 3. 性能考虑

- **异步日志**: 使用异步日志处理器
- **批量写入**: 避免频繁的磁盘 I/O
- **日志采样**: 高频日志使用采样策略
- **合理过滤**: 生产环境过滤 DEBUG 日志

### 4. 日志保留

- **定期清理**: 自动清理过期日志
- **分级保留**: 不同级别日志保留不同时间
- **归档策略**: 重要日志归档到长期存储
- **合规要求**: 满足审计和合规要求

## 监控和告警

### 关键指标

1. **错误率**: ERROR 和 CRITICAL 日志的数量
2. **响应时间**: API 响应时间的分布
3. **成功率**: 场景执行的成功率
4. **吞吐量**: 每秒处理的请求数

### 告警规则

1. **错误率告警**: ERROR 日志数量超过阈值
2. **响应时间告警**: API 响应时间超过阈值
3. **成功率告警**: 场景执行成功率低于阈值
4. **服务可用性告警**: 关键服务不可用

## 附录

### A. 日志字段快速参考

| 字段名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| trace_id | string | 是 | 全局追踪标识 |
| scenario_id | int | 场景相关 | 场景标识 |
| execution_id | int | 执行相关 | 执行标识 |
| node_key | string | 节点相关 | 节点标识 |
| project_id | int | 资源相关 | 项目标识 |
| user_id | int | 用户相关 | 用户标识 |
| task_id | int | 任务相关 | 任务标识 |
| status | string | 状态相关 | 状态值 |
| duration_ms | int | 性能相关 | 耗时（毫秒） |
| error_type | string | 错误相关 | 错误类型 |
| error_message | string | 错误相关 | 错误消息 |

### B. 日志示例集合

#### 场景执行完整流程

```python
# 场景开始
logger.info(f"[{trace_id}] 场景执行开始: scenario_id={scenario_id}, ...")

# 图校验
logger.debug(f"[{trace_id}] 场景图校验通过: scenario_id={scenario_id}, ...")

# 执行层级构建
logger.debug(f"[{trace_id}] 构建执行层级: scenario_id={scenario_id}, levels={len(levels)}")

# 节点执行
logger.info(f"[{trace_id}] 节点执行开始: scenario_id={scenario_id}, node_key={node_key}, ...")
logger.info(f"[{trace_id}] 节点执行完成: scenario_id={scenario_id}, node_key={node_key}, ...")

# 场景完成
logger.info(f"[{trace_id}] 场景执行完成: scenario_id={scenario_id}, ...")
```

#### API 请求完整流程

```python
# 请求进入
logger.info(f"[{trace_id}] API 请求: method={method}, path={path}, ...")

# 业务逻辑
logger.debug(f"[{trace_id}] 业务逻辑执行: ...")

# 响应返回
logger.info(f"[{trace_id}] API 响应: method={method}, path={path}, status_code={status_code}, ...")
```

---

**文档版本**: 1.0
**创建日期**: 2026-03-10
**最后更新**: 2026-03-10
**维护者**: Backend Team