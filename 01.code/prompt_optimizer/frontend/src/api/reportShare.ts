// ==========================================================
// 报告分享 API：创建/列表/撤销（登录态）+ 公开只读（免登录）
// ==========================================================
import http from './http'
import type {
  PublicReportData,
  ReportShareItem,
  ReportShareType,
} from '@/types'

// 创建分享链接
export function createShare(
  reportType: ReportShareType,
  targetId: number,
  expiresHours?: number,
) {
  return http.post<ReportShareItem, ReportShareItem>('/reports/shares', {
    report_type: reportType,
    target_id: targetId,
    expires_hours: expiresHours ?? null,
  })
}

// 我的分享列表
export function listShares() {
  return http.get<{ items: ReportShareItem[] }, { items: ReportShareItem[] }>('/reports/shares')
}

// 撤销分享
export function revokeShare(shareId: number) {
  return http.delete<{ id: number }, { id: number }>(`/reports/shares/${shareId}`)
}

// 公开：读取报告数据（免登录；token 无效/撤销/过期返回业务错误）
export function getPublicReportData<T = unknown>(token: string) {
  return http.get<PublicReportData<T>, PublicReportData<T>>(
    `/public/reports/${encodeURIComponent(token)}/data`,
  )
}

// 公开：读取链接元信息（免登录）
export function getPublicMeta(token: string) {
  return http.get<PublicReportData<null>['meta'], PublicReportData<null>['meta']>(
    `/public/reports/${encodeURIComponent(token)}`,
  )
}