// ==========================================================
// 认证状态管理：基于 zustand 持久化用户信息
//   token 不再存 localStorage：登录态由后端通过 HttpOnly cookie 管理
//   （JS 不可读，防 XSS 窃取；浏览器请求自动携带）
// ==========================================================
import { create } from 'zustand'
import type { UserInfo } from '@/types'

interface AuthState {
  user: UserInfo | null
  // 登录成功后写入状态（token 由 cookie 托管，前端不落盘）
  setAuth: (user: UserInfo) => void
  // 更新用户信息（如角色变化后刷新）
  setUser: (user: UserInfo) => void
  // 退出登录：清空本地用户信息（cookie 由后端 /auth/logout 清除）
  logout: () => void
}

// 从 localStorage 读取已持久化的用户信息（非敏感字段：姓名/邮箱/角色）
function loadAuth() {
  const raw = localStorage.getItem('user')
  let user: UserInfo | null = null
  if (raw) {
    try {
      user = JSON.parse(raw) as UserInfo
    } catch {
      user = null
    }
  }
  return { user }
}

const init = loadAuth()

export const useAuthStore = create<AuthState>((set) => ({
  user: init.user,
  setAuth: (user) => {
    localStorage.setItem('user', JSON.stringify(user))
    set({ user })
  },
  setUser: (user) => {
    localStorage.setItem('user', JSON.stringify(user))
    set({ user })
  },
  logout: () => {
    localStorage.removeItem('user')
    set({ user: null })
  },
}))

// 判断是否为管理员
export function isAdmin(user?: UserInfo | null) {
  return (user ?? useAuthStore.getState().user)?.role === 'admin'
}
