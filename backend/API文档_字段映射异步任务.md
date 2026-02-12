# 字段映射异步任务 API 文档

## 概述

本文档描述字段映射异步任务相关的 API 接口，用于管理字段映射建议生成的异步任务。

## 基础信息

- **Base URL**: `/api/v1`
- **Content-Type**: `application/json`
- **统一响应格式**:
  ```json
  {
    "code": 0,
    "message": "success",
    "data": { ... }
  }
  ```

---

## API 接口

### 1. 获取异步任务列表

**接口**: `GET /async-tasks`

**描述**: 获取当前用户的异步任务列表，支持分页和筛选。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| task_type | string | 否 | 任务类型，默认 `field_mapping_suggest` |
| project_id | int | 否 | 项目ID（可选，默认使用上下文） |
| version_id | int | 否 | 版本ID（可选） |
| status | string | 否 | 状态筛选（可选） |
| limit | int | 否 | 每页数量，默认 20，范围 1-100 |
| offset | int | 否 | 偏移量，默认 0 |

**状态值**:
- `pending`: 等待中
- `running`: 运行中
- `completed`: 已完成
- `failed`: 失败
- `cancelled`: 已取消

**响应示例**:
```json
{
  "code": 0,
  "message": "查询成功",
  "data": {
    "total": 45,
    "items": [
      {
        "id": 101,
        "task_type": "field_mapping_suggest",
        "status": "completed",
        "progress": 100,
        "created_at": "2026-02-12T09:00:00",
        "finished_at": "2026-02-12T09:10:30",
        "duration": 630,
        "statistics": {
          "total_fields": 128,
          "auto_confirmed": 45,
          "ai_enhanced": 83
        },
        "result_count": 128
      }
    ]
  }
}
```

**字段说明**:

| 字段 | 类型 | 描述 |
|------|------|------|
| id | int | 任务ID |
| task_type | string | 任务类型 |
| status | string | 任务状态 |
| progress | int | 进度百分比 (0-100) |
| created_at | string | 创建时间 (ISO 8601) |
| finished_at | string | 完成时间 (ISO 8601) |
| duration | int | 任务耗时（秒） |
| statistics | object | 统计信息 |
| result_count | int | 生成建议数量 |

---

### 2. 获取异步任务详情

**接口**: `GET /async-tasks/{task_id}`

**描述**: 获取指定任务的详细信息，包括阶段进度和结果。

**路径参数**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| task_id | int | 是 | 任务ID |

**响应示例**:
```json
{
  "code": 0,
  "message": "查询成功",
  "data": {
    "task_id": 101,
    "task_type": "field_mapping_suggest",
    "status": "running",
    "progress": 45,
    "progress_message": "正在分析 api_field_path...",
    "current_stage": 2,
    "stages": [
      {
        "name": "字段提取",
        "status": "completed",
        "progress": 100,
        "description": "已提取 128 个字段，分组: 4 个"
      },
      {
        "name": "规则评分",
        "status": "running",
        "progress": 45,
        "description": "正在匹配... (45/128)"
      },
      {
        "name": "智能筛选",
        "status": "pending",
        "progress": 0,
        "description": null
      },
      {
        "name": "AI 优化",
        "status": "pending",
        "progress": 0,
        "description": null
      },
      {
        "name": "结果合并",
        "status": "pending",
        "progress": 0,
        "description": null
      }
    ],
    "statistics": {
      "total_fields": 128,
      "processed": 45,
      "auto_confirmed": 0,
      "ai_enhanced": 0
    },
    "result": null,
    "error_message": null,
    "can_retry": false,
    "retryable_stages": [],
    "started_at": "2026-02-12T09:00:00",
    "finished_at": null,
    "created_at": "2026-02-12T09:00:00",
    "updated_at": "2026-02-12T09:02:30"
  }
}
```

**字段说明**:

| 字段 | 类型 | 描述 |
|------|------|------|
| task_id | int | 任务ID |
| task_type | string | 任务类型 |
| status | string | 任务状态 |
| progress | int | 总体进度百分比 (0-100) |
| progress_message | string | 进度消息 |
| current_stage | int | 当前阶段编号 (1-5) |
| stages | array | 阶段列表 |
| stages[].name | string | 阶段名称 |
| stages[].status | string | 阶段状态 |
| stages[].progress | int | 阶段进度百分比 |
| stages[].description | string | 阶段描述（后端计算生成） |
| statistics | object | 统计信息 |
| result | object | 任务结果 |
| error_message | string | 错误消息 |
| can_retry | bool | 是否可以重试 |
| retryable_stages | array | 可重试的阶段编号列表 |
| started_at | string | 开始时间 (ISO 8601) |
| finished_at | string | 完成时间 (ISO 8601) |
| created_at | string | 创建时间 (ISO 8601) |
| updated_at | string | 更新时间 (ISO 8601) |

