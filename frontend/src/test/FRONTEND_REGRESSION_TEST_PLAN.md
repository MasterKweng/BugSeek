# 前端回归用例测试计划

**BSK-SC-033: 前端回归用例**

## 测试框架建议

由于当前项目未配置前端测试框架，建议使用以下组合：

1. **测试运行器**: Vitest (与 Vite 原生集成)
2. **测试工具**: Testing Library (React Testing Library)
3. **Mock**: MSW (Mock Service Worker) 用于 API Mock

安装命令：
```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event msw
```

配置文件示例：`vitest.config.ts`
```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
```

## 关键交互流程测试用例

### 1. 意图工作台（Intent Workbench）

#### 测试用例 1.1: 意图输入与场景生成

**前置条件**: 用户已登录，有有效的项目

**测试步骤**:
1. 导航到"意图工作台"页面
2. 在意图输入框中输入: "测试用户创建、查询和删除流程"
3. 点击"生成场景"按钮
4. 等待 AI 生成完成

**预期结果**:
- 意图输入框显示输入的文本
- "生成场景"按钮在生成过程中显示加载状态
- 生成完成后显示候选 API 列表
- 显示生成的场景节点图（至少 3 个节点）
- 显示场景描述和执行顺序说明

**测试代码示例**:
```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IntentWorkbench } from '@/pages/scenario/IntentWorkbench'
import { server } from '@/test/mocks/server'
import { rest } from 'msw'

describe('IntentWorkbench - 意图生成', () => {
  beforeAll(() => server.listen())
  afterEach(() => server.resetHandlers())
  afterAll(() => server.close())

  it('应该成功生成场景', async () => {
    // Mock API 响应
    server.use(
      rest.post('/api/v1/intent-workbench/retrieve-apis', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            code: 0,
            message: 'success',
            data: {
              candidates: [
                { id: 1, method: 'POST', path: '/api/users', summary: '创建用户' },
                { id: 2, method: 'GET', path: '/api/users/:id', summary: '获取用户' },
              ]
            }
          })
        )
      }),
      rest.post('/api/v1/intent-workbench/generate-scenario', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            code: 0,
            message: 'success',
            data: {
              scenario: { name: '用户管理流程测试' },
              nodes: [
                { node_key: 'create_user', node_name: '创建用户' },
                { node_key: 'get_user', node_name: '获取用户' },
              ]
            }
          })
        )
      })
    )

    render(<IntentWorkbench />)

    // 输入意图
    const input = screen.getByPlaceholderText(/请输入您的测试意图/i)
    await userEvent.type(input, '测试用户创建、查询和删除流程')

    // 点击生成按钮
    const generateButton = screen.getByRole('button', { name: /生成场景/i })
    await userEvent.click(generateButton)

    // 验证结果
    await waitFor(() => {
      expect(screen.getByText('用户管理流程测试')).toBeInTheDocument()
      expect(screen.getByText('创建用户')).toBeInTheDocument()
      expect(screen.getByText('获取用户')).toBeInTheDocument()
    })
  })
})
```

#### 测试用例 1.2: 场景确认与落库

**前置条件**: 已生成场景草案

**测试步骤**:
1. 查看生成的场景节点图
2. 检查节点依赖关系
3. 点击"确认并保存"按钮
4. 等待保存完成

**预期结果**:
- 显示保存成功的提示
- 导航到场景列表页面
- 新创建的场景出现在列表中
- 场景状态为"已激活"

### 2. 场景编排器（Scenario Designer）

#### 测试用例 2.1: DAG 可视化渲染

**前置条件**: 打开已创建的场景

**测试步骤**:
1. 导航到场景编排页面
2. 查看节点图

**预期结果**:
- 显示所有场景节点
- 节点之间显示依赖连线
- 节点显示名称和类型
- 支持拖拽调整节点位置

#### 测试用例 2.2: 节点编辑

**前置条件**: 打开已创建的场景

**测试步骤**:
1. 点击某个节点
2. 在右侧面板编辑节点配置
3. 修改输入映射
4. 修改提取规则
5. 点击"保存"

**预期结果**:
- 节点配置更新成功
- 变量映射正确显示
- 图中节点状态更新

### 3. 场景执行（Scenario Execution）

#### 测试用例 3.1: 场景执行触发

**前置条件**: 打开已激活的场景

**测试步骤**:
1. 点击"执行场景"按钮
2. 选择环境
3. 点击"开始执行"

**预期结果**:
- 显示执行进度
- 节点实时更新状态
- 显示执行日志

**测试代码示例**:
```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ScenarioExecution } from '@/pages/scenario/ScenarioExecution'
import { server } from '@/test/mocks/server'

describe('ScenarioExecution - 场景执行', () => {
  it('应该成功执行场景', async () => {
    // Mock 执行 API
    server.use(
      rest.post('/api/v1/scenarios/1/execute', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            code: 0,
            message: 'success',
            data: {
              execution_id: 123,
              status: 'running',
              total_nodes: 3,
              passed_nodes: 0,
              failed_nodes: 0
            }
          })
        )
      })
    )

    render(<ScenarioExecution scenarioId={1} />)

    // 点击执行按钮
    const executeButton = screen.getByRole('button', { name: /执行场景/i })
    await userEvent.click(executeButton)

    // 选择环境
    const environmentSelect = screen.getByRole('combobox')
    await userEvent.selectOptions(environmentSelect, '测试环境')

    // 开始执行
    const startButton = screen.getByRole('button', { name: /开始执行/i })
    await userEvent.click(startButton)

    // 验证执行状态
    await waitFor(() => {
      expect(screen.getByText(/执行中/i)).toBeInTheDocument()
    })
  })
})
```

