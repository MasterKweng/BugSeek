# 字段映射异步任务 - P2 后端优化 API 文档

## 概述

本文档描述了字段映射异步任务后端 P2 优化的相关接口和功能。P2 优化主要关注连接池监控、健康检查和系统状态管理。

---

## 修改的文件

### 1. `backend/app/dependencies.py`

#### 功能增强

- **新增 `max_concurrent` 统计**：跟踪最大并发连接数
- **增强 `log_pool_status()` 函数**：
  - 支持指定日志级别
  - 显示更详细的连接池信息
  - 包含最大并发连接数统计

- **增强 `get_pool_stats()` 函数**：
  - 返回完整的连接池统计信息
  - 包含最大并发连接数

- **增强事件监听器**：
  - `receive_connect`：显示更详细的连接创建信息
  - `receive_checkout`：根据检出频率智能调整日志级别
  - `receive_checkin`：显示连接归还信息
  - `receive_error`：根据错误类型选择适当的日志级别

#### 新增统计字段

```python
{
    "created": 0,          # 创建的连接数
    "checked_out": 0,      # 检出的连接数
    "checked_in": 0,       # 归还的连接数
    "overflow": 0,         # 溢出连接数
    "errors": 0,           # 错误数
    "max_concurrent": 0    # 最大并发连接数（新增）
}
```

---

### 2. `backend/app/field_mapping/processor.py`

#### 功能增强

- **优化 `_refresh_db_connection()` 函数**：
  - 添加智能刷新策略，根据任务进度调整刷新频率
  - 任务前期（progress < 30%）：每 5 分钟刷新一次
  - 任务中期（30% <= progress < 70%）：每 3 分钟刷新一次
  - 任务后期（progress >= 70%）：每 2 分钟刷新一次
  - 根据进度调整日志级别（debug/info/warning）
  - 连接失败时自动标记任务为失败状态

#### 代码规范遵循

- 异常处理：捕获所有异常并记录
- 详细日志：包含 TraceID
- 智能刷新：根据任务进度决定刷新频率

---

### 3. `backend/app/api/v1/health.py`

#### 功能增强

##### 1. `/api/v1/health` - 基础健康检查

**响应字段增强**：
- 新增 `timestamp`：检查时间戳

**响应示例**：
```json
{
  "status": "ok",
  "message": "系统运行正常",
  "timestamp": 1739356800.123
}
```

---

##### 2. `/api/v1/health/db-pool` - 数据库连接池状态

**新增响应字段**：
- `utilization`：连接池利用率 (0-100%)
- `health`：健康度评分 (0-100)
- `warnings`：警告信息列表

**响应示例**：
```json
{
  "status": "ok",
  "pool_size": 20,
  "max_overflow": 30,
  "checked_out": 15,
  "overflow": 2,
  "idle": 5,
  "timeout": 60,
  "recycle": 3600,
  "total_connections": 22,
  "utilization": 55.88,
  "health": 90,
  "warnings": [],
  "timestamp": 1739356800.123
}
```

**健康度评分规则**：
- 初始分：100
- 利用率 > 80%：-20分
- 溢出连接数 > 10：-15分
- 空闲连接数 < 5：-10分

---

##### 3. `/api/v1/health/db-pool/stats` - 连接池统计信息

**响应字段增强**：
- 新增 `timestamp`：检查时间戳

**响应示例**：
```json
{
  "status": "ok",
  "statistics": {
    "pool_size": 20,
    "pool_overflow": 2,
    "checked_out": 15,
    "available": 5,
    "max_overflow": 30,
    "timeout": 60,
    "recycle": 3600,
    "stats": {
      "created": 25,
      "checked_out": 1000,
      "checked_in": 985,
      "overflow": 10,
      "errors": 0,
      "max_concurrent": 18
    }
  },
  "timestamp": 1739356800.123
}
```

---

##### 4. `/api/v1/health/db-pool/detailed` - 连接池详细状态（新增）

**功能**：
- 综合连接池信息、统计信息和配置信息
- 计算健康度评分
- 提供优化建议

**响应字段**：
- `status`：状态 (ok/warning/error)
- `pool`：连接池信息
- `stats`：统计信息
- `health`：健康度评分 (0-100)
- `utilization`：连接池利用率 (0-100%)
- `config`：配置信息
- `recommendations`：优化建议列表
- `timestamp`：检查时间戳

