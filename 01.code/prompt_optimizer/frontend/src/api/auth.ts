// ==========================================================
// 认证相关接口：注册 / 登录 / 登出 / 当前用户
// ==========================================================
import http from './http'
import type { LoginData, UserInfo } from '@/types'

// 注册：成功后返回用户信息
export function register(data: { email: string; password: string; full_name?: string }) {
  return http.post<UserInfo, UserInfo>('/auth/register', data)
}

// 登录：后端把登录态写入 HttpOnly cookie，响应体返回 token 与用户信息
export function login(data: { email: string; password: string }) {
  return http.post<LoginData, LoginData>('/auth/login', data)
}

// 退出登录：清除后端 HttpOnly cookie（幂等）
export function logout() {
  return http.post<null, null>('/auth/logout')
}

// 获取当前登录用户信息
export function getMe() {
  return http.get<UserInfo, UserInfo>('/auth/me')
}