#### 测试用例 3.2: 实时进度更新

**前置条件**: 场景正在执行中

**测试步骤**:
1. 观察执行进度条
2. 查看节点状态变化
3. 查看实时日志

**预期结果**:
- 进度条实时更新
- 节点状态从"待执行" -> "执行中" -> "已通过/失败"
- 日志实时滚动

#### 测试用例 3.3: 失败节点定位

**前置条件**: 场景执行完成，有失败节点

**测试步骤**:
1. 查看执行结果
2. 点击失败的节点
3. 查看错误详情

**预期结果**:
- 失败节点高亮显示
- 显示错误消息
- 显示请求和响应详情
- 显示断言结果

### 4. 场景级字段映射确认

#### 测试用例 4.1: 场景级映射建议查看

**前置条件**: 已生成场景并触发 JIT 映射

**测试步骤**:
1. 导航到字段映射页面
2. 选择"按场景查看"模式
3. 选择目标场景

**预期结果**:
- 显示该场景涉及的接口
- 显示字段映射建议
- 显示置信度
- 显示连线视图

#### 测试用例 4.2: 批量确认映射

**前置条件**: 查看场景级映射建议

**测试步骤**:
1. 查看所有映射建议
2. 选择需要确认的映射
3. 点击"批量确认"
4. 点击"应用到场景"

**预期结果**:
- 显示确认成功的提示
- 映射应用到场景节点
- 返回场景编排页面
- 节点输入映射已更新

### 5. 场景报告查看

#### 测试用例 5.1: 执行报告查看

**前置条件**: 场景执行完成

**测试步骤**:
1. 导航到场景执行历史
2. 点击某次执行记录
3. 查看执行报告

**预期结果**:
- 显示执行摘要（通过率、耗时等）
- 显示节点执行详情
- 显示请求/响应
- 显示断言结果
- 如果有失败，显示 RCA 分析

#### 测试用例 5.2: 报告下载

**前置条件**: 查看执行报告

**测试步骤**:
1. 点击"下载报告"按钮
2. 选择格式（HTML/PDF）
3. 确认下载

**预期结果**:
- 报告文件开始下载
- 文件名格式正确
- 报告内容完整

## Smoke 测试清单

每次部署前必须执行的快速验证：

### 1. 页面加载测试
- [ ] 首页能正常加载
- [ ] 意图工作台页面能正常加载
- [ ] 场景列表页面能正常加载
- [ ] 场景编排页面能正常加载
- [ ] 场景执行页面能正常加载

### 2. 关键流程测试
- [ ] 用户登录流程
- [ ] 意图输入 -> 场景生成流程
- [ ] 场景创建 -> 保存流程
- [ ] 场景执行流程
- [ ] 报告查看流程

### 3. 状态管理测试
- [ ] 场景列表正确加载
- [ ] 场景详情正确显示
- [ ] 执行历史正确显示
- [ ] 用户信息正确显示

### 4. API 集成测试
- [ ] 意图生成 API 调用成功
- [ ] 场景 CRUD API 调用成功
- [ ] 场景执行 API 调用成功
- [ ] 报告获取 API 调用成功

### 5. 错误处理测试
- [ ] 网络错误正确提示
- [ ] API 错误正确提示
- [ ] 表单验证正确提示
- [ ] 权限错误正确提示

## 测试执行指南

### 本地测试

1. **安装依赖**:
```bash
npm install
```

2. **运行测试**:
```bash
npm run test
```

3. **生成覆盖率报告**:
```bash
npm run test:coverage
```

### CI/CD 集成

在 CI/CD 流水线中添加测试步骤：

```yaml
# .github/workflows/test.yml
name: Frontend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm run test
      - run: npm run test:coverage
      - uses: codecov/codecov-action@v3
```

### 测试覆盖率目标

- **整体覆盖率**: ≥ 70%
- **关键路径覆盖率**: ≥ 90%
- **组件覆盖率**: ≥ 60%

## 测试最佳实践

1. **使用测试优先开发（TDD）**: 先写测试，再写代码
2. **测试用户行为**: 测试用户如何使用应用，而不是实现细节
3. **保持测试独立**: 每个测试应该独立运行
4. **使用有意义的断言**: 断言应该清晰表达预期行为
5. **Mock 外部依赖**: 使用 Mock 隔离外部依赖
6. **测试边界情况**: 测试正常流程和异常情况
7. **定期维护测试**: 删除过时的测试，更新变化的测试

## 常见问题

### Q: 如何测试异步操作？
A: 使用 `waitFor` 或 `findBy*` 查询器等待异步操作完成。

### Q: 如何测试表单？
A: 使用 `userEvent` 模拟用户输入和提交。

### Q: 如何测试路由？
A: 使用 MemoryRouter 或测试路由组件。

### Q: 如何测试状态管理？
A: 测试使用该状态的组件，而不是直接测试 store。

## 下一步行动

1. 配置测试环境（安装依赖、配置文件）
2. 编写第一个测试用例
3. 建立测试规范
4. 集成到 CI/CD 流程
5. 定期回顾和改进测试覆盖率

---

**文档版本**: 1.0
**创建日期**: 2026-03-10
**最后更新**: 2026-03-10
**维护者**: Frontend Team