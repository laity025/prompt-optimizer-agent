// ==========================================================
// 路由定义：认证守卫、管理员守卫、页面挂载
// ==========================================================
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuthStore, isAdmin } from '@/stores/auth'
import Login from '@/pages/Login'
import MainLayout from '@/layouts/MainLayout'
import TaskList from '@/pages/tasks/TaskList'
import TaskCreate from '@/pages/tasks/TaskCreate'
import TaskDetail from '@/pages/tasks/TaskDetail'
import Dashboard from '@/pages/Dashboard'
import ModelBenchmark from '@/pages/tasks/ModelBenchmark'
import OnlineService from '@/pages/services/OnlineService'
import KnowledgeBase from '@/pages/knowledge/KnowledgeBase'
import WorkflowBoard from '@/pages/workflows/WorkflowBoard'
import ShareCenter from '@/pages/ShareCenter'
import PublicReport from '@/pages/PublicReport'
import AdminLogs from '@/pages/admin/Logs'
import AdminUsers from '@/pages/admin/Users'

// 认证守卫：未登录跳转到登录页
// 登录态由后端 HttpOnly cookie 管理（前端无 token 概念），本地只存用户信息；
// 会话是否有效由后端 401 兜底（http.ts 统一清本地并跳登录）
function RequireAuth({ children }: { children: React.ReactElement }) {
  const user = useAuthStore((s) => s.user)
  const location = useLocation()
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return children
}

// 管理员守卫：非管理员访问管理页时重定向到任务列表
function RequireAdmin({ children }: { children: React.ReactElement }) {
  if (!isAdmin()) {
    return <Navigate to="/tasks" replace />
  }
  return children
}

// 应用外层：只承载路由
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 登录页独立布局 */}
        <Route path="/login" element={<Login />} />
        {/* 公开报告页：免登录，任何持链接者可访问 */}
        <Route path="/share/:token" element={<PublicReport />} />
        {/* 主界面，需登录 */}
        <Route
          path="/"
          element={
            <RequireAuth>
              <MainLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="tasks" element={<TaskList />} />
          <Route path="tasks/new" element={<TaskCreate />} />
          <Route path="tasks/:id" element={<TaskDetail />} />
          <Route path="benchmarks" element={<ModelBenchmark />} />
          <Route path="services" element={<OnlineService />} />
          <Route path="knowledge" element={<KnowledgeBase />} />
          <Route path="workflows" element={<WorkflowBoard />} />
          <Route path="shares" element={<ShareCenter />} />
          <Route
            path="admin/logs"
            element={
              <RequireAdmin>
                <AdminLogs />
              </RequireAdmin>
            }
          />
          <Route
            path="admin/users"
            element={
              <RequireAdmin>
                <AdminUsers />
              </RequireAdmin>
            }
          />
          {/* 兜底重定向 */}
          <Route path="*" element={<Navigate to="/tasks" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}