**响应示例**：
```json
{
  "status": "ok",
  "pool": {
    "pool_size": 20,
    "max_overflow": 30,
    "checked_out": 15,
    "overflow": 2,
    "idle": 5,
    "timeout": 60,
    "recycle": 3600,
    "total_connections": 22
  },
  "stats": {
    "pool_size": 20,
    "pool_overflow": 2,
    "checked_out": 15,
    "available": 5,
    "max_overflow": 30,
    "timeout": 60,
    "recycle": 3600,
    "stats": {
      "created": 25,
      "checked_out": 1000,
      "checked_in": 985,
      "overflow": 10,
      "errors": 0,
      "max_concurrent": 18
    }
  },
  "health": 90,
  "utilization": 55.88,
  "config": {
    "DB_POOL_SIZE": 20,
    "DB_MAX_OVERFLOW": 30,
    "DB_POOL_TIMEOUT": 60,
    "DB_POOL_RECYCLE": 3600,
    "DB_POOL_PRE_PING": true,
    "DB_POOL_EXPIRE": 30
  },
  "recommendations": [],
  "timestamp": 1739356800.123
}
```

**优化建议规则**：
- 利用率 > 80%：建议增加连接池大小 (DB_POOL_SIZE)
- 溢出连接数 > 10：建议增加最大溢出连接数 (DB_MAX_OVERFLOW)
- 检出连接数 > 池大小：存在连接泄漏风险，建议检查连接是否正确释放

---

##### 5. `/api/v1/health/db-pool/reset-cache` - 清除用户缓存

**响应字段增强**：
- 新增 `timestamp`：检查时间戳

**响应示例**：
```json
{
  "status": "ok",
  "message": "用户缓存已清除",
  "timestamp": 1739356800.123
}
```

---

## 测试脚本

### `backend/test_p2_backend.py`

#### 测试用例

1. **基础健康检查接口测试**
   - 验证 HTTP 状态码
   - 验证响应字段完整性
   - 验证 timestamp 字段

2. **数据库连接池状态接口测试**
   - 验证响应字段完整性
   - 验证数据类型正确性
   - 验证数值范围有效性

3. **连接池统计信息接口测试**
   - 验证响应字段完整性
   - 验证 statistics 子字段完整性
   - 验证 stats 子字段完整性

4. **连接池详细状态接口测试**
   - 验证响应字段完整性
   - 验证 config 子字段完整性
   - 验证 recommendations 字段

#### 运行测试

```bash
cd backend
python test_p2_backend.py
```

#### 测试结果

测试结果将保存到 `backend/test_p2_results.json` 文件中。

---

## 代码规范遵循

所有修改均遵循 `@rule_doc/后端代码规范.md`：

1. **统一响应格式**：所有 API 返回统一的响应格式
2. **异常处理**：所有异常都被捕获并记录
3. **详细日志**：包含 TraceID 和必要的上下文信息
4. **类型安全**：使用 Python 类型注解
5. **无魔术值**：所有配置项都有明确的常量定义

---

## 依赖

- FastAPI
- SQLAlchemy
- requests (测试脚本)

---

## 使用说明

### 启动后端服务

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 查看健康状态

```bash
# 基础健康检查
curl http://localhost:8000/api/v1/health

# 连接池状态
curl http://localhost:8000/api/v1/health/db-pool

# 连接池统计信息
curl http://localhost:8000/api/v1/health/db-pool/stats

# 连接池详细状态
curl http://localhost:8000/api/v1/health/db-pool/detailed
```

### 运行测试

```bash
cd backend
python test_p2_backend.py
```

---

## 注意事项

1. 后端服务必须运行才能执行测试
2. 数据库连接池配置应与服务器硬件配置匹配
3. 定期检查健康检查接口，监控系统状态
4. 连接池利用率过高时，建议调整配置参数

---

## 后续优化建议

1. 添加更多系统资源监控（CPU、内存、磁盘）
2. 添加异步任务队列监控（Celery）
3. 添加历史任务统计信息
4. 添加性能指标记录和分析
5. 添加告警机制（邮件、短信）

---

## 版本历史

- **V1.0** (2026-02-12)：初始版本
  - 添加连接池监控增强
  - 优化异步任务处理器连接管理
  - 添加健康检查接口优化
  - 创建测试脚本

---

## 相关文档

- [后端代码规范](D:\code\BugSeek\rule_doc\后端代码规范.md)
- [字段映射异步任务 API 文档](D:\code\BugSeek\backend\API文档_字段映射异步任务.md)