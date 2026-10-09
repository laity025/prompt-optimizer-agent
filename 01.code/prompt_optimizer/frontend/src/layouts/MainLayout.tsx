// ==========================================================
// 主布局：黑色侧边导航 + 内容区（皇家蓝作品集 V2.0）
// ==========================================================
import { useState } from 'react'
import {
  UnorderedListOutlined,
  PlusOutlined,
  FileTextOutlined,
  TeamOutlined,
  LogoutOutlined,
  MenuOutlined,
  ExperimentOutlined,
  ApiOutlined,
  DatabaseOutlined,
  DashboardOutlined,
} from '@ant-design/icons'
import { Popconfirm } from 'antd'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'
import { useAuthStore, isAdmin } from '@/stores/auth'
import { logout as logoutApi } from '@/api/auth'
import { TASK_TYPE_LABEL } from '@/types'

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const [drawerOpen, setDrawerOpen] = useState(false)
  // 创建任务的"任务类型"子菜单是否展开：在创建页时默认展开
  const [typeMenuOpen, setTypeMenuOpen] = useState(() => location.pathname.startsWith('/tasks/new'))

  // 根据路由计算当前选中菜单项
  const selectedKey = (() => {
    if (location.pathname.startsWith('/dashboard')) return 'dashboard'
    if (location.pathname.startsWith('/tasks/new')) return 'new'
    if (location.pathname.startsWith('/tasks')) return 'tasks'
    if (location.pathname.startsWith('/benchmarks')) return 'benchmarks'
    if (location.pathname.startsWith('/services')) return 'services'
    if (location.pathname.startsWith('/knowledge')) return 'knowledge'
    if (location.pathname.startsWith('/workflows')) return 'workflows'
    if (location.pathname.startsWith('/admin/logs')) return 'logs'
    if (location.pathname.startsWith('/admin/users')) return 'users'
    return 'dashboard'
  })()

  // 记录路由 query，用于高亮侧边栏中当前选中的任务类型二级项
  const activeType = location.pathname.startsWith('/tasks/new')
    ? new URLSearchParams(location.search).get('type')
    : null
  const typeEntries = Object.entries(TASK_TYPE_LABEL) as [string, string][]

  const go = (path: string) => {
    navigate(path)
    setDrawerOpen(false)
  }

  const onLogout = async () => {
    // 先清后端 HttpOnly cookie（失败也继续本地清理，刷新后由 401 兜底）
    try {
      await logoutApi()
    } catch {
      /* 忽略网络异常 */
    }
    logout()
    navigate('/login', { replace: true })
  }

  const displayName = user?.full_name || user?.email || '用户'
  const avatarText = (user?.full_name || user?.email || 'U').slice(0, 1).toUpperCase()
  const roleText = isAdmin(user) ? '管理员' : '普通用户'

  const navBtn = (key: string, icon: React.ReactNode, label: string, path: string) => (
    <button
      type="button"
      className={`pe-nav-item ${selectedKey === key ? 'is-active' : ''}`}
      onClick={() => go(path)}
    >
      <span className="nav-ico">{icon}</span>
      {label}
    </button>
  )

  return (
    <div className="pe-app">
      {drawerOpen && <div className="pe-sidebar-backdrop" onClick={() => setDrawerOpen(false)} />}
      <aside className={`pe-sidebar ${drawerOpen ? 'is-open' : ''}`}>
        <a className="pe-brand" onClick={() => go('/tasks')}>
          <span className="pe-brand-mark" />
          <span>
            <span className="pe-brand-name" style={{ display: 'block' }}>
              PROMPT
              <br />
              EVOLVER
            </span>
            <span className="pe-brand-sub">提示词迭代智能体</span>
          </span>
        </a>

        <nav className="pe-nav">
          {navBtn('dashboard', <DashboardOutlined />, '资产门户', '/dashboard')}

          {/* 创建任务：一级标题，点击展开下方的"任务类型"二级子项 */}
          <button
            type="button"
            className={`pe-nav-item ${selectedKey === 'new' || typeMenuOpen ? 'is-active' : ''}`}
            onClick={() => setTypeMenuOpen((v) => !v)}
            aria-expanded={typeMenuOpen}
          >
            <span className="nav-ico"><PlusOutlined /></span>
            创建任务
            <span className={`pe-caret ${typeMenuOpen ? 'is-open' : ''}`}>▾</span>
          </button>
          {typeMenuOpen && (
            <div className="pe-nav-group-body">
              {typeEntries.map(([value, cn]) => (
                <button
                  key={value}
                  type="button"
                  className={`pe-nav-sub ${activeType === value ? 'is-active' : ''}`}
                  onClick={() => go(`/tasks/new?type=${value}`)}
                >
                  {cn}
                </button>
              ))}
            </div>
          )}

          {navBtn('tasks', <UnorderedListOutlined />, '任务列表', '/tasks')}
          {navBtn('benchmarks', <ExperimentOutlined />, '模型评测', '/benchmarks')}
          {navBtn('services', <ApiOutlined />, '在线服务', '/services')}
          {navBtn('knowledge', <DatabaseOutlined />, '知识库', '/knowledge')}

          {isAdmin(user) && <div className="pe-nav-sep">ADMIN · 管理员</div>}
          {isAdmin(user) && navBtn('logs', <FileTextOutlined />, '系统日志', '/admin/logs')}
          {isAdmin(user) && navBtn('users', <TeamOutlined />, '用户管理', '/admin/users')}
        </nav>

        <div className="pe-nav-spacer" />

        <div className="pe-user">
          <span className="pe-avatar">{avatarText}</span>
          <span className="pe-user-meta">
            <span className="pe-user-name" style={{ display: 'block' }}>
              {displayName}
            </span>
            <span className="pe-user-role" style={{ display: 'block' }}>
              {roleText}
              {user?.email ? ` · ${user.email}` : ''}
            </span>
          </span>
          <Popconfirm
            title="退出登录"
            description="确定退出当前账号吗？"
            okText="退出"
            cancelText="取消"
            placement="topRight"
            onConfirm={onLogout}
          >
            <button type="button" className="pe-user-out" title="退出登录">
              <LogoutOutlined style={{ fontSize: 16 }} />
            </button>
          </Popconfirm>
        </div>
      </aside>

      <main className="pe-main">
        <div className="pe-main-inner">
          {/* 移动端顶栏 */}
          <div className="pe-mobile-bar">
            <button type="button" className="pe-ico-btn" onClick={() => setDrawerOpen(true)} aria-label="打开菜单">
              <MenuOutlined />
            </button>
            <span className="font-display" style={{ fontWeight: 900, letterSpacing: '0.02em' }}>
              PROMPT EVOLVER
            </span>
          </div>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
