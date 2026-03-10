# 场景数据迁移兼容策略

## 背景

系统中存在多个历史迁移脚本，导致场景相关的表结构存在多个版本：

### 历史表结构

| 迁移脚本 | 表名 | 状态 |
|---------|------|------|
| `add_scenario_tables.py` | `api_dependencies` | 保留（依赖分析） |
| `add_scenario_tables.py` | `api_scenarios` | 已被 V1 替代 |
| `add_scenario_tables.py` | `scenario_endpoints` | 已废弃 |
| `add_chain_scenarios_table.py` | `api_chain_scenarios` | 保留（链路关联） |
| `add_scenario_v1_tables.py` | `api_scenarios` | **当前使用** |
| `add_scenario_v1_tables.py` | `scenario_nodes` | **当前使用** |

---

## 命名冲突分析

### 1. `api_scenarios` 表冲突

**问题**：
- 旧版本（`add_scenario_tables.py`）和 V1（`add_scenario_v1_tables.py`）都定义了 `api_scenarios` 表
- 字段定义不完全一致

**解决方案**：
- **以 `add_scenario_v1_tables.py` 为准**，重新定义表结构
- 使用 `DROP TABLE IF EXISTS api_scenarios CASCADE` 强制重建
- **数据丢失警告**：旧表数据会被清空，需要在重建前备份

### 2. 节点表命名变化

| 旧版本 | 新版本 | 变化 |
|--------|--------|------|
| `scenario_endpoints` | `scenario_nodes` | 语义升级：从"端点"改为"节点" |

**解决方案**：
- 废弃 `scenario_endpoints` 表
- 新数据全部写入 `scenario_nodes`
- 提供数据迁移脚本（如需要）

---

## 兼容策略

### 策略一：激进式迁移（推荐用于开发/测试环境）

**适用场景**：
- 开发/测试环境
- 无需保留历史数据
- 快速迭代

**步骤**：
1. 备份现有数据库
2. 执行以下 SQL：
```sql
-- 1. 删除旧表
DROP TABLE IF EXISTS scenario_endpoints CASCADE;
DROP TABLE IF EXISTS api_scenarios CASCADE;

-- 2. 删除旧链路关联表（如果不需要）
-- DROP TABLE IF EXISTS api_chain_scenarios CASCADE;

-- 3. 保留依赖分析表
-- DROP TABLE IF EXISTS api_dependencies CASCADE;

-- 4. 运行 V1 迁移脚本
-- 执行 add_scenario_v1_tables.py
```

3. 验证表结构：
```sql
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name IN ('api_scenarios', 'scenario_nodes')
ORDER BY table_name, ordinal_position;
```

### 策略二：渐进式迁移（推荐用于生产环境）

**适用场景**：
- 生产环境
- 需要保留历史数据
- 零停机迁移

**步骤**：

#### 阶段 1：创建 V1 表（不删除旧表）

```sql
-- 创建 V1 表（使用新表名避免冲突）
CREATE TABLE api_scenarios_v1 (
    -- 与 add_scenario_v1_tables.py 定义一致
    ...
);

CREATE TABLE scenario_nodes (
    -- 与 add_scenario_v1_tables.py 定义一致
    ...
);
```

#### 阶段 2：数据迁移

```sql
-- 迁移 api_scenarios 数据
INSERT INTO api_scenarios_v1 (
    id, project_id, version_id, name, description, 
    scenario_type, source_type, environment_id, 
    status, created_at, updated_at
)
SELECT 
    id, project_id, version_id, name, description,
    'business_flow', 'manual', environment_id,
    status, created_at, updated_at
FROM api_scenarios;

-- 迁移 scenario_endpoints 到 scenario_nodes
INSERT INTO scenario_nodes (
    id, scenario_id, node_key, node_name, node_type,
    ref_type, ref_id, step_order, created_at, updated_at
)
SELECT 
    id, scenario_id, 
    'node_' || id::text,  -- 生成 node_key
    endpoint_id::text,     -- 使用 endpoint_id 作为 node_name
    'api_call',
    'api_definition',      -- 假设旧版本都是 api_definition
    endpoint_id,
    execution_order,
    created_at, updated_at
FROM scenario_endpoints;
```

#### 阶段 3：重命名表（原子操作）

```sql
-- 在低峰期执行，时间窗口 < 1 秒
BEGIN;

-- 重命名旧表为备份
ALTER TABLE api_scenarios RENAME TO api_scenarios_backup_YYYYMMDD;
ALTER TABLE scenario_endpoints RENAME TO scenario_endpoints_backup_YYYYMMDD;

-- 重命名 V1 表为正式表
ALTER TABLE api_scenarios_v1 RENAME TO api_scenarios;

COMMIT;
```

#### 阶段 4：清理

```sql
-- 验证新表正常工作后，删除备份表（30天后）
DROP TABLE IF EXISTS api_scenarios_backup_YYYYMMDD CASCADE;
DROP TABLE IF EXISTS scenario_endpoints_backup_YYYYMMDD CASCADE;
```

---

## 字段映射关系

### `api_scenarios` 字段映射

