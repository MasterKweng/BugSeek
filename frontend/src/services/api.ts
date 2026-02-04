import axios from 'axios'
import { useAuthStore } from '../store/auth'

// 创建自定义 axios 实例，拦截器返回 response.data
const instance = axios.create({
  baseURL: '/api/v1',
  timeout: 60000, // 增加到60秒，适应依赖分析等耗时操作
})

// 请求拦截器
instance.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // 检查 URL 中的参数是否包含 NaN
    if (config.url) {
      const urlParams = config.url.match(/\/(\d+)/g)
      if (urlParams) {
        for (const param of urlParams) {
          const id = parseInt(param.slice(1))
          if (isNaN(id)) {
            return Promise.reject(new Error('URL 中包含无效的 ID 参数'))
          }
        }
      }
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器：统一返回标准格式 { code, message, data }
instance.interceptors.response.use(
  (response) => {
    // 如果后端返回的是标准格式 { code, message, data }，直接返回
    const data = response.data
    if (typeof data === 'object' && 'code' in data) {
      return data
    }
    // 否则包装成标准格式
    return { code: 0, message: 'success', data }
  },
  (error) => {
    // 401 未授权，静默跳转登录
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
      return Promise.reject(error)
    }

    // 500 服务器错误
    if (error.response?.status >= 500) {
      return Promise.reject({ ...error, message: '服务开小差了，请稍后重试' })
    }

    // 网络超时
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      return Promise.reject({ ...error, message: '网络连接不稳定，请检查网络后重试' })
    }

    // 网络错误
    if (!error.response) {
      return Promise.reject({ ...error, message: '网络连接失败，请检查网络' })
    }

    return Promise.reject(error)
  }
)

// 导出带类型的 API 实例
const api = instance as any
export default api

// 导出 API 响应类型
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}