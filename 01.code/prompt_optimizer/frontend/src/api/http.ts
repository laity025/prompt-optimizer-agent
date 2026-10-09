// ==========================================================
// HTTP 客户端：axios 实例 + 拦截器
// 统一处理：响应解包、401 跳转登录、错误提示
//   登录态通过 HttpOnly cookie 自动携带，前端不注入 Authorization；
//   在线服务调用走 X-Api-Key 头（由调用方显式设置，与登录态无关）
// ==========================================================
import axios, { AxiosError } from 'axios'
import { message } from 'antd'
import type { ApiResponse } from '@/types'

// 后端统一以 /api/v1 为基础路径（可通过请求动态拼接，这里直接内置）
const http = axios.create({
  baseURL: '/api/v1',
  timeout: 120000, // 大模型相关接口耗时较长，放宽超时
})

// 响应拦截器：解包统一响应结构，并集中处理业务错误码
http.interceptors.response.use(
  (response) => {
    // 文件下载（blob）场景：不经过 JSON 解包，直接返回原始数据
    if (response.config.responseType === 'blob') {
      return response.data as never
    }
    const body = response.data as ApiResponse<unknown>
    // code===0 表示成功，直接返回业务数据
    if (body && typeof body.code === 'number' && body.code === 0) {
      return body.data as never
    }
    // 鉴权失败（401）视为未登录/过期：清本地用户信息并跳转登录页
    if (body && body.code === 401) {
      localStorage.removeItem('user')
      if (!location.pathname.startsWith('/login')) {
        message.warning('登录已过期，请重新登录')
        location.href = '/login'
      }
    }
    // 其余业务错误向外抛出
    message.error(body?.message || '请求失败')
    return Promise.reject(new Error(body?.message || '请求失败'))
  },
  (error: AxiosError) => {
    // HTTP 层错误处理
    const status = error.response?.status
    if (status === 401) {
      localStorage.removeItem('user')
      if (!location.pathname.startsWith('/login')) {
        location.href = '/login'
      }
    }
    const data = error.response?.data as ApiResponse<unknown> | undefined
    message.error(data?.message || error.message || '网络错误')
    return Promise.reject(error)
  },
)

export default http