---

### 3. 取消异步任务

**接口**: `POST /async-tasks/{task_id}/cancel`

**描述**: 取消指定的异步任务。只有 `pending` 或 `running` 状态的任务才能取消。

**路径参数**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| task_id | int | 是 | 任务ID |

**请求体**: 无

**响应示例**:
```json
{
  "code": 0,
  "message": "任务已取消",
  "data": {
    "task_id": 101,
    "status": "cancelled"
  }
}
```

**错误示例**:

```json
// 任务不存在
{
  "code": 404,
  "message": "任务不存在：101"
}

// 无权限访问
{
  "code": 403,
  "message": "无权访问该任务"
}

// 任务状态不允许取消
{
  "code": 400,
  "message": "任务状态为 completed，无法取消"
}
```

---

### 4. 创建字段映射建议任务

**接口**: `POST /field-mappings/suggest-task`

**描述**: 创建字段映射建议生成的异步任务。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| project_id | int | 否 | 项目ID（可选，默认使用上下文） |
| version_id | int | 否 | 版本ID（可选，默认使用上下文） |

**请求体**:
```json
{
  "include_paths": true,
  "include_query": true,
  "include_body": true,
  "use_ai": true
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "任务创建成功",
  "data": {
    "task_id": 101,
    "status": "pending",
    "estimated_duration": 600,
    "estimated_fields": 150
  }
}
```

---

### 5. 获取字段映射建议结果

**接口**: `GET /field-mappings/suggestions`

**描述**: 获取字段映射建议的结果。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| task_id | int | 是 | 任务ID |

**响应示例**:
```json
{
  "code": 0,
  "message": "查询成功",
  "data": {
    "items": [
      {
        "definition_id": 1,
        "definition_method": "POST",
        "definition_path": "/api/orders",
        "api_field_path": "body.order_id",
        "candidates": [
          {
            "db_table": "orders",
            "db_column": "id",
            "score": 0.95,
            "reasons": ["名称匹配", "ID字段"]
          }
        ]
      }
    ]
  }
}
```

---

## 错误码说明

| 错误码 | 描述 |
|--------|------|
| 0 | 成功 |
| 400 | 请求参数错误 |
| 403 | 无权限访问 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 数据模型

### AsyncTaskSummary

任务摘要模型，用于列表展示。

```typescript
interface AsyncTaskSummary {
  id: number;
  task_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  created_at: string;  // ISO 8601
  finished_at: string | null;  // ISO 8601
  duration: number | null;  // 秒
  statistics: {
    total_fields?: number;
    auto_confirmed?: number;
    ai_enhanced?: number;
  };
  result_count: number | null;
}
```

### StageDetail

阶段详情模型。

```typescript
interface StageDetail {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  description: string | null;
}
```

---

## 使用示例

### 示例 1: 获取任务列表

```bash
curl -X GET "http://localhost:8000/api/v1/async-tasks?task_type=field_mapping_suggest&limit=20" \
  -H "Authorization: Bearer {token}"
```

### 示例 2: 获取任务详情

```bash
curl -X GET "http://localhost:8000/api/v1/async-tasks/101" \
  -H "Authorization: Bearer {token}"
```

### 示例 3: 取消任务

```bash
curl -X POST "http://localhost:8000/api/v1/async-tasks/101/cancel" \
  -H "Authorization: Bearer {token}"
```

### 示例 4: 创建任务

```bash
curl -X POST "http://localhost:8000/api/v1/field-mappings/suggest-task" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "include_paths": true,
    "include_query": true,
    "include_body": true,
    "use_ai": true
  }'
```

---

## 注意事项

1. **权限校验**: 所有接口都会校验用户权限，只能访问自己创建的任务
2. **状态限制**: 只有 `pending` 或 `running` 状态的任务才能取消
3. **分页限制**: 单次查询最多返回 100 条记录
4. **时间格式**: 所有时间字段使用 ISO 8601 格式
5. **统一响应**: 所有接口返回统一的响应格式 `{ code, message, data }`

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-02-12 | 初始版本，支持基本的任务管理功能 |