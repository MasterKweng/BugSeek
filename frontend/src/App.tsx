import { Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { Spin } from 'antd'
import ProtectedRoute from './components/ProtectedRoute'
import MainLayout from './components/MainLayout'
import ProjectVersionGuard from './components/ProjectVersionGuard'
import ComingSoon from './components/ComingSoon'

// 路由懒加载 (P1-7)
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const Profile = lazy(() => import('./pages/Profile'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Projects = lazy(() => import('./pages/Projects'))
const Versions = lazy(() => import('./pages/Versions'))

// API Hub 模块 (V2.0)
const ApiHubDefinitions = lazy(() => import('./pages/api-hub/DefinitionsList'))
const ApiHubCases = lazy(() => import('./pages/api-hub/CasesList'))
const ApiHubSync = lazy(() => import('./pages/api-hub/SyncTasksList'))
const ApiHubSnapshots = lazy(() => import('./pages/api-hub/VersionSnapshots'))

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
          {/* 需求洞察模块 */}
          <Route path="requirements" element={<ComingSoon />} />
          {/* 代码质量模块 */}
          <Route path="code-quality" element={<ComingSoon />} />
          {/* API Hub 模块 (V2.0) */}
          <Route path="api-hub/definitions" element={<ProjectVersionGuard><ApiHubDefinitions /></ProjectVersionGuard>} />
          <Route path="api-hub/definitions/:id" element={<ProjectVersionGuard><ApiHubDefinitions /></ProjectVersionGuard>} />
          <Route path="api-hub/cases" element={<ProjectVersionGuard><ApiHubCases /></ProjectVersionGuard>} />
          <Route path="api-hub/sync" element={<ProjectVersionGuard><ApiHubSync /></ProjectVersionGuard>} />
          <Route path="api-hub/snapshots" element={<ProjectVersionGuard><ApiHubSnapshots /></ProjectVersionGuard>} />
          {/* 鉴权配置模块 */}
          <Route path="projects/:projectId/auth-config" element={<ProjectVersionGuard><AuthConfig /></ProjectVersionGuard>} />
          {/* UI 自动化模块 */}
          <Route path="ui-automation" element={<ComingSoon />} />
          {/* 流程编排模块 */}
          <Route path="orchestrator" element={<ComingSoon />} />
          {/* 基础设施模块 */}
          <Route path="infra" element={<ComingSoon />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

export default App