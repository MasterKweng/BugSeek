import { Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { Spin } from 'antd'
import ProtectedRoute from './components/ProtectedRoute'
import ProjectVersionGuard from './components/ProjectVersionGuard'

// 路由懒加载 (P1-7)
const MainLayout = lazy(() => import('./components/MainLayout'))
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const Profile = lazy(() => import('./pages/Profile'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Projects = lazy(() => import('./pages/Projects'))
const Versions = lazy(() => import('./pages/Versions'))
const DbSchema = lazy(() => import('./pages/version-center/DbSchema'))
const FieldMapping = lazy(() => import('./pages/version-center/FieldMapping'))
const FieldMappingHelp = lazy(() => import('./pages/version-center/FieldMappingHelp'))
const KnowledgeGraph = lazy(() => import('./pages/KnowledgeGraph'))
const EnvironmentManagement = lazy(() => import('./pages/project-center/EnvironmentManagement'))
const OperationsCenter = lazy(() => import('./pages/operations/OperationsCenter'))
const ExecutionCenter = lazy(() => import('./pages/operations/ExecutionCenter'))
const ExecutionDetail = lazy(() => import('./pages/operations/ExecutionDetail'))
const ExecutionReports = lazy(() => import('./pages/operations/ExecutionReports'))
const UIAutomationWorkbench = lazy(() => import('./pages/ui-automation/UIAutomationWorkbench'))

// API Hub 模块 (V2.0)
const ApiHubDefinitions = lazy(() => import('./pages/api-hub/DefinitionsList'))
const ApiHubCases = lazy(() => import('./pages/api-hub/CasesList'))
const ApiHubSync = lazy(() => import('./pages/api-hub/SyncTasksList'))
const ApiHubSnapshots = lazy(() => import('./pages/api-hub/VersionSnapshots'))

// 场景工作室模块 (V2.0)
const IntentWorkbench = lazy(() => import('./pages/scenario/IntentWorkbench'))
const ScenarioList = lazy(() => import('./pages/scenario/ScenarioList'))
const ScenarioDetail = lazy(() => import('./pages/scenario/ScenarioDetail'))
const ScenarioDesigner = lazy(() => import('./pages/scenario/ScenarioDesigner'))
const ScenarioExecution = lazy(() => import('./pages/scenario/ScenarioExecution'))
const ScenarioFieldMapping = lazy(() => import('./pages/scenario/ScenarioFieldMapping'))

// 鉴权配置模块
const AuthConfig = lazy(() => import('./pages/AuthConfig'))

// 加载组件
const LoadingFallback = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
    <Spin size="large" tip="加载中..." />
  </div>
)

function App() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="profile" element={<Profile />} />
          {/* 项目管理模块 */}
          <Route path="projects" element={<Projects />} />
          <Route path="projects/:projectId/versions" element={<Versions />} />
          <Route path="project-center/environments" element={<ProjectVersionGuard><EnvironmentManagement /></ProjectVersionGuard>} />
          <Route path="version-center/db-schema" element={<ProjectVersionGuard><DbSchema /></ProjectVersionGuard>} />
          <Route path="version-center/field-mapping" element={<ProjectVersionGuard><FieldMapping /></ProjectVersionGuard>} />
          <Route path="version-center/field-mapping/help" element={<ProjectVersionGuard><FieldMappingHelp /></ProjectVersionGuard>} />
          <Route path="knowledge-graph" element={<ProjectVersionGuard><KnowledgeGraph /></ProjectVersionGuard>} />
          {/* 需求洞察模块 */}
          {/* 代码质量模块 */}
          {/* API Hub 模块 (V2.0) */}
          <Route path="api-hub/definitions" element={<ProjectVersionGuard><ApiHubDefinitions /></ProjectVersionGuard>} />
          <Route path="api-hub/definitions/:id" element={<ProjectVersionGuard><ApiHubDefinitions /></ProjectVersionGuard>} />
          <Route path="api-hub/cases" element={<ProjectVersionGuard><ApiHubCases /></ProjectVersionGuard>} />
          <Route path="api-hub/sync" element={<ProjectVersionGuard><ApiHubSync /></ProjectVersionGuard>} />
          <Route path="api-hub/snapshots" element={<ProjectVersionGuard><ApiHubSnapshots /></ProjectVersionGuard>} />
          {/* 场景工作室模块 (V2.0) - BSK-SC-020 */}
          <Route path="scenario/intent-workbench" element={<ProjectVersionGuard><IntentWorkbench /></ProjectVersionGuard>} />
          <Route path="scenario/list" element={<ProjectVersionGuard><ScenarioList /></ProjectVersionGuard>} />
          <Route path="scenario/:scenarioId" element={<ProjectVersionGuard><ScenarioDetail /></ProjectVersionGuard>} />
          <Route path="scenario/:scenarioId/design" element={<ProjectVersionGuard><ScenarioDesigner /></ProjectVersionGuard>} />
          <Route path="scenario/:scenarioId/execution/:executionId" element={<ProjectVersionGuard><ScenarioExecution /></ProjectVersionGuard>} />
          <Route path="scenario/:scenarioId/field-mapping" element={<ProjectVersionGuard><ScenarioFieldMapping /></ProjectVersionGuard>} />
          {/* 鉴权配置模块 */}
          <Route path="projects/:projectId/auth-config" element={<ProjectVersionGuard><AuthConfig /></ProjectVersionGuard>} />
          <Route path="operations" element={<ProjectVersionGuard><OperationsCenter /></ProjectVersionGuard>} />
          <Route path="operations/executions" element={<ProjectVersionGuard><ExecutionCenter /></ProjectVersionGuard>} />
          <Route path="operations/executions/:executionId" element={<ProjectVersionGuard><ExecutionDetail /></ProjectVersionGuard>} />
          <Route path="operations/reports" element={<ProjectVersionGuard><ExecutionReports /></ProjectVersionGuard>} />
          {/* UI 自动化模块 */}
          <Route path="ui-automation" element={<ProjectVersionGuard><UIAutomationWorkbench /></ProjectVersionGuard>} />
          {/* 流程编排模块 */}
          {/* 基础设施模块 */}
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

export default App
