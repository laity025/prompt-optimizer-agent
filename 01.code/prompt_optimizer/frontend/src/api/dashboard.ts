// ==========================================================
// 资产管理门户/汇总仪表盘接口
// ==========================================================
import http from './http'
import type {
  DashboardModelStat,
  DashboardOverview,
  DashboardTaskAsset,
  DashboardTrend,
  DashboardVersionItem,
} from '@/types'

// 资产总览
export function getOverview() {
  return http.get<DashboardOverview, DashboardOverview>('/dashboard/overview')
}

// 近 N 天活动趋势
export function getTrend(days = 30) {
  return http.get<DashboardTrend, DashboardTrend>(`/dashboard/trend?days=${days}`)
}

// 任务资产表（可按名称搜索）
export function getTaskAssets(keyword = '') {
  return http.get<{ items: DashboardTaskAsset[]; total: number },
    { items: DashboardTaskAsset[]; total: number }>(
    `/dashboard/tasks?keyword=${encodeURIComponent(keyword)}`,
  )
}

// 模型统计
export function getModelStats() {
  return http.get<{ calls: DashboardModelStat[]; best_dist: { model: string; count: number }[] },
    { calls: DashboardModelStat[]; best_dist: { model: string; count: number }[] }>(
    '/dashboard/models',
  )
}

// Prompt 版本库检索
export function searchVersions(keyword = '', taskId?: number, limit = 50) {
  const params = new URLSearchParams()
  params.set('keyword', keyword)
  if (taskId) params.set('task_id', String(taskId))
  params.set('limit', String(limit))
  return http.get<{ items: DashboardVersionItem[]; total: number },
    { items: DashboardVersionItem[]; total: number }>(`/dashboard/versions?${params.toString()}`)
}
