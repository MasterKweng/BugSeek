# 执行中心联调回归清单

## 自动化部分

先运行后端 smoke 脚本：

```powershell
cd D:\code\BugSeek\backend
$env:PYTHONPATH = "D:\code\BugSeek\backend"
.\venv\Scripts\python.exe scripts\run_execution_center_regression.py
```

脚本会做这些事情：

- 复用真实开发库
- 自动准备一组最小执行中心样本数据
- 校验执行列表、详情、子执行、结果详情、报表接口
- 校验父执行、来源执行、结果增强字段是否可读
- 输出本次样本执行 ID，供前端页面回归使用

## 手工主链路

1. 打开 [ExecutionCenter.tsx](/D:/code/BugSeek/frontend/src/pages/operations/ExecutionCenter.tsx) 对应页面 `/operations/executions`
2. 确认可以看到 smoke 脚本生成的样本记录
3. 从列表进入执行详情页
4. 在详情页确认：
   - 执行 ID 可复制
   - 父执行可跳转
   - 来源执行可跳转
   - 子执行列表可打开
   - 结果列表可打开
5. 打开结果详情抽屉，确认：
   - 请求头可复制
   - 请求体可复制
   - 响应头可复制
   - 响应体可复制
   - 断言结果可复制
   - 提取变量可复制
6. 打开 `/operations/reports`
7. 确认：
   - 趋势折线图展示正常
   - 环境柱状图展示正常
   - 版本柱状图展示正常
   - 失败 Top 和性能排行有数据

## 手工异常链路

1. 在执行列表输入不存在的关键字，确认空态正常
2. 在结果列表筛选 `failed`，确认只展示失败结果
3. 在详情页打开重新执行弹窗，输入非法 JSON，确认前端报错且不发起重跑
4. 切换环境筛选和时间筛选，确认报表重新加载

## 数据对账

对 smoke 样本执行，核对下面字段：

- `test_executions.parent_execution_id`
- `test_executions.source_execution_id`
- `test_executions.version_id`
- `test_execution_results.definition_id`
- `test_execution_results.request_headers`
- `test_execution_results.response_headers`
- `test_execution_results.request_display_type`
- `test_execution_results.response_display_type`
- `test_execution_results.assertion_passed_count`
- `test_execution_results.assertion_total_count`

## 通过标准

- 自动化 smoke 脚本全部通过
- 前端页面能完整走通列表、详情、结果抽屉、报表
- 页面展示与数据库字段一致
- 没有白屏、无响应、控制台阻断错误
