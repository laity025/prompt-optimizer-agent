// ==========================================================
// 多步工作流 API：CRUD / 步骤编排 / 执行评测 / 报告
// ==========================================================
import http from './http'
import type { Workflow, WorkflowOptItem, WorkflowOptReport, WorkflowReport, WorkflowRunItem, WorkflowStep } from '@/types'

// 创建工作流（可携带初始步骤）
export function createWorkflow(taskId: number, data: {
  name: string; description?: string; steps?: Partial<WorkflowStep>[]
}) {
  return http.post<Workflow, Workflow>(`/tasks/${taskId}/workflows`, data)
}

// 任务的工作流列表
export function listWorkflows(taskId: number) {
  return http.get<{ items: Workflow[]; total: number }, { items: Workflow[]; total: number }>(
    `/tasks/${taskId}/workflows`,
  )
}

// 工作流详情（含步骤）
export function getWorkflow(taskId: number, wfId: number) {
  return http.get<Workflow, Workflow>(`/tasks/${taskId}/workflows/${wfId}`)
}

// 更新工作流（可整体替换步骤）
export function updateWorkflow(taskId: number, wfId: number, data: {
  name?: string; description?: string; steps?: Partial<WorkflowStep>[]
}) {
  return http.put<Workflow, Workflow>(`/tasks/${taskId}/workflows/${wfId}`, data)
}

// 删除工作流
export function deleteWorkflow(taskId: number, wfId: number) {
  return http.delete<{ id: number }, { id: number }>(`/tasks/${taskId}/workflows/${wfId}`)
}

// 执行工作流（异步）
export function runWorkflow(taskId: number, wfId: number, runBaseline = true) {
  return http.post<{ run_id: number; status: string }, { run_id: number; status: string }>(
    `/tasks/${taskId}/workflows/${wfId}/run`, { run_baseline: runBaseline },
  )
}

// 运行历史
export function listRuns(taskId: number, wfId: number) {
  return http.get<{ items: WorkflowRunItem[]; total: number },
    { items: WorkflowRunItem[]; total: number }>(`/tasks/${taskId}/workflows/${wfId}/runs`)
}

// 运行报告
export function getRunReport(taskId: number, wfId: number, runId: number) {
  return http.get<WorkflowReport, WorkflowReport>(
    `/tasks/${taskId}/workflows/${wfId}/runs/${runId}`,
  )
}

// 启动对某步骤的自动迭代优化（异步）
export function startStepOptimization(taskId: number, wfId: number, seq: number, maxRounds = 3) {
  return http.post<{ opt_id: number; status: string }, { opt_id: number; status: string }>(
    `/tasks/${taskId}/workflows/${wfId}/steps/${seq}/optimize`, { max_rounds: maxRounds },
  )
}

// 步骤优化历史
export function listOptimizations(taskId: number, wfId: number) {
  return http.get<{ items: WorkflowOptItem[]; total: number },
    { items: WorkflowOptItem[]; total: number }>(
    `/tasks/${taskId}/workflows/${wfId}/optimizations`,
  )
}

// 步骤优化报告（含变体明细）
export function getOptReport(taskId: number, wfId: number, optId: number) {
  return http.get<WorkflowOptReport, WorkflowOptReport>(
    `/tasks/${taskId}/workflows/${wfId}/optimizations/${optId}`,
  )
}