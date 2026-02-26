# Celery 字段映射任务测试指南

## 概述

本文档描述如何测试 Celery 字段映射任务的完整流程。

## 测试前提

### 1. 启动 Redis 服务

确保 Redis 服务正在运行：

```bash
# Windows (PowerShell)
redis-server --port 6380

# Linux/Mac
redis-server --port 6380
```

### 2. 启动 Celery Worker

在 `backend` 目录下运行：

```bash
# Windows
celery -A app.celery_config worker --loglevel=info --pool=solo

# Linux/Mac
celery -A app.celery_config worker --loglevel=info --pool=solo
```

或者使用启动脚本：

```bash
# Windows
start_celery_worker.bat

# Linux/Mac
./start_celery_worker.sh
```

## 测试步骤

### 步骤 1: 代码逻辑验证

验证 Celery 任务代码逻辑是否正确：

```bash
cd D:\code\BugSeek\backend
python test_celery_logic.py
```

预期结果：
- ✓ 模块导入成功
- ✓ 函数签名正确
- ✓ 异步函数处理正确
- ✓ 所有依赖可用
- ✓ 文件内容符合规范

### 步骤 2: 启动后端服务

在新的终端窗口中启动 FastAPI 服务：

```bash
cd D:\code\BugSeek\backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 步骤 3: 运行端到端测试

在另一个终端窗口中运行测试：

```bash
cd D:\code\BugSeek\backend
python test_celery_e2e.py
```

预期结果：
- ✓ 测试1: 创建任务 - PASS
- ✓ 测试2: 提交 Celery 任务 - PASS
- ✓ 测试3: 检查任务状态 - PASS
- ✓ 测试4: 等待任务完成 - PASS（需要 Worker 运行）
- ✓ 测试5: 验证任务结果 - PASS（需要 Worker 运行）

### 步骤 4: 验证数据库

检查数据库中的任务记录：

```sql
SELECT id, status, progress, celery_task_id, started_at, finished_at 
FROM async_tasks 
WHERE id = 458
ORDER BY id DESC 
LIMIT 1;
```

预期结果：
- `status` = "completed"
- `progress` = 100
- `celery_task_id` 有值
- `started_at` 和 `finished_at` 有值

### 步骤 5: 验证 Worker 日志

查看 Celery Worker 的输出日志，确认任务已执行：

```
[2026-02-12 12:40:00] 开始执行字段映射任务: task_id=458
[2026-02-12 12:40:00] 任务执行成功: task_id=458
```

## 常见问题

### 问题 1: 任务一直处于 pending 状态

**原因**: Celery Worker 没有运行

**解决方案**:
1. 检查 Redis 服务是否正常运行
2. 检查 Celery Worker 是否已启动
3. 检查 Worker 日志是否有错误信息

### 问题 2: Redis 连接失败

**原因**: Redis 服务未启动或配置错误

**解决方案**:
1. 启动 Redis 服务
2. 检查 `celery_config.py` 中的 Broker URL 配置
3. 确认 Redis 端口正确（默认 6380）

### 问题 3: Worker 崩溃

**原因**: 任务执行失败或代码错误

**解决方案**:
1. 查看 Worker 日志获取详细错误信息
2. 检查任务参数是否正确
3. 确保所有依赖都已安装

### 问题 4: 数据库连接失败

**原因**: Worker 无法连接数据库

**解决方案**:
1. 检查数据库服务是否正常运行
2. 检查数据库连接配置
3. 检查数据库连接池配置

## 测试脚本说明

### test_celery_logic.py
验证 Celery 任务代码逻辑，包括：
- 模块导入
- 函数签名
- 异步函数处理
- 依赖检查
- 文件内容验证

### test_celery_e2e.py
完整的端到端测试，包括：
- 创建任务
- 提交 Celery 任务
- 检查任务状态
- 等待任务完成
- 验证任务结果

### test_celery_integration.py
集成测试，支持两种模式：
1. 直接测试任务执行（不使用 Celery）
2. 测试 Celery 任务提交（需要 Worker）

## 性能基准

### 不使用 AI 的情况
- 100 个字段：约 5-10 秒
- 500 个字段：约 20-30 秒
- 1000 个字段：约 40-60 秒

### 使用 AI 的情况
- 100 个字段：约 30-60 秒
- 500 个字段：约 2-3 分钟
- 1000 个字段：约 4-6 分钟

## 下一步

测试通过后，可以进行：
1. 性能优化
2. 监控和告警
3. 生产环境部署