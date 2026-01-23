import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { useEffect } from 'react'

interface ProtectedRouteProps {
  children: React.ReactNode
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, checkAuth } = useAuthStore()
  const location = useLocation()

  // 组件挂载时检查认证状态
  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

export default ProtectedRoute