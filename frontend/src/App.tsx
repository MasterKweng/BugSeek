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

// 接口集成模块
const Documents = lazy(() => import('./pages/api/Documents'))
const Endpoints = lazy(() => import('./pages/api/Endpoints'))
const Scripts = lazy(() => import('./pages/api/Scripts'))
const Scenarios = lazy(() => import('./pages/api/Scenarios'))
const Mock = lazy(() => import('./pages/api/Mock'))
const TestSuites = lazy(() => import('./pages/api/TestSuites'))
const Executions = lazy(() => import('./pages/api/Executions'))
const Reports = lazy(() => import('./pages/api/Reports'))

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
          {/* 接口集成模块 */}
          <Route path="api/documents" element={<ProjectVersionGuard><Documents /></ProjectVersionGuard>} />
          <Route path="api/endpoints" element={<ProjectVersionGuard><Endpoints /></ProjectVersionGuard>} />
          <Route path="api/scripts" element={<ProjectVersionGuard><Scripts /></ProjectVersionGuard>} />
          <Route path="api/scenarios" element={<ProjectVersionGuard><Scenarios /></ProjectVersionGuard>} />
          <Route path="api/mock" element={<ProjectVersionGuard><Mock /></ProjectVersionGuard>} />
          <Route path="api/suites" element={<ProjectVersionGuard><TestSuites /></ProjectVersionGuard>} />
          <Route path="api/executions" element={<ProjectVersionGuard><Executions /></ProjectVersionGuard>} />
          <Route path="api/reports" element={<ProjectVersionGuard><Reports /></ProjectVersionGuard>} />
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