// ==========================================================
// 在线服务 API：创建/列表/详情/更新/轮换密钥/删除 + 调用/日志/统计
//   调用接口需携带 X-Api-Key 头（不依赖登录态，模拟对外服务）
// ==========================================================
import http from './http'
import type {
  EndpointCallLogItem,
  EndpointDetail,
  EndpointInvokeResult,
  EndpointItem,
  EndpointStats,
  Version,
} from '@/types'

// 创建在线服务
export function createEndpoint(data: {
  task_id: number
  name?: string
  description?: string
  version_id?: number | null
  model?: string
}) {
  return http.post<{ id: number; api_key: string }, { id: number; api_key: string }>('/endpoints', data)
}

// 我的在线服务列表
export function listEndpoints() {
  return http.get<{ items: EndpointItem[]; total: number }, { items: EndpointItem[]; total: number }>('/endpoints')
}

// 详情（含密钥）
export function getEndpoint(id: number) {
  return http.get<EndpointDetail, EndpointDetail>(`/endpoints/${id}`)
}

// 更新（改名/描述/启停）
export function updateEndpoint(id: number, data: { name?: string; description?: string; active?: number }) {
  return http.put<{ id: number; active: number }, { id: number; active: number }>(`/endpoints/${id}`, data)
}

// 轮换密钥
export function rotateEndpointKey(id: number) {
  return http.post<{ id: number; api_key: string }, { id: number; api_key: string }>(`/endpoints/${id}/rotate-key`)
}

// 删除
export function deleteEndpoint(id: number) {
  return http.delete<{ id: number }, { id: number }>(`/endpoints/${id}`)
}

// 调用日志
export function getEndpointLogs(id: number, page = 1, pageSize = 20) {
  return http.get<{ items: EndpointCallLogItem[]; total: number },
    { items: EndpointCallLogItem[]; total: number }>(`/endpoints/${id}/logs`, {
    params: { page, page_size: pageSize },
  })
}

// 调用统计
export function getEndpointStats(id: number) {
  return http.get<EndpointStats, EndpointStats>(`/endpoints/${id}/stats`)
}

// 在线调用（携带 api_key）
export function invokeEndpoint(id: number, input: string, apiKey: string) {
  return http.post<EndpointInvokeResult, EndpointInvokeResult>(
    `/endpoints/${id}/invoke`,
    { input },
    { headers: { 'X-Api-Key': apiKey } },
  )
}

// 任务的版本列表（创建时选择冻结版本）
export function listEndpointVersions(taskId: number) {
  return http.get<Version[], Version[]>(`/tasks/${taskId}/versions`)
}