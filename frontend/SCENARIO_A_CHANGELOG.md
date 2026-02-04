# 场景组装方案A - 变更记录与回滚指南

## [SCENARIO-A-SOLUTION] 标记说明

所有本次方案A实现的代码变更都已标记 `[SCENARIO-A-SOLUTION]`，方便后续回滚。

---

## 变更文件清单

### 1. 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/pages/api/ModuleDetail.tsx` | 模块详情独立页面 |

### 2. 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/App.tsx` | 添加模块详情路由 |
| `frontend/src/store/scenario.ts` | 添加 `internalChains` 状态和 `loadInternalChains` 方法 |
| `frontend/src/pages/api/Modules.tsx` | 详情按钮改为跳转到独立页面 |

### 3. 备份文件

| 备份文件 | 原文件 | 用途 |
|----------|--------|------|
| `Modules_backup_before_route_change.tsx` | `Modules.tsx` | 列表页备份 |
| `App_backup_before_route_change.tsx` | `App.tsx` | 路由配置备份 |

---

## 回滚步骤

### 方式一：使用备份文件快速回滚

```bash
# 1. 恢复 Modules.tsx
cd D:\code\BugSeek\frontend\src\pages\api
del Modules.tsx
rename Modules_backup_before_route_change.tsx Modules.tsx

# 2. 恢复 App.tsx
cd D:\code\BugSeek\frontend\src
del App.tsx
rename App_backup_before_route_change.tsx App.tsx

# 3. 删除新增文件
del ModuleDetail.tsx

# 4. 恢复 Store（撤销 internalChains 相关变更）
# 需要手动撤销 scenario.ts 中的以下标记内容：
# - internalChains 状态
# - loadingInternalChains 状态
# - loadInternalChains 方法
```

### 方式二：手动回滚（推荐）

搜索所有 `[SCENARIO-A-SOLUTION]` 标记，按以下顺序撤销：

#### Step 1: 撤销 App.tsx 变更

```diff
- const ModuleDetail = lazy(() => import('./pages/api/ModuleDetail'))  // [SCENARIO-A-SOLUTION]
```

```diff
- <Route path="api/modules/:moduleId" element={<ProjectVersionGuard><ModuleDetail /></ProjectVersionGuard>} />  {/* [SCENARIO-A-SOLUTION] */}
```

#### Step 2: 撤销 scenario.ts 变更

删除以下带 `[SCENARIO-A-SOLUTION]` 标记的内容：
- `internalChains: any[]` 状态定义
- `loadingInternalChains: boolean` 状态定义
- `loadInternalChains` 方法定义和实现

#### Step 3: 撤销 Modules.tsx 变更

```diff
- import { useNavigate } from 'react-router-dom';
- const navigate = useNavigate();
```

```diff
- {/* [SCENARIO-A-SOLUTION] 详情按钮改为跳转到独立页面 */}
- <Button type="link" icon={<EyeOutlined />} onClick={() => navigate(`/api/modules/${record.id}`)}>
+ <Button type="link" icon={<EyeOutlined />} onClick={() => viewModuleDetail(record)}>
```

#### Step 4: 删除新增文件

```bash
del frontend\src\pages\api\ModuleDetail.tsx
```

---

## 新增功能说明

### 1. 独立详情页面 (`ModuleDetail.tsx`)

**特性：**
- 全屏展示，适合大数据量
- 四个 Tab：依赖关系、输入接口、输出接口、内部链路
- 内部链路支持虚拟滚动 + 分页
- 支持搜索、筛选、导出（待实现）

**路由：** `/api/modules/:moduleId`

### 2. Store 扩展

**新增状态：**
- `internalChains: any[]` - 内部链路列表
- `loadingInternalChains: boolean` - 加载状态

**新增方法：**
- `loadInternalChains(moduleId: number)` - 加载内部链路

### 3. 列表页更新

**变更：**
- 详情按钮从弹窗改为跳转到独立页面
- 添加面包屑导航
- 支持返回列表功能

---

## 回滚验证

回滚后请验证以下功能是否正常：

1. ✅ 模块列表页面正常显示
2. ✅ 点击"详情"按钮打开弹窗（而非跳转）
3. ✅ 模块分析功能正常
4. ✅ 依赖图查看正常
5. ✅ 无编译错误

---

## 注意事项

1. **备份文件保留**：建议保留备份文件一段时间，确保回滚成功后再删除
2. **Git 提交**：如果使用 Git，建议创建新分支提交此次变更，方便回滚
3. **数据库**：本次变更不涉及数据库修改，无需回滚数据库
4. **后端 API**：本次变更假设后端已支持 `/api-integration/modules/:moduleId/internal-chains` 接口

---

## 技术栈

- React Router v6
- Zustand
- Ant Design v5
- TypeScript

---

## 联系方式

如有问题，请查看备份文件或联系开发团队。