| 旧字段 | 新字段 | 处理策略 |
|--------|--------|----------|
| `id` | `id` | 直接映射 |
| `project_id` | `project_id` | 直接映射 |
| `version_id` | `version_id` | 直接映射 |
| `name` | `name` | 直接映射 |
| `description` | `description` | 直接映射 |
| `status` | `status` | 直接映射 |
| - | `scenario_type` | 默认值：`'business_flow'` |
| - | `source_type` | 默认值：`'manual'` |
| - | `source_ref_id` | NULL |
| - | `environment_id` | 从旧表迁移 |
| - | `context_init` | NULL |
| - | `execution_mode` | 默认值：`'sequential'` |
| - | `timeout_seconds` | 默认值：600 |
| - | `retry_count` | 默认值：0 |
| - | `continue_on_failure` | 默认值：FALSE |
| `created_at` | `created_at` | 直接映射 |
| `updated_at` | `updated_at` | 直接映射 |
| - | `created_by` | NULL（需补充） |
| - | `updated_by` | NULL（需补充） |

### `scenario_endpoints` → `scenario_nodes` 字段映射

| 旧字段 | 新字段 | 处理策略 |
|--------|--------|----------|
| `id` | `id` | 直接映射 |
| `scenario_id` | `scenario_id` | 直接映射 |
| - | `node_key` | 生成：`'node_' || id::text` |
| - | `node_name` | 映射：`endpoint_id::text` |
| - | `node_type` | 默认值：`'api_call'` |
| - | `ref_type` | 默认值：`'api_definition'` |
| `endpoint_id` | `ref_id` | 直接映射 |
| `execution_order` | `step_order` | 直接映射 |
| - | `depends_on` | NULL |
| - | `input_mapping` | NULL |
| - | `extract_rules` | NULL |
| - | `assertion_overrides` | NULL |
| - | `timeout_seconds` | NULL |
| - | `retry_count` | 默认值：0 |
| - | `continue_on_failure` | 默认值：FALSE |
| - | `is_enabled` | 默认值：TRUE |
| - | `extra_config` | NULL |
| `created_at` | `created_at` | 直接映射 |
| `updated_at` | `updated_at` | 直接映射 |

---

## 保留表说明

### 1. `api_dependencies` 表

**用途**：接口依赖分析

**保留原因**：
- 用于模块化依赖分析（Sprint 2）
- 与场景执行独立，无冲突

**字段**：
```sql
id, source_definition_id, target_definition_id, 
dependency_type, confidence, evidence, created_at
```

### 2. `api_chain_scenarios` 表

**用途**：链路与场景的多对多关联

**保留原因**：
- 用于跨模块场景组合
- 与场景执行独立，无冲突

**字段**：
```sql
id, chain_id, chain_type, scenario_id, 
is_primary, mapping_config, created_at, updated_at
```

---

## 数据验证脚本

```sql
-- 验证 api_scenarios 表结构
SELECT 
    column_name, 
    data_type, 
    is_nullable, 
    column_default
FROM information_schema.columns 
WHERE table_name = 'api_scenarios'
ORDER BY ordinal_position;

-- 验证 scenario_nodes 表结构
SELECT 
    column_name, 
    data_type, 
    is_nullable, 
    column_default
FROM information_schema.columns 
WHERE table_name = 'scenario_nodes'
ORDER BY ordinal_position;

-- 验证外键约束
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name IN ('api_scenarios', 'scenario_nodes');

-- 验证索引
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('api_scenarios', 'scenario_nodes')
ORDER BY tablename, indexname;
```

---

## 回滚策略

### 情况 1：激进式迁移后回滚

```sql
-- 如果 V1 迁移后发现问题，可以快速回滚
DROP TABLE IF EXISTS api_scenarios CASCADE;
DROP TABLE IF EXISTS scenario_nodes CASCADE;

-- 恢复旧表（如果有备份）
-- CREATE TABLE api_scenarios AS SELECT * FROM api_scenarios_backup;
-- CREATE TABLE scenario_endpoints AS SELECT * FROM scenario_endpoints_backup;
```

### 情况 2：渐进式迁移后回滚

```sql
-- 重命名回旧表
BEGIN;

ALTER TABLE api_scenarios RENAME TO api_scenarios_v1_failed;
ALTER TABLE api_scenarios_backup_YYYYMMDD RENAME TO api_scenarios;

ALTER TABLE scenario_nodes RENAME TO scenario_nodes_failed;
ALTER TABLE scenario_endpoints_backup_YYYYMMDD RENAME TO scenario_endpoints;

COMMIT;

-- 删除失败的 V1 表
DROP TABLE IF EXISTS api_scenarios_v1_failed CASCADE;
DROP TABLE IF EXISTS scenario_nodes_failed CASCADE;
```

---

## 注意事项

1. **数据备份**：执行任何迁移前，务必备份数据库
2. **测试先行**：在测试环境充分验证后再在生产环境执行
3. **停机时间**：渐进式迁移阶段 3 需要短暂停机（< 1 秒）
4. **应用兼容**：确保应用代码已更新为使用新表结构
5. **索引优化**：迁移后重建索引以提高性能
6. **监控观察**：迁移后密切监控系统日志和性能指标

---

## 推荐执行顺序

1. ✅ 在测试环境执行激进式迁移
2. ✅ 验证功能完整性
3. ✅ 在生产环境执行渐进式迁移
4. ✅ 监控 7 天，确认无异常
5. ✅ 删除备份表

---

## 联系人

如有问题，请联系：
- 技术负责人：[待补充]
- DBA：[待补充]