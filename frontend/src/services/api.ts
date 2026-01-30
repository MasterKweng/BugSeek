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
    console.log('请求拦截器 - URL:', config.url, 'Token存在:', !!token)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
      console.log('已添加Authorization头，Token前20字符:', token.substring(0, 20) + '...')
    } else {
      console.warn('Token不存在，未添加Authorization头')
    }

    // 检查 URL 中的参数是否包含 NaN
    if (config.url) {
      const urlParams = config.url.match(/\/(\d+)/g)
      if (urlParams) {
        for (const param of urlParams) {
          const id = parseInt(param.slice(1))
          if (isNaN(id)) {
            console.error('URL 中包含无效的 ID 参数:', config.url)
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

// 响应拦截器：直接返回 response.data
instance.interceptors.response.use(
  (response) => {
    return response.data
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
      console.error('服务器错误:', error.response?.data?.message || '服务开小差了')
      return Promise.reject({ ...error, message: '服务开小差了，请稍后重试' })
    }

    // 网络超时
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      console.error('请求超时:', error.message)
      return Promise.reject({ ...error, message: '网络连接不稳定，请检查网络后重试' })
    }

    // 网络错误
    if (!error.response) {
      console.error('网络错误:', error.message)
      return Promise.reject({ ...error, message: '网络连接失败，请检查网络' })
    }

    return Promise.reject(error)
  }
)

// 导出带类型的 API 实例
const api = instance as any
export default api