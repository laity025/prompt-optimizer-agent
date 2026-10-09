// ==========================================================
// 管理员接口：系统日志 / 用户管理
// ==========================================================
import http from './http'
import type { AdminLogItem, AdminUserUpdateParams, PageResult, UserInfo } from '@/types'

// 系统日志（管理员）
export function getLogs(params?: { page?: number; page_size?: number; user_id?: number; result?: string }) {
  return http.get<PageResult<AdminLogItem>, PageResult<AdminLogItem>>('/admin/logs', { params })
}

// 用户列表（管理员）
export function getAdminUsers(params?: { page?: number; page_size?: number; role?: string }) {
  return http.get<PageResult<UserInfo>, PageResult<UserInfo>>('/admin/users', { params })
}

// 修改用户角色 / 启停账号（管理员）
export function updateAdminUser(userId: number, data: AdminUserUpdateParams) {
  return http.put<UserInfo, UserInfo>(`/admin/users/${userId}`, data)
}