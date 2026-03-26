import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const service = axios.create({
  // 生产环境使用相对路径 /api/v1 (通过 Nginx 代理)，开发环境使用 localhost:8010
  baseURL: import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? '/api/v1' : 'http://localhost:8010/api/v1'),
  timeout: 600000 // 大模型偶发较慢，超时提高到 10min（与后端降级策略配合）
})

// Request interceptor
service.interceptors.request.use(
  config => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers['Authorization'] = `Bearer ${authStore.token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// Response interceptor
service.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    const status = error.response?.status
    const request_url = error.config?.url || ''

    // 登录接口返回 401 是“用户名或密码错误”，不要误判为 token 过期并强制登出跳转
    if (status === 401 && !request_url.includes('/auth/login')) {
      ElMessage.error('登录已过期，请重新登录')
      const authStore = useAuthStore()
      authStore.logout()
      setTimeout(() => {
        window.location.href = '/'
      }, 1000)
    } else if (error.response && error.response.status === 404) {
      ElMessage.error(error.response.data?.detail || '资源不存在')
    } else {
      ElMessage.error(error.response?.data?.detail || error.message || '请求失败')
    }
    return Promise.reject(error)
  }
)

